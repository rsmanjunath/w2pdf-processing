
### 1. Validating incoming request and processing asynchronously.

### 2. Added various error handling scenarios with appropriate http status codes.
### 3. CORS headers are added to responses to allow cross-origin requests from the frontend.

### 4. Validating file extension and request content type is application/pdf.

### 5. Assuming pdf can be of larger size. When the file is large processing(greater than 2mb) it by chunking else load all in memory.

### 6. Added Exception handling for pdf parsing.

### 7. For Simplicity, assuming the pdf is text based and not scanned image. So using PyPDF2 to extract text.

### 8. Using regex to extract required fields assuming the fields are in standard format.

### 9. Validating all required fields are extracted.

### 10. Assuming third party apis are reliable and will return 200 on success. If not returning 502 to client.

### 11. Authentication to third party apis is done using a simple secret key in headers.

### 12. Added various error handling scenarios with appropriate http status codes.

### 13. Logging at various steps for debugging and traceability.

### 14. Mocking third party apis within the same project for simplicity.

### 15. Returning both data id and file id received from third party apis to client on success.

### 16. Cleaning up any temporary files created during processing.

### 17. If processing takes time celery or background jobs can be used. But for simplicity processing is done within the request.


