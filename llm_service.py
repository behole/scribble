import os
import logging
import json
import requests
import re
from datetime import datetime
import time

class LLMService:
    """Service for interacting with LLM APIs."""
    
    def __init__(self, api_key=None, model="claude-3-7-sonnet-20250219"):
        """Initialize the LLM service."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            logging.warning("No API key found. LLM service will not function.")
        
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def _call_api(self, messages, max_tokens=4000, temperature=0.7):
        """Make an API call to the LLM service."""
        if not self.api_key:
            logging.error("API key not set. Cannot make API call.")
            return None
        
        # Anthropic API requires anthhropic-beta or anthropic-version header
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        # Format the request based on the messages
        # Anthropic expects system message as a separate parameter
        system_message = None
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)
        
        # Create request data
        data = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # Add system message if exists
        if system_message:
            data["system"] = system_message
        
        logging.info(f"Calling LLM API with model: {self.model}")
        
        retries = 0
        while retries < self.max_retries:
            try:
                logging.info(f"Making API request to {self.base_url}")
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=90  # Increased timeout for processing larger documents
                )
                
                # Log rate limit headers if present
                if 'X-RateLimit-Remaining' in response.headers:
                    logging.info(f"Rate limit remaining: {response.headers.get('X-RateLimit-Remaining')}")
                    
                if not response.ok:
                    logging.error(f"API call failed: {response.status_code} {response.text}")
                    
                response.raise_for_status()
                
                # Parse response
                result = response.json()
                logging.info("API call successful")
                
                # Get text from response content
                if "content" in result and isinstance(result["content"], list) and len(result["content"]) > 0:
                    return result["content"][0]["text"]
                else:
                    logging.error(f"Unexpected response format: {result}")
                    return None
            
            except requests.exceptions.RequestException as e:
                logging.error(f"API call failed: {str(e)}")
                retries += 1
                
                if retries < self.max_retries:
                    # Exponential backoff
                    sleep_time = self.retry_delay * (2 ** (retries - 1))
                    logging.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logging.error("Max retries reached. Giving up.")
                    return None
                    
    def _call_api_with_image(self, image_path, prompt, max_tokens=4000, temperature=0.7):
        """Make an API call to the LLM service with an image."""
        if not self.api_key:
            logging.error("API key not set. Cannot make API call.")
            return None
        
        # Anthropic API requires anthhropic-beta for multimodal
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        # Read the image as base64
        try:
            import base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logging.error(f"Error reading image file: {e}")
            return None
        
        # Create the message with the image
        message = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",  # Adjust based on the image type
                        "data": base64_image
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
        
        # Create system message
        system_prompt = "You are an expert document analyzer with perfect OCR capabilities. Your task is to extract ALL text from the image with 100% accuracy, preserving the exact formatting and layout. For documents, focus exclusively on the text content rather than describing what you see. Your goal is to recreate the document text exactly as if it were digitally extracted, not to describe the image."
        
        # Create request data
        data = {
            "model": self.model,
            "messages": [message],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt
        }
        
        logging.info(f"Calling LLM API with image: {image_path}")
        
        retries = 0
        while retries < self.max_retries:
            try:
                logging.info(f"Making API request to {self.base_url}")
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=90  # Increased timeout for processing images
                )
                
                # Log rate limit headers if present
                if 'X-RateLimit-Remaining' in response.headers:
                    logging.info(f"Rate limit remaining: {response.headers.get('X-RateLimit-Remaining')}")
                    
                if not response.ok:
                    logging.error(f"API call failed: {response.status_code} {response.text}")
                    
                response.raise_for_status()
                
                # Parse response
                result = response.json()
                logging.info("API call successful")
                
                # Get text from response content
                if "content" in result and isinstance(result["content"], list) and len(result["content"]) > 0:
                    return result["content"][0]["text"]
                else:
                    logging.error(f"Unexpected response format: {result}")
                    return None
            
            except requests.exceptions.RequestException as e:
                logging.error(f"API call failed: {str(e)}")
                retries += 1
                
                if retries < self.max_retries:
                    # Exponential backoff
                    sleep_time = self.retry_delay * (2 ** (retries - 1))
                    logging.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logging.error("Max retries reached. Giving up.")
                    return None
    
    def analyze_image(self, image_path, prompt=None):
        """Analyze an image and extract text and content."""
        if not image_path or not os.path.exists(image_path):
            logging.error(f"Image file not found: {image_path}")
            return None
        
        # Default prompt if none provided
        if not prompt:
            prompt = "Please analyze this image. Extract any visible text, describe the content, and identify any action items or tasks that might be present."
        
        try:
            # Use multimodal API call
            return self._call_api_with_image(image_path, prompt)
        except Exception as e:
            logging.error(f"Error analyzing image: {e}")
            return None
    
    def transcribe_handwritten(self, text):
        """Transcribe potentially handwritten text."""
        if not text:
            return None
        
        system_message = {
            "role": "system",
            "content": "You are an expert transcriber. Your task is to clean up and correct the text that was extracted from a handwritten note or an image using OCR. Fix any obvious OCR errors, complete partial words if their meaning is clear, and format the text properly. Do not add information that isn't present in the original."
        }
        
        user_message = {
            "role": "user",
            "content": f"Please transcribe and clean up the following text that was extracted from a handwritten note or image:\n\n{text}"
        }
        
        return self._call_api([system_message, user_message], max_tokens=len(text) * 2)
        
    def clean_extraction(self, text):
        """Clean and format extracted text from a document."""
        if not text:
            return None
        
        system_message = {
            "role": "system",
            "content": "You are an expert document processor. Your task is to extract and format text from documents that may have been processed by OCR or other text extraction methods. Clean up any errors, preserve the original formatting where possible, and ensure the output is clear and readable. Format tables, lists, and other structures properly. This is NOT a summary - provide the full extracted text in a clean format."
        }
        
        user_message = {
            "role": "user",
            "content": f"{text}"
        }
        
        return self._call_api([system_message, user_message], max_tokens=8000)
    
    def summarize_content(self, text, title=None, source=None):
        """Summarize the content."""
        if not text:
            return None
        
        # Create context based on available metadata
        context = "a document"
        if title and source:
            context = f"the document titled '{title}' from {source}"
        elif title:
            context = f"the document titled '{title}'"
        elif source:
            context = f"the document from {source}"
        
        system_message = {
            "role": "system",
            "content": "You are an expert summarizer. Your task is to create a concise but informative summary of the provided content. Focus on the key points, main arguments, and important details. The summary should be about 2-3 paragraphs."
        }
        
        user_message = {
            "role": "user",
            "content": f"Please summarize the following content from {context}:\n\n{text[:10000]}"  # Limit to first 10k chars
        }
        
        return self._call_api([system_message, user_message])
    
    def extract_tasks(self, text):
        """Extract tasks from the content."""
        if not text:
            return []
        
        system_message = {
            "role": "system",
            "content": "You are an expert assistant that helps identify action items and tasks from documents. Your job is to extract any explicit or implied tasks, to-dos, or action items from the provided text. Return the tasks as a JSON array of strings."
        }
        
        user_message = {
            "role": "user",
            "content": f"Please extract any tasks, to-dos, or action items from the following text. Return ONLY a JSON array of strings, with each string being a separate task:\n\n{text[:10000]}"  # Limit to first 10k chars
        }
        
        response = self._call_api([system_message, user_message])
        
        # Extract the JSON array from the response
        if response:
            try:
                # Look for JSON array in the response
                json_match = re.search(r'\[\s*".*"\s*\]', response, re.DOTALL)
                if json_match:
                    tasks_json = json_match.group(0)
                    return json.loads(tasks_json)
                else:
                    # Try to parse the entire response as JSON
                    return json.loads(response)
            except (json.JSONDecodeError, ValueError) as e:
                logging.error(f"Failed to parse tasks from LLM response: {e}")
                logging.debug(f"Response was: {response}")
        
        return []
    
    def extract_tags(self, text):
        """Extract relevant tags/topics from the content."""
        if not text:
            return []
        
        system_message = {
            "role": "system",
            "content": "You are an expert at categorizing and tagging content. Your task is to extract or generate relevant tags for the provided text. These tags should capture the main topics, themes, and categories of the content. Return the tags as a JSON array of strings."
        }
        
        user_message = {
            "role": "user",
            "content": f"Please identify relevant tags for the following content. Extract existing hashtags and generate additional appropriate tags. Return ONLY a JSON array of strings (without the # symbol):\n\n{text[:10000]}"  # Limit to first 10k chars
        }
        
        response = self._call_api([system_message, user_message])
        
        # Extract the JSON array from the response
        if response:
            try:
                # Look for JSON array in the response
                json_match = re.search(r'\[\s*".*"\s*\]', response, re.DOTALL)
                if json_match:
                    tags_json = json_match.group(0)
                    return json.loads(tags_json)
                else:
                    # Try to parse the entire response as JSON
                    return json.loads(response)
            except (json.JSONDecodeError, ValueError) as e:
                logging.error(f"Failed to parse tags from LLM response: {e}")
                logging.debug(f"Response was: {response}")
        
        return []
    
    def generate_weekly_digest(self, contents, start_date, end_date):
        """Generate a weekly digest from multiple pieces of content."""
        if not contents:
            return None
        
        # Format the date range
        start_str = datetime.fromisoformat(start_date).strftime("%B %d, %Y")
        end_str = datetime.fromisoformat(end_date).strftime("%B %d, %Y")
        
        # Prepare a condensed version of the contents
        content_summaries = []
        for i, content in enumerate(contents, 1):
            content_type = content.get('content_type', 'document')
            file_type = content.get('file_type', 'unknown')
            file_path = content.get('file_path', f'document-{i}')
            
            # Get filename without path
            filename = os.path.basename(file_path)
            
            # Get a brief summary (first 200 chars)
            text = content.get('content_text', '')[:200] + "..."
            
            content_summaries.append(f"Document {i}: {filename} ({file_type}/{content_type})\nExcerpt: {text}\n")
        
        all_summaries = "\n".join(content_summaries)
        
        system_message = {
            "role": "system",
            "content": f"You are an expert content analyst and summarizer. Your task is to create a comprehensive weekly digest of various documents and notes from {start_str} to {end_str}. The digest should include:\n1. A high-level summary of the week's content\n2. Key themes and topics\n3. Important tasks or action items identified\n4. Notable insights or learnings\n5. Connections between different pieces of content"
        }
        
        user_message = {
            "role": "user",
            "content": f"Please create a weekly digest for the following content collected from {start_str} to {end_str}. Format the digest with clear headings and sections:\n\n{all_summaries}"
        }
        
        return self._call_api([system_message, user_message], max_tokens=8000)
    
    def analyze_trends(self, digests, num_weeks=4):
        """Analyze trends across multiple weekly digests."""
        if not digests or len(digests) < 2:
            return None
        
        # Prepare the digests for analysis
        digest_texts = []
        for i, digest in enumerate(digests[-num_weeks:], 1):
            digest_type = digest.get('digest_type', 'weekly')
            start_date = digest.get('start_date')
            end_date = digest.get('end_date')
            
            # Format date range if available
            date_range = ""
            if start_date and end_date:
                start_str = datetime.fromisoformat(start_date).strftime("%B %d")
                end_str = datetime.fromisoformat(end_date).strftime("%B %d, %Y")
                date_range = f" ({start_str} - {end_str})"
            
            digest_texts.append(f"Digest {i}{date_range}:\n{digest.get('content', '')[:1000]}...\n")
        
        all_digests = "\n".join(digest_texts)
        
        system_message = {
            "role": "system",
            "content": "You are an expert trend analyst. Your task is to analyze multiple weekly digests and identify trends, patterns, and developments over time. Focus on recurring themes, evolving topics, and changes in priorities or interests."
        }
        
        user_message = {
            "role": "user",
            "content": f"Please analyze the following {len(digest_texts)} weekly digests and provide a trend report that identifies patterns, developments, and shifts in focus over time:\n\n{all_digests}"
        }
        
        return self._call_api([system_message, user_message], max_tokens=4000)
    
    def suggest_reading(self, recent_content, num_items=5):
        """Generate suggested reading/resources based on recent content."""
        if not recent_content:
            return None
        
        # Extract topics from recent content
        topics = []
        for content in recent_content[:10]:  # Limit to 10 most recent items
            text = content.get('processed_text') or content.get('content_text', '')
            extracted_tags = self.extract_tags(text[:5000])  # Limit to first 5000 chars
            topics.extend(extracted_tags)
        
        # Get unique topics
        unique_topics = list(set(topics))[:20]  # Limit to 20 topics
        
        system_message = {
            "role": "system",
            "content": f"You are an expert at recommending relevant resources. Based on the provided topics of interest, suggest {num_items} valuable resources. These could be books, articles, websites, courses, videos, or tools. For each suggestion, provide a brief description of why it's relevant. Format your response as a list with clear headings."
        }
        
        user_message = {
            "role": "user",
            "content": f"Based on these topics of interest: {', '.join(unique_topics)}, please suggest {num_items} resources that would be valuable for further exploration, learning, or reference. For each suggestion, include a brief explanation of its relevance."
        }
        
        return self._call_api([system_message, user_message])

# Example usage
if __name__ == "__main__":
    import re  # Make sure re is imported at the top
    
    # Initialize the LLM service
    llm_service = LLMService()
    
    # Test with a sample text
    sample_text = """Meeting Notes - Product Team - May 5, 2025
    
    Attendees: John, Sarah, Miguel, Leila
    
    Action Items:
    - Sarah will finalize the Q3 roadmap by Friday
    - Miguel to investigate the performance issue reported by customer XYZ
    - Everyone: Review the new design mockups before next meeting
    - John: Schedule user testing for the new feature
    
    Key Points Discussed:
    - User feedback on the recent release has been mostly positive
    - We need to prioritize mobile optimization for the next sprint
    - Budget approval for the new analytics tool is still pending
    
    #product #planning #roadmap #customer-feedback
    """
    
    # Test summarization
    summary = llm_service.summarize_content(sample_text, "Meeting Notes")
    print(f"Summary:\n{summary}\n")
    
    # Test task extraction
    tasks = llm_service.extract_tasks(sample_text)
    print(f"Tasks:\n{tasks}\n")
    
    # Test tag extraction
    tags = llm_service.extract_tags(sample_text)
    print(f"Tags:\n{tags}\n")
