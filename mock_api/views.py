

import uuid
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

SECRET_KEY = settings.SECRET_KEY


@api_view(['POST'])
def mock_report(request):
	"""
	Receives W-2 data, returns a unique id. Requires secret key for authentication.
	"""
	try:
		logger.info(f"Mock report API called from {request.META.get('REMOTE_ADDR')}")
		
		# Validate authentication
		secret = request.headers.get('X-API-SECRET')
		if not secret:
			logger.warning("Mock report API called without secret key")
			return Response({'error': 'Unauthorized: Missing secret key.'}, status=status.HTTP_401_UNAUTHORIZED)
		
		if secret != SECRET_KEY:
			logger.warning(f"Mock report API called with invalid secret key: {secret[:8]}...")
			return Response({'error': 'Unauthorized: Invalid secret key.'}, status=status.HTTP_401_UNAUTHORIZED)
		
		# Validate request data exists
		if not request.data:
			logger.warning("Mock report API called with empty request data")
			return Response({'error': 'Request data is required.'}, status=status.HTTP_400_BAD_REQUEST)
		
		# Log received data for debugging (without sensitive info)
		logger.info(f"Mock report API processing data with keys: {list(request.data.keys())}")
		
		# Generate unique ID
		unique_id = str(uuid.uuid4())
		logger.info(f"Mock report API generated ID: {unique_id}")
		
		return Response({'id': unique_id}, status=status.HTTP_200_OK)
	
	except Exception as e:
		logger.error(f"Mock report API - Unexpected error: {e}")
		return Response({'error': 'Internal server error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def mock_upload(request):
	"""
	Receives a unique id and a file, returns a unique file id. Requires secret key for authentication.
	"""
	try:
		
		# Validate authentication
		secret = request.headers.get('X-API-SECRET')
		if not secret:
			logger.warning("Mock upload API called without secret key")
			return Response({'error': 'Unauthorized: Missing secret key.'}, status=status.HTTP_401_UNAUTHORIZED)
		
		if secret != SECRET_KEY:
			logger.warning(f"Mock upload API called with invalid secret key: {secret[:8]}...")
			return Response({'error': 'Unauthorized: Invalid secret key.'}, status=status.HTTP_401_UNAUTHORIZED)
		
		# Validate required fields
		unique_id = request.POST.get('unique_id')
		file = request.FILES.get('file')
		
		if not unique_id:
			logger.warning("Mock upload API called without unique_id")
			return Response({'error': 'unique_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
		
		if not file:
			logger.warning("Mock upload API called without file")
			return Response({'error': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)
		
		# Validate file properties
		if file.size == 0:
			logger.warning(f"Mock upload API received empty file: {file.name}")
			return Response({'error': 'Uploaded file is empty.'}, status=status.HTTP_400_BAD_REQUEST)
		
		
		# Log file info for debugging
		logger.info(f"Mock upload API processing file: {file.name} ({file.size} bytes) with ID: {unique_id}")
		
		# Generate file ID
		file_id = str(uuid.uuid4())
		logger.info(f"Mock upload API generated file ID: {file_id}")
		
		return Response({'file_id': file_id}, status=status.HTTP_200_OK)
	
	
	except Exception as e:
		logger.error(f"Mock upload API - Unexpected error: {e}")
		return Response({'error': 'Internal server error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
