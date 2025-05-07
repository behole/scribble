import os
import logging
import time
import re
from datetime import datetime

class EnhancedProcessor:
    """Enhances the file processing with advanced LLM capabilities."""
    
    def __init__(self, db_manager, llm_service):
        self.db_manager = db_manager
        self.llm_service = llm_service
        self.logger = logging.getLogger(__name__)
    
    def process_content(self, content_dict, content_id=None):
        """Process content using LLM for enhanced understanding."""
        if not content_dict or not self.llm_service:
            return content_dict
        
        # Extract raw text
        raw_text = content_dict.get('raw_text', '')
        if not raw_text:
            self.logger.warning("No raw text provided for LLM processing")
            return content_dict
        
        # Determine if this might be handwritten
        might_be_handwritten = content_dict.get('might_be_handwritten', False)
        
        # Limit text length to prevent API overuse
        max_text_length = 8000  # Characters
        if len(raw_text) > max_text_length:
            processed_text = raw_text[:max_text_length] + "...[truncated]"
        else:
            processed_text = raw_text
        
        enhanced_dict = content_dict.copy()
        
        try:
            # Process handwritten content with transcription
            if might_be_handwritten:
                self.logger.info("Processing potential handwritten content with transcription")
                transcribed = self.llm_service.transcribe_handwritten(processed_text)
                if transcribed:
                    enhanced_dict['processed_text'] = transcribed
                    enhanced_dict['is_transcribed'] = True
            
            # Default summary and processing for all content
            else:
                self.logger.info("Generating summary and extracting key information")
                
                # Get filename without path
                file_path = content_dict.get('file_path', '')
                filename = os.path.basename(file_path) if file_path else ''
                
                # Summarize content
                summary = self.llm_service.summarize_content(
                    processed_text, 
                    title=filename,
                    source=content_dict.get('metadata', {}).get('source', '')
                )
                
                if summary:
                    enhanced_dict['processed_text'] = summary
            
            # Extract tasks using LLM
            tasks = self.llm_service.extract_tasks(processed_text)
            if tasks:
                enhanced_dict['tasks'] = tasks
                
                # Save tasks to database if we have a content_id
                if content_id and self.db_manager:
                    for task in tasks:
                        self.db_manager.add_task(content_id, task)
            
            # Extract tags using LLM
            tags = self.llm_service.extract_tags(processed_text)
            if tags:
                # Combine with existing tags
                existing_tags = enhanced_dict.get('tags', [])
                combined_tags = list(set(existing_tags + tags))
                enhanced_dict['tags'] = combined_tags
                
                # Save tags to database if we have a content_id
                if content_id and self.db_manager:
                    self.db_manager.add_tags(content_id, combined_tags)
            
            return enhanced_dict
            
        except Exception as e:
            self.logger.error(f"Error in LLM processing: {str(e)}")
            
            # Return original if there's an error
            return content_dict
    
    def process_backlog(self, limit=None, reprocess=False):
        """Process or reprocess content in the database."""
        if not self.db_manager:
            self.logger.error("No database manager available for backlog processing")
            return False
        
        # Get content items to process
        content_items = self.db_manager.get_unprocessed_content(limit=limit) if not reprocess else \
                        self.db_manager.get_all_content(limit=limit)
        
        if not content_items:
            self.logger.info("No content items found for processing")
            return True
        
        self.logger.info(f"Processing {len(content_items)} items from backlog")
        
        processed_count = 0
        for item in content_items:
            content_id = item[0]
            file_id = item[1]
            content_type = item[2]
            raw_text = item[3]
            
            # Skip if already processed and not reprocessing
            if item[4] and not reprocess:  # item[4] is processed_text
                continue
            
            # Get file info
            file_info = self.db_manager.get_file_by_id(file_id)
            if not file_info:
                continue
            
            file_path = file_info[1]  # file_path
            file_type = file_info[2]  # file_type
            
            # Create content dict for processing
            content_dict = {
                'raw_text': raw_text,
                'content_type': content_type,
                'file_type': file_type,
                'file_path': file_path,
                'might_be_handwritten': 'image' in file_type or 'pdf' in file_type
            }
            
            # Process with LLM
            enhanced_dict = self.process_content(content_dict, content_id)
            
            # Update database with processed content
            if enhanced_dict.get('processed_text'):
                self.db_manager.update_content_processed_text(
                    content_id, 
                    enhanced_dict['processed_text']
                )
            
            processed_count += 1
            
            # Add a small delay to avoid API rate limits
            time.sleep(1)
        
        self.logger.info(f"Completed processing {processed_count} backlog items")
        return True
    
    def enhance_weekly_digest(self, digest_content, start_date, end_date):
        """Enhance a weekly digest with additional insights."""
        if not digest_content or not self.llm_service:
            return digest_content
        
        try:
            # Format date range for prompt
            start_str = datetime.fromisoformat(start_date).strftime("%B %d, %Y")
            end_str = datetime.fromisoformat(end_date).strftime("%B %d, %Y")
            
            # Create system message
            system_message = {
                "role": "system",
                "content": f"You are an expert content analyst tasked with enhancing a weekly digest of notes and documents. Your job is to review the digest content and add additional insights, connections between topics, and observations that might be valuable. Focus on making the content more useful and insightful."
            }
            
            # Create user message
            user_message = {
                "role": "user",
                "content": f"Please enhance the following weekly digest for the period {start_str} to {end_str}. Add insights, identify themes or patterns, and suggest connections between topics where appropriate:\n\n{digest_content}"
            }
            
            # Call LLM
            enhanced_content = self.llm_service._call_api([system_message, user_message])
            
            if enhanced_content:
                # Add a section header for the enhanced insights
                final_content = digest_content + "\n\n## Additional Insights\n\n" + enhanced_content
                return final_content
        
        except Exception as e:
            self.logger.error(f"Error enhancing weekly digest: {str(e)}")
        
        # Return original if there's an error
        return digest_content
    
    def analyze_content_trends(self, content_items, period="last_month"):
        """Analyze content trends across multiple items."""
        if not content_items or not self.llm_service:
            return None
        
        # Prepare metadata about the content
        content_summary = []
        for i, item in enumerate(content_items[:20]):  # Limit to 20 items
            # Extract basic information
            content_type = item.get('content_type', 'unknown')
            file_type = item.get('file_type', 'unknown')
            date_processed = item.get('date_processed', '')
            
            # Format date if available
            date_str = ""
            if date_processed:
                try:
                    date_obj = datetime.fromisoformat(date_processed)
                    date_str = date_obj.strftime("%B %d, %Y")
                except ValueError:
                    date_str = date_processed
            
            # Get a brief excerpt (first 100 chars)
            text = item.get('processed_text') or item.get('content_text', '')
            excerpt = text[:100] + "..." if len(text) > 100 else text
            
            # Add to summary
            content_summary.append(f"Item {i+1} ({content_type}/{file_type}, {date_str}): {excerpt}")
        
        # Determine period description
        period_desc = "the last month"
        if period == "last_week":
            period_desc = "the last week"
        elif period == "last_year":
            period_desc = "the last year"
        
        # Create system message
        system_message = {
            "role": "system",
            "content": f"You are an expert trend analyst specializing in finding patterns and insights across content. Your task is to analyze multiple content items from {period_desc} and identify key trends, recurring themes, shifts in focus, and other notable patterns."
        }
        
        # Create user message
        user_message = {
            "role": "user",
            "content": f"Please analyze the following content items from {period_desc} and provide a trend analysis report identifying patterns, developments, and emerging topics:\n\n" + "\n\n".join(content_summary)
        }
        
        try:
            # Call LLM
            trend_analysis = self.llm_service._call_api([system_message, user_message])
            
            if trend_analysis:
                return trend_analysis
        
        except Exception as e:
            self.logger.error(f"Error analyzing content trends: {str(e)}")
        
        return None
    
    def generate_content_connections(self, content_items):
        """Generate connections between different content items."""
        if not content_items or len(content_items) < 2 or not self.llm_service:
            return None
        
        # Prepare content summaries
        content_summaries = []
        for i, item in enumerate(content_items[:10]):  # Limit to 10 items
            # Get filename without path
            file_path = item.get('file_path', '')
            filename = os.path.basename(file_path) if file_path else f"Document {i+1}"
            
            # Get processed text or raw text
            text = item.get('processed_text') or item.get('content_text', '')
            
            # Get tags
            tags = item.get('tags', [])
            tags_str = f"Tags: {', '.join(['#' + tag for tag in tags])}" if tags else "No tags"
            
            # Create summary
            summary = f"Document: {filename}\n{tags_str}\nContent: {text[:200]}..."
            content_summaries.append(summary)
        
        # Create system message
        system_message = {
            "role": "system",
            "content": "You are an expert at finding connections and relationships between different pieces of content. Your task is to analyze multiple documents and identify meaningful connections, related concepts, and how they might complement or build upon each other."
        }
        
        # Create user message
        user_message = {
            "role": "user",
            "content": "Please analyze the following documents and identify meaningful connections between them. Focus on thematic links, complementary information, conceptual relationships, and how the content might be related:\n\n" + "\n\n---\n\n".join(content_summaries)
        }
        
        try:
            # Call LLM
            connections = self.llm_service._call_api([system_message, user_message])
            
            if connections:
                return connections
        
        except Exception as e:
            self.logger.error(f"Error generating content connections: {str(e)}")
        
        return None

# Example usage
if __name__ == "__main__":
    from database_manager import DatabaseManager
    from llm_service import LLMService
    
    # Initialize the services
    db_manager = DatabaseManager("test_notes.db")
    llm_service = LLMService()
    
    # Initialize the enhanced processor
    enhanced_processor = EnhancedProcessor(db_manager, llm_service)
    
    # Test processing content
    content_dict = {
        'raw_text': "Meeting Notes: April 5, 2025\n\nAttendees: John, Sarah, Michael\n\nTODO: Complete the project proposal by Friday\nTODO: Schedule follow-up meeting next week\n\nKey points discussed:\n- Budget constraints for Q2\n- New marketing strategy\n- Hiring plans\n\n#project #meeting #planning",
        'file_path': 'meeting_notes.txt',
        'file_type': 'document',
        'content_type': 'text'
    }
    
    enhanced_content = enhanced_processor.process_content(content_dict)
    
    print("Enhanced Content:")
    for key, value in enhanced_content.items():
        print(f"{key}: {value}")
