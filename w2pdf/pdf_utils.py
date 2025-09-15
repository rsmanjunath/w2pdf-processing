import PyPDF2
import re

def extract_w2_fields(pdf_input, use_file_path=False):
    """
    Extract required W-2 fields from PDF file or file path.
    Returns dictionary with EIN, SSN, wages, and federal tax withheld.
    Supports both in-memory and file-path processing for large files.
    """
    try:
        if use_file_path:
            # Process file from disk (for large files processed in chunks)
            with open(pdf_input, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = _extract_text_from_reader(reader)
        else:
            # Process file from memory (for small files)
            pdf_input.seek(0)
            reader = PyPDF2.PdfReader(pdf_input)
            text = _extract_text_from_reader(reader)
        
        # Extract required fields using regex patterns
        fields = _parse_w2_fields(text)
        
        # Validate all required fields are present
        required_fields = ['ein', 'ssn', 'wages', 'federal_tax_withheld']
        missing_fields = [field for field in required_fields if field not in fields]
        
        if missing_fields:
            raise ValueError(f"Missing required fields in PDF: {', '.join(missing_fields)}")
        
        return fields
        
    except Exception as e:
        if "Missing required fields" in str(e):
            raise  # Re-raise ValueError for missing fields
        raise Exception(f"Failed to process PDF: {e}")

def _extract_text_from_reader(reader):
    """Extract text from all pages of a PDF reader object"""
    text = ""
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        text += page.extract_text() + "\n"
    return text

def _parse_w2_fields(text):
    """Parse W-2 fields from extracted PDF text using regex patterns"""
    fields = {}
    
    # EIN pattern (XX-XXXXXXX)
    ein_match = re.search(r'(?:EIN|Employer.{0,20}ID|Federal.{0,20}ID).{0,20}(\d{2}-\d{7})', text, re.IGNORECASE)
    if ein_match:
        fields['ein'] = ein_match.group(1)
    
    # SSN pattern (XXX-XX-XXXX)
    ssn_match = re.search(r'(?:SSN|Social.{0,20}Security|Employee.{0,20}SSN).{0,20}(\d{3}-\d{2}-\d{4})', text, re.IGNORECASE)
    if ssn_match:
        fields['ssn'] = ssn_match.group(1)
    
    # Box 1 - Wages (look for monetary amounts)
    wages_match = re.search(r'(?:Box.{0,5}1|Wages).{0,20}\$?([\d,]+\.?\d{0,2})', text, re.IGNORECASE)
    if wages_match:
        wage_str = wages_match.group(1).replace(',', '')
        fields['wages'] = float(wage_str)
    
    # Box 2 - Federal tax withheld
    tax_match = re.search(r'(?:Box.{0,5}2|Federal.{0,20}tax|Tax.{0,20}withheld).{0,20}\$?([\d,]+\.?\d{0,2})', text, re.IGNORECASE)
    if tax_match:
        tax_str = tax_match.group(1).replace(',', '')
        fields['federal_tax_withheld'] = float(tax_str)
    
    return fields
