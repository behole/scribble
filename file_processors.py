import os
import logging
import requests
import pytesseract
from PIL import Image
import PyPDF2
from bs4 import BeautifulSoup
import json
import re
import urllib.parse

class BaseProcessor:
    """Base class for all file processors."""
    
    def __init__(self, db_manager=None, llm_service=None):
        self.db_manager = db_manager
        self.llm_service = llm_service
    
    def process(self, file_path):
        """Process the file and return extracted content."""
        raise NotImplementedError("Subclasses must implement process()")
    
    def _extract_tags(self, text):
        """Extract hashtags from text."""
        if not text:
            return []
        
        # Find all hashtags using regex
        hashtags = re.findall(r'#(\w+)', text)
        return hashtags
    
    def _extract_tasks(self, text):
        """Extract tasks from text."""
        if not text:
            return []
        
        # Simple task extraction - look for common task indicators
        tasks = []
        
        # Check for lines starting with task markers
        markers = ['- [ ]', '* [ ]', '[] ', 'TODO:', 'TASK:']
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            for marker in markers:
                if line.startswith(marker):
                    tasks.append(line[len(marker):].strip())
                    break
        
        # If using LLM service, we could ask it to extract tasks
        if self.llm_service and not tasks:
            # This would be implemented when we add the LLM service
            pass
            
        return tasks


class ImageProcessor(BaseProcessor):
    """Process image files including screenshots."""
    
    def process(self, file_path):
        """Process image using OCR."""
        try:
            # Open the image
            image = Image.open(file_path)
            
            # Perform OCR
            extracted_text = pytesseract.image_to_string(image)
            
            # Process with LLM
            processed_text = None
            if self.llm_service:
                # This would be implemented when we add the LLM service
                pass
            
            # Extract tags and tasks
            tags = self._extract_tags(extracted_text)
            tasks = self._extract_tasks(extracted_text)
            
            return {
                'raw_text': extracted_text,
                'processed_text': processed_text,
                'tags': tags,
                'tasks': tasks
            }
        except Exception as e:
            logging.error(f"Error processing image {file_path}: {e}")
            return None


class PDFProcessor(BaseProcessor):
    """Process PDF files."""
    
    def process(self, file_path):
        """Extract text from PDF."""
        try:
            logging.info(f"Starting PDF processing for {file_path}")
            extracted_text = ""
            images_extracted = False
            temp_images = []
            
            # First try with PyPDF2
            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                logging.info(f"PDF has {len(pdf_reader.pages)} pages")
                
                # Extract text from each page
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    logging.info(f"Page {page_num+1} extracted text length: {len(page_text) if page_text else 0}")
                    if page_text:
                        extracted_text += page_text + "\n\n"
            
            # Check if PDF might contain handwriting or has low text content
            words_per_page = len(extracted_text.split()) / max(1, len(pdf_reader.pages))
            might_be_handwritten = words_per_page < 20
            
            logging.info(f"PDF has {len(pdf_reader.pages)} pages with {words_per_page:.1f} words per page")
            logging.info(f"Total extracted text length: {len(extracted_text)}")
            
            # For debugging
            if not extracted_text:
                logging.info("No text extracted from PDF - might be scanned images or handwriting")
            
            processed_text = None
            ocr_text = ""
            
            # If little or no text was extracted, try using OCR via direct image processing
            if self.llm_service and (not extracted_text or might_be_handwritten):
                try:
                    logging.info("Attempting to convert PDF to images for OCR/LLM processing")
                    
                    # First try with pdf2image if available
                    try:
                        import pdf2image
                        from pdf2image import convert_from_path
                        import tempfile
                        
                        # Initialize variables
                        temp_dir = None
                        page_images = []
                        
                        try:
                            images = convert_from_path(file_path)
                            images_extracted = True
                        except Exception as poppler_err:
                            # Handle Poppler errors - usually means Poppler is not installed
                            if "poppler" in str(poppler_err).lower():
                                logging.warning(f"Poppler not properly configured: {poppler_err}")
                                logging.warning("Will try alternative approach using PyMuPDF if available")
                                
                                # Try PyMuPDF as fallback
                                try:
                                    import fitz  # PyMuPDF
                                    doc = fitz.open(file_path)
                                    
                                    # Create a temporary directory for saving images
                                    temp_dir = tempfile.mkdtemp()
                                    page_images = []
                                    
                                    for i, page in enumerate(doc):
                                        # Render page to an image (PNG)
                                        pix = page.get_pixmap(dpi=300)  # Higher DPI for better quality
                                        image_path = os.path.join(temp_dir, f'page_{i+1}.png')
                                        pix.save(image_path)
                                        page_images.append(image_path)
                                        temp_images.append(image_path)
                                    
                                    images_extracted = True
                                    logging.info(f"Successfully extracted {len(page_images)} page images from PDF using PyMuPDF")
                                except ImportError:
                                    logging.warning("PyMuPDF not available")
                                    # No fallback options left
                                    raise
                            else:
                                # Some other error with pdf2image
                                raise
                        
                        # If we have pdf2image results, convert to images
                        if not images_extracted and 'images' in locals():
                            # Create a temporary directory for saving images
                            temp_dir = tempfile.mkdtemp()
                            
                            # Save pages as images
                            page_images = []
                            for i, image in enumerate(images):
                                image_path = os.path.join(temp_dir, f'page_{i+1}.png')
                                image.save(image_path, 'PNG')
                                page_images.append(image_path)
                                temp_images.append(image_path)
                            
                            images_extracted = True
                            logging.info(f"Successfully extracted {len(page_images)} page images from PDF")
                        
                        # Now process images with OCR and/or LLM
                        combined_text = ""
                        for i, img_path in enumerate(page_images):
                            logging.info(f"Processing page {i+1} image with LLM service")
                            
                            # First try using OCR
                            try:
                                ocr_result = pytesseract.image_to_string(Image.open(img_path))
                                if ocr_result and len(ocr_result) > 50:  # Only use OCR if it extracted meaningful text
                                    combined_text += f"Page {i+1}:\n{ocr_result}\n\n"
                                    ocr_text += ocr_result + "\n\n"
                                    logging.info(f"OCR extracted {len(ocr_result)} characters from page {i+1}")
                            except Exception as ocr_err:
                                logging.warning(f"OCR failed for page {i+1}: {ocr_err}")
                            
                            # Always use Claude's vision capabilities for better analysis
                            try:
                                logging.info(f"Using Claude to analyze page {i+1} image")
                                prompt = f"This is page {i+1} of a PDF document named '{os.path.basename(file_path)}'. Please extract ALL text visible in this image with perfect accuracy. Preserve the exact formatting, layout, and structure. If there are any tables, forms, or special formatting, maintain it as much as possible. Also identify any tasks, dates, or important information present."
                                
                                # Call the analyze_image method
                                image_analysis = self.llm_service.analyze_image(img_path, prompt)
                                
                                if image_analysis:
                                    logging.info(f"Claude extracted content from page {i+1} image")
                                    if not combined_text:
                                        combined_text = f"Page {i+1} (analyzed by Claude):\n{image_analysis}\n\n"
                                    else:
                                        combined_text += f"Page {i+1} (analyzed by Claude):\n{image_analysis}\n\n"
                            except Exception as img_err:
                                logging.error(f"Error using Claude to analyze image: {img_err}")
                        
                        if combined_text:
                            extracted_text = combined_text
                            logging.info(f"Successfully extracted {len(extracted_text)} characters from images")
                            
                    except ImportError:
                        logging.warning("pdf2image not available, skipping image-based OCR")
                        
                except Exception as img_err:
                    logging.error(f"Error during image extraction/OCR: {img_err}")
            
            # Use LLM to help with processing
            if self.llm_service:
                try:
                    if not extracted_text and not ocr_text:
                        logging.info(f"PDF has no extractable text, using LLM to analyze file metadata")
                        # Prompt LLM with description for better context
                        prompt = f"This PDF file '{os.path.basename(file_path)}' appears to be image-based or contain handwritten content that couldn't be extracted by standard PDF text extraction. The file appears to be from {os.path.basename(file_path).split('.')[0]}. Please describe what this file is likely to contain based on its filename."
                        
                        processed_text = self.llm_service.summarize_content(prompt, title=os.path.basename(file_path))
                        logging.info(f"LLM summary generated: {processed_text[:100]}...")
                    else:
                        # Normal PDF processing with LLM
                        logging.info(f"Using LLM to process PDF content")
                        
                        # Combine OCR and PyPDF2 text if both exist
                        if ocr_text and extracted_text and "Page" in extracted_text:
                            full_text = extracted_text  # Prefer Claude's extracted text if it's page-structured
                        elif ocr_text and extracted_text:
                            full_text = f"Text extracted directly from PDF:\n{extracted_text}\n\nText extracted via OCR:\n{ocr_text}"
                        else:
                            full_text = extracted_text or ocr_text
                        
                        # Create two separate prompts: one for extraction and one for summarization
                        extraction_prompt = f"Here is the content extracted from the PDF file '{os.path.basename(file_path)}'. Please format this content clearly and readably, preserving the key information:\n\n{full_text}"
                        
                        # First get a clean extraction
                        raw_extraction = self.llm_service.clean_extraction(extraction_prompt)
                        if raw_extraction:
                            # Store the clean extraction as raw text
                            raw_text = raw_extraction
                            logging.info(f"LLM extraction generated: {raw_extraction[:100]}...")
                        
                            # Now generate a summary as processed text
                            processed_text = self.llm_service.summarize_content(raw_extraction, title=os.path.basename(file_path))
                            logging.info(f"LLM summary generated: {processed_text[:100]}...")
                        else:
                            # Fallback to standard summarization 
                            processed_text = self.llm_service.summarize_content(full_text, title=os.path.basename(file_path))
                            logging.info(f"LLM summary generated: {processed_text[:100]}...")
                    
                    # Extract tasks using LLM
                    task_source = extracted_text or ocr_text or processed_text
                    tasks = self.llm_service.extract_tasks(task_source)
                    logging.info(f"Extracted tasks: {tasks}")
                    
                    # Extract tags using LLM
                    tags = self.llm_service.extract_tags(task_source)
                    logging.info(f"Extracted tags: {tags}")
                except Exception as llm_error:
                    logging.error(f"Error in LLM processing: {llm_error}")
                    processed_text = f"LLM processing failed: {str(llm_error)}. PDF contains {'text content' if extracted_text else 'no extractable text and may be image-based'}"
                    tasks = []
                    tags = ["pdf", "scan"]
            else:
                # Fallback to basic extraction
                logging.info("No LLM service available, using basic extraction")
                tasks = self._extract_tasks(extracted_text)
                tags = self._extract_tags(extracted_text)
                if not tags and not extracted_text:
                    tags = ["pdf", "scan"]
            
            # Clean up temporary files
            for img_path in temp_images:
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                except Exception as cleanup_err:
                    logging.warning(f"Error cleaning up temporary file {img_path}: {cleanup_err}")
            
            logging.info(f"PDF processing complete: extracted text = {bool(extracted_text)}, OCR text = {bool(ocr_text)}, processed text = {bool(processed_text)}")
            
            # By this point raw_text may have been set in the LLM processing section
            # Only set it if it hasn't been set already
            if 'raw_text' not in locals():
                raw_text = extracted_text
                if not raw_text and ocr_text:
                    raw_text = f"Text extracted via OCR:\n{ocr_text}"
                if not raw_text:
                    raw_text = "No text could be extracted - may be image-based PDF"
            
            return {
                'raw_text': raw_text,
                'processed_text': processed_text,
                'tags': tags,
                'tasks': tasks,
                'metadata': {
                    'pages': len(pdf_reader.pages),
                    'might_be_handwritten': might_be_handwritten,
                    'words_per_page': words_per_page,
                    'ocr_attempted': images_extracted,
                    'ocr_success': bool(ocr_text),
                    'filename': os.path.basename(file_path)
                }
            }
        except Exception as e:
            logging.error(f"Error processing PDF {file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Return a minimal response instead of None
            return {
                'raw_text': f"Error processing PDF: {str(e)}",
                'processed_text': f"This PDF could not be processed due to an error: {str(e)}",
                'tags': ["error", "pdf"],
                'tasks': [],
                'metadata': {
                    'error': str(e),
                    'filename': os.path.basename(file_path)
                }
            }


class DocumentProcessor(BaseProcessor):
    """Process text document files."""
    
    def process(self, file_path):
        """Extract text from document."""
        try:
            # Simple text extraction for now
            with open(file_path, 'r', encoding='utf-8') as file:
                extracted_text = file.read()
            
            # Process with LLM
            processed_text = None
            if self.llm_service:
                # This would be implemented when we add the LLM service
                pass
            
            # Extract tags and tasks
            tags = self._extract_tags(extracted_text)
            tasks = self._extract_tasks(extracted_text)
            
            return {
                'raw_text': extracted_text,
                'processed_text': processed_text,
                'tags': tags,
                'tasks': tasks
            }
        except Exception as e:
            logging.error(f"Error processing document {file_path}: {e}")
            return None


class WebClipProcessor(BaseProcessor):
    """Process HTML web clips."""
    
    def process(self, file_path):
        """Process HTML content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            
            # Get text
            extracted_text = soup.get_text()
            
            # Clean whitespace
            lines = (line.strip() for line in extracted_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            extracted_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Process with LLM
            processed_text = None
            if self.llm_service:
                # This would be implemented when we add the LLM service
                pass
            
            # Extract metadata if available
            metadata = {}
            
            # Try to get title
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.string
            
            # Try to get source URL
            link_tags = soup.find_all('link', rel='canonical')
            if link_tags and len(link_tags) > 0:
                metadata['source_url'] = link_tags[0].get('href')
            
            # Extract tags and tasks
            tags = self._extract_tags(extracted_text)
            tasks = self._extract_tasks(extracted_text)
            
            return {
                'raw_text': extracted_text,
                'processed_text': processed_text,
                'tags': tags,
                'tasks': tasks,
                'metadata': metadata
            }
        except Exception as e:
            logging.error(f"Error processing web clip {file_path}: {e}")
            return None


class URLProcessor(BaseProcessor):
    """Process URL files."""
    
    def process(self, file_path):
        """Extract URL and fetch content."""
        try:
            # Extract URL from file
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
            
            # Check for common URL file formats
            url = None
            
            # Windows .url format
            if file_path.endswith('.url'):
                match = re.search(r'URL=(.+)', file_content)
                if match:
                    url = match.group(1)
            
            # macOS .webloc format (could be XML or binary plist)
            elif file_path.endswith('.webloc'):
                if '<?xml' in file_content:
                    # XML format
                    soup = BeautifulSoup(file_content, 'xml')
                    string_tag = soup.find('string')
                    if string_tag:
                        url = string_tag.text
                else:
                    # Might be plain text
                    url = file_content.strip()
            
            # Plain text URL
            else:
                url = file_content.strip()
            
            if not url:
                logging.error(f"Could not extract URL from {file_path}")
                return None
            
            # Fetch the webpage content
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            
            # Get text
            extracted_text = soup.get_text()
            
            # Clean whitespace
            lines = (line.strip() for line in extracted_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            extracted_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Get metadata
            metadata = {
                'url': url,
                'title': soup.title.string if soup.title else None,
                'fetch_date': response.headers.get('Date')
            }
            
            # Process with LLM
            processed_text = None
            if self.llm_service:
                # This would be implemented when we add the LLM service
                pass
            
            # Extract tags and tasks (from original file, not the fetched content)
            with open(file_path, 'r', encoding='utf-8') as file:
                original_content = file.read()
                
            tags = self._extract_tags(original_content)
            tasks = self._extract_tasks(original_content)
            
            return {
                'raw_text': extracted_text,
                'processed_text': processed_text,
                'tags': tags,
                'tasks': tasks,
                'metadata': metadata
            }
        except Exception as e:
            logging.error(f"Error processing URL {file_path}: {e}")
            return None


class AIChatProcessor(BaseProcessor):
    """Process AI chat logs."""
    
    def process(self, file_path):
        """Process AI chat log."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                chat_content = file.read()
            
            # Try to parse as JSON
            try:
                chat_data = json.loads(chat_content)
                
                # Extract text from chat messages
                extracted_text = ""
                
                # Handle different possible JSON structures
                if isinstance(chat_data, list):
                    # List of messages
                    for msg in chat_data:
                        if isinstance(msg, dict):
                            role = msg.get('role', '')
                            content = msg.get('content', '')
                            extracted_text += f"{role}: {content}\n\n"
                elif isinstance(chat_data, dict):
                    # Nested structure
                    messages = chat_data.get('messages', [])
                    if messages:
                        for msg in messages:
                            if isinstance(msg, dict):
                                role = msg.get('role', '')
                                content = msg.get('content', '')
                                extracted_text += f"{role}: {content}\n\n"
            except json.JSONDecodeError:
                # Not JSON, try simple text parsing
                extracted_text = chat_content
            
            # Process with LLM
            processed_text = None
            if self.llm_service:
                # This would be implemented when we add the LLM service
                pass
            
            # Extract tags and tasks
            tags = self._extract_tags(extracted_text)
            tasks = self._extract_tasks(extracted_text)
            
            return {
                'raw_text': extracted_text,
                'processed_text': processed_text,
                'tags': tags,
                'tasks': tasks
            }
        except Exception as e:
            logging.error(f"Error processing AI chat {file_path}: {e}")
            return None


class ProcessorFactory:
    """Factory for creating file processors."""
    
    def __init__(self, db_manager=None, llm_service=None):
        self.db_manager = db_manager
        self.llm_service = llm_service
    
    def get_processor(self, file_type):
        """Get the appropriate processor for a file type."""
        processors = {
            'image': ImageProcessor(self.db_manager, self.llm_service),
            'pdf': PDFProcessor(self.db_manager, self.llm_service),
            'document': DocumentProcessor(self.db_manager, self.llm_service),
            'web_clip': WebClipProcessor(self.db_manager, self.llm_service),
            'url': URLProcessor(self.db_manager, self.llm_service),
            'ai_chat': AIChatProcessor(self.db_manager, self.llm_service)
        }
        
        return processors.get(file_type, BaseProcessor(self.db_manager, self.llm_service))

# Example usage
if __name__ == "__main__":
    # Test processors
    factory = ProcessorFactory()
    
    # Test document processor
    doc_processor = factory.get_processor('document')
    result = doc_processor.process('test_files/sample_note.txt')
    if result:
        print(f"Document Processing Result: {result}")
    
    # Test image processor (requires Tesseract OCR to be installed)
    img_processor = factory.get_processor('image')
    result = img_processor.process('test_files/sample_image.jpg')
    if result:
        print(f"Image Processing Result: {result}")
