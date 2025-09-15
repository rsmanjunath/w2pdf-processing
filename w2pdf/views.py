
import asyncio
import httpx
import tempfile
import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import W2PDFUploadSerializer
from .pdf_utils import extract_w2_fields
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB - files larger than this use chunked processing
CHUNK_SIZE = 64 * 1024              # 64KB chunks for reading
REQUEST_TIMEOUT = 30                # Timeout for third-party API calls


@method_decorator(csrf_exempt, name='dispatch')  # Exempt from CSRF for API usage
class W2PDFUploadView(APIView):
	"""
	Async API endpoint to accept a W-2 PDF, extract fields, and report to third-party API.
	Optimized for handling large PDF files with chunk-by-chunk processing.
	"""
	
	def _should_use_chunked_processing(self, pdf_file):
		"""Determine if file should be processed in chunks instead of loading fully into memory"""
		return pdf_file.size > MAX_MEMORY_SIZE
	
	def _validate_pdf_file(self, pdf_file):
		"""Validate PDF file format, type, and size"""
		if not pdf_file.name.lower().endswith('.pdf'):
			return {'error': 'File extension must be .pdf'}
		
		if hasattr(pdf_file, 'content_type') and pdf_file.content_type != 'application/pdf':
			return {'error': 'Content type must be application/pdf'}
		
		if pdf_file.size == 0:
			return {'error': 'Uploaded file is empty.'}
		return None
	
	async def _save_file_in_chunks(self, pdf_file):
		"""Save uploaded file to temporary location using chunk-by-chunk reading"""
		temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
		try:
			pdf_file.seek(0)
			bytes_written = 0
			
			while True:
				chunk = pdf_file.read(CHUNK_SIZE)
				if not chunk:
					break
				temp_file.write(chunk)
				bytes_written += len(chunk)
				
				# Log progress for very large files
				if bytes_written % (1024 * 1024) == 0:
					logger.info(f"Processed {bytes_written // (1024 * 1024)}MB of PDF file")
			
			temp_file.close()
			return temp_file.name
		except Exception as e:
			# Clean up temp file
			temp_file.close()
			if os.path.exists(temp_file.name):
				os.unlink(temp_file.name)
			logger.error(f"Failed to save file in chunks: {e}")
			raise e
	
	def _cleanup_temp_file(self, temp_file_path):
		"""Safely clean up temporary file"""
		if temp_file_path and os.path.exists(temp_file_path):
			try:
				os.unlink(temp_file_path)
				logger.debug(f"Cleaned up temp file: {temp_file_path}")
			except Exception as e:
				logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")
	
	async def _extract_pdf_fields(self, pdf_file):
		"""Extract fields from PDF with proper error handling"""
		temp_file_path = None
		try:
			if self._should_use_chunked_processing(pdf_file):
				logger.info(f"Using chunked processing for large file: {pdf_file.name} ({pdf_file.size} bytes)")
				temp_file_path = await self._save_file_in_chunks(pdf_file)
				fields = await asyncio.to_thread(extract_w2_fields, temp_file_path, use_file_path=True)
			else:
				logger.info(f"Processing small file in memory: {pdf_file.name}")
				fields = await asyncio.to_thread(extract_w2_fields, pdf_file)
			
			logger.info("PDF field extraction successful")
			return fields
		finally:
			self._cleanup_temp_file(temp_file_path)
	
	def _handle_third_party_response(self, response, operation_name):
		"""Handle third-party API response with proper error codes"""
		if response.status_code == 401:
			logger.error(f"Third-party API authentication failed for {operation_name}")
			return Response({'error': f'Authentication failed with third-party API for {operation_name}.'}, 
						   status=status.HTTP_502_BAD_GATEWAY)
		
		if response.status_code == 400:
			logger.error(f"Third-party API rejected {operation_name}: {response.text}")
			return Response({'error': f'Third-party API rejected {operation_name}.'}, 
						   status=status.HTTP_502_BAD_GATEWAY)
		
		if response.status_code >= 500:
			logger.error(f"Third-party API server error for {operation_name}: {response.status_code}")
			return Response({'error': f'Third-party API server error for {operation_name}.'}, 
						   status=status.HTTP_502_BAD_GATEWAY)
		
		if response.status_code != 200:
			logger.error(f"Unexpected third-party API response for {operation_name}: {response.status_code}")
			raise Exception(f"Third-party {operation_name} API error: {response.text}")
		
		return None
	
	async def _report_data_to_third_party(self, fields, client):
		"""Report extracted data to third-party API"""
		logger.info("Reporting extracted data to third-party API")
		
		response = await client.post(
			settings.THIRD_PARTY_UPLOAD_URL, 
			json=fields, 
			headers={'X-API-SECRET': settings.SECRET_KEY}, 
			timeout=REQUEST_TIMEOUT
		)
		
		error_response = self._handle_third_party_response(response, "data reporting")
		if error_response:
			return error_response
		
		data_response = response.json()
		data_id = data_response.get('id')
		logger.info(f"Data reported successfully, received ID: {data_id}")
		return data_id
	
	async def _upload_file_to_third_party(self, pdf_file, data_id, client):
		"""Upload original file to third-party API"""
		logger.info("Uploading original file to third-party API")
		
		pdf_file.seek(0)
		files = {'file': (pdf_file.name, pdf_file, 'application/pdf')}
		data = {'unique_id': data_id} if data_id else {}
		
		response = await client.post(
			settings.THIRD_PARTY_UPLOAD_URL, 
			files=files,
			data=data,
			headers={'X-API-SECRET': settings.SECRET_KEY}, 
			timeout=REQUEST_TIMEOUT
		)
		
		error_response = self._handle_third_party_response(response, "file upload")
		if error_response:
			return error_response
		
		upload_response = response.json()
		file_id = upload_response.get('file_id')
		logger.info(f"File uploaded successfully, received file ID: {file_id}")
		return file_id

	async def post(self, request, *args, **kwargs):
		
		logger.info(f"W-2 PDF upload request received from {request.META.get('REMOTE_ADDR')}")
		
		# Step 1: Validate 
		serializer = W2PDFUploadSerializer(data=request.data)
		if not serializer.is_valid():
			logger.warning(f"Invalid serializer data: {serializer.errors}")
			return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

		pdf_file = serializer.validated_data['file']
		
		validation_error = self._validate_pdf_file(pdf_file)
		if validation_error:
			logger.warning(f"PDF validation failed: {validation_error}")
			return Response(validation_error, status=status.HTTP_400_BAD_REQUEST)

		# Step 2: Extraction
		try:
			fields = await self._extract_pdf_fields(pdf_file)
		except ValueError as ve:
			logger.error(f"PDF parsing error: {ve}")
			return Response({'error': f'PDF parsing error: {ve}'}, 
						   status=status.HTTP_422_UNPROCESSABLE_ENTITY)
		except Exception as e:
			logger.error(f"Failed to read PDF: {e}")
			return Response({'error': f'Failed to read PDF: {e}'}, 
						   status=status.HTTP_422_UNPROCESSABLE_ENTITY)

		# Step 3: Report data and upload file to third-party API
		try:
			data_id, file_id = await self._process_third_party_integration(pdf_file, fields)
		except httpx.ConnectError as e:
			logger.error(f"Connection error to third-party API: {e}")
			return Response({'error': 'Unable to connect to third-party API.'}, 
						   status=status.HTTP_502_BAD_GATEWAY)
		except httpx.TimeoutException as e:
			logger.error(f"Timeout contacting third-party API: {e}")
			return Response({'error': 'Timeout contacting third-party API.'}, 
						   status=status.HTTP_504_GATEWAY_TIMEOUT)
		except httpx.RequestError as e:
			logger.error(f"Network error contacting third-party API: {e}")
			return Response({'error': f'Network error contacting third-party API: {e}'}, 
						   status=status.HTTP_502_BAD_GATEWAY)
		except Exception as e:
			logger.error(f"Unexpected error during third-party API calls: {e}")
			return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
		response_data = {
			'message': 'W-2 processed and reported successfully',
			'extracted_fields': fields,
			'data_id': data_id,
			'file_id': file_id
		}
		logger.info(f"W-2 processing completed successfully for file: {pdf_file.name}")
		return Response(response_data, status=status.HTTP_200_OK)
	
	async def _process_third_party_integration(self, pdf_file, fields):
		"""Handle the complete third-party API integration process"""
		async with httpx.AsyncClient() as client:
			data_id = await self._report_data_to_third_party(fields, client)
			if isinstance(data_id, Response):  # Error response returned
				raise Exception(f"Data reporting failed: {data_id.data}")
			
			# Upload original file with data ID
			file_id = await self._upload_file_to_third_party(pdf_file, data_id, client)
			if isinstance(file_id, Response):  # Error response returned
				raise Exception(f"File upload failed: {file_id.data}")
			
			return data_id, file_id


@api_view(['GET', 'POST', 'OPTIONS'])
def cors_test(request):
	"""
	Simple endpoint to test CORS functionality.
	Returns basic info about the request for debugging.
	"""
	return Response({
		'message': 'CORS is working!',
		'method': request.method,
		'origin': request.META.get('HTTP_ORIGIN', 'No origin header'),
		'user_agent': request.META.get('HTTP_USER_AGENT', 'No user agent'),
		'headers': dict(request.headers),
	}, status=status.HTTP_200_OK)
