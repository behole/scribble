#!/usr/bin/env python
"""
PDF Processor Test Script

This script tests the enhanced PDF processing capabilities of the Notes Digest application,
using either OCR or Claude's vision capabilities to extract text from PDF files.

Usage:
  python process_pdf.py <pdf_file_path> [--api-key=<key>]

Options:
  --api-key=<key>     Anthropic API key to use for Claude processing
"""

import os
import sys
import logging
import argparse
from main_application import NotesDigestApp

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def analyze_pdf_with_images(pdf_path, api_key):
    """Analyze a PDF file by extracting and analyzing images of each page."""
    # Import necessary modules
    import base64
    import requests
    import json
    import os
    import tempfile
    
    if not api_key:
        logger.error("API key required for direct PDF analysis")
        return None
    
    try:
        # First convert PDF to images
        logger.info("Converting PDF to images for analysis...")
        
        try:
            # Try with PyMuPDF first
            import fitz  # PyMuPDF
            
            # Create a temporary directory for saving images
            temp_dir = tempfile.mkdtemp()
            page_images = []
            
            # Open the PDF
            doc = fitz.open(pdf_path)
            
            # Extract each page as an image
            for i, page in enumerate(doc):
                # Render page to an image (PNG)
                pix = page.get_pixmap(dpi=300)  # Higher DPI for better quality
                image_path = os.path.join(temp_dir, f'page_{i+1}.png')
                pix.save(image_path)
                page_images.append(image_path)
                
            logger.info(f"Successfully extracted {len(page_images)} page images from PDF")
        except ImportError:
            # Fall back to pdf2image
            try:
                from pdf2image import convert_from_path
                
                # Create a temporary directory for saving images
                temp_dir = tempfile.mkdtemp()
                
                # Convert PDF to images
                images = convert_from_path(pdf_path, dpi=300)
                
                # Save pages as images
                page_images = []
                for i, image in enumerate(images):
                    image_path = os.path.join(temp_dir, f'page_{i+1}.png')
                    image.save(image_path, 'PNG')
                    page_images.append(image_path)
                    
                logger.info(f"Successfully extracted {len(page_images)} page images from PDF")
            except Exception as pdf2image_err:
                logger.error(f"Error extracting PDF pages with pdf2image: {pdf2image_err}")
                return None
        
        # Now analyze each page with Claude
        all_content = ""
        
        for i, img_path in enumerate(page_images):
            with open(img_path, 'rb') as img_file:
                img_bytes = img_file.read()
                
            # Encode the image as base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # Determine MIME type based on file extension
            mime_type = "image/png"  # Default
            if img_path.lower().endswith('.jpg') or img_path.lower().endswith('.jpeg'):
                mime_type = "image/jpeg"
                
            # Create the message with the image
            message = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": img_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": f"This is page {i+1} of a PDF named '{os.path.basename(pdf_path)}'. Please extract all text content, describe the content, and identify any tasks, action items, or important dates mentioned."
                    }
                ]
            }
            
            # Create request data
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": "claude-3-7-sonnet-20250219",
                "messages": [message],
                "max_tokens": 4000,
                "temperature": 0.2,  # Lower temperature for more accurate transcription
                "system": "You are a document analysis assistant that can extract information from images. Your task is to extract all text visible in the image, preserve formatting when possible, identify any tasks or action items, and describe any non-text content."
            }
            
            # Make the API request
            try:
                logger.info(f"Making API request to analyze image of page {i+1}")
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=data,
                    timeout=90
                )
                
                # Check if the request was successful
                response.raise_for_status()
                
                # Parse the response
                result = response.json()
                
                if "content" in result and isinstance(result["content"], list) and len(result["content"]) > 0:
                    content = result["content"][0]["text"]
                    logger.info(f"Successfully analyzed page {i+1}")
                    
                    # Add to the combined content
                    all_content += f"\n\n## Page {i+1}\n\n{content}"
                else:
                    logger.error(f"Unexpected response format for page {i+1}: {result}")
            except Exception as e:
                logger.error(f"Error analyzing page {i+1}: {e}")
        
        # If we have content, extract tasks and tags
        if all_content:
            from llm_service import LLMService
            llm = LLMService(api_key=api_key)
            
            # Extract tasks and tags
            tasks = llm.extract_tasks(all_content)
            tags = llm.extract_tags(all_content)
            
            # Generate a summary
            summary_prompt = f"This is a summary of the PDF '{os.path.basename(pdf_path)}'. Please create a concise summary of the document based on all the extracted text:"
            
            system_message = {
                "role": "system",
                "content": "You are an expert at summarizing documents. Create a concise summary that captures the key information, structure, and any important points from the document."
            }
            
            user_message = {
                "role": "user",
                "content": all_content + "\n\n" + summary_prompt
            }
            
            summary = llm._call_api([system_message, user_message])
            
            # Compile results
            return {
                'raw_text': all_content,
                'processed_text': summary if summary else all_content,
                'tasks': tasks,
                'tags': tags,
                'metadata': {
                    'analysis_method': 'claude_image_analysis',
                    'pages_analyzed': len(page_images),
                    'filename': os.path.basename(pdf_path)
                }
            }
        else:
            logger.error("Failed to extract content from any page")
            return None
            
    except Exception as e:
        logger.error(f"Error in PDF image analysis: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def analyze_pdf_directly(pdf_path, api_key):
    """Legacy function kept for compatibility - now just calls analyze_pdf_with_images."""
    return analyze_pdf_with_images(pdf_path, api_key)

def process_pdf(pdf_path, api_key=None):
    """Process a PDF file and display the results."""
    # Read config to get API key if not provided
    if not api_key:
        try:
            import json
            with open("config.json", 'r') as f:
                config = json.load(f)
                api_key = config.get("api_key")
        except:
            pass
    
    # Initialize the app
    app = NotesDigestApp()
    
    # Override API key if provided
    if api_key:
        app.llm_service.api_key = api_key
        app.config["api_key"] = api_key
    
    logger.info(f"Processing PDF file: {pdf_path}")
    
    # First try direct multimodal approach
    result = None
    if api_key:
        try:
            logger.info("Attempting direct multimodal PDF analysis...")
            result = analyze_pdf_directly(pdf_path, api_key)
            if result:
                logger.info("Direct multimodal PDF analysis successful!")
        except Exception as e:
            logger.error(f"Error in direct multimodal PDF analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
    # If direct approach failed, fallback to standard approach
    if not result:
        logger.info("Falling back to standard PDF processing...")
        result = app.process_pdf_with_claude(pdf_path)
    
    if result:
        logger.info("PDF processing successful!")
        
        # Display results
        print("\n" + "="*50)
        print(f"RESULTS FOR: {os.path.basename(pdf_path)}")
        print("="*50)
        
        # Raw text (truncated)
        raw_text = result.get('raw_text', '')
        print(f"\nEXTRACTED TEXT (first 500 chars):\n{raw_text[:500]}...")
        
        # Processed text
        processed_text = result.get('processed_text', '')
        if processed_text:
            print(f"\nPROCESSED TEXT:\n{processed_text}")
        
        # Tasks
        tasks = result.get('tasks', [])
        if tasks:
            print("\nEXTRACTED TASKS:")
            for i, task in enumerate(tasks, 1):
                print(f"  {i}. {task}")
        else:
            print("\nNo tasks were extracted.")
        
        # Tags
        tags = result.get('tags', [])
        if tags:
            print("\nEXTRACTED TAGS:")
            print(f"  {', '.join(tags)}")
        else:
            print("\nNo tags were extracted.")
        
        # Metadata
        metadata = result.get('metadata', {})
        if metadata:
            print("\nMETADATA:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
        
        print("\n" + "="*50)
        return True
    else:
        logger.error("PDF processing failed!")
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Process a PDF file with enhanced capabilities.')
    parser.add_argument('pdf_path', help='Path to the PDF file to process')
    parser.add_argument('--api-key', help='Anthropic API key for Claude processing')
    
    args = parser.parse_args()
    
    # Validate PDF path
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        return 1
    
    # Process the PDF
    success = process_pdf(args.pdf_path, args.api_key)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())