import os
import logging
import argparse
import time
import json
import schedule
from datetime import datetime, timedelta

from folder_monitor import NotesWatcher, NotesProcessor
from database_manager import DatabaseManager
from llm_service import LLMService
from file_processors import ProcessorFactory
from digest_generator import DigestGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('notes_digest.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class NotesDigestApp:
    """Main application for the Notes Digest system."""
    
    def __init__(self, config_path="config.json"):
        """Initialize the application with configuration."""
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config.get("db_path", "notes_digest.db"))
        self.llm_service = LLMService(self.config.get("api_key"))
        
        # Initialize processor
        self.processor = self._create_processor()
        
        # Initialize digest generator
        self.digest_generator = DigestGenerator(self.db_manager, self.llm_service)
        
        # Initialize folder watcher
        self.watcher = None
    
    def _load_config(self, config_path):
        """Load configuration from a JSON file."""
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return self._create_default_config(config_path)
        else:
            return self._create_default_config(config_path)
    
    def _create_default_config(self, config_path):
        """Create a default configuration file."""
        default_config = {
            "notes_folder": "./notes_folder",
            "db_path": "notes_digest.db",
            "api_key": "",
            "weekly_digest_day": "Sunday",
            "monthly_digest_day": 1,
            "output_dir": "digests",
            "schedule": {
                "weekly_digest": True,
                "monthly_digest": True,
                "task_list": True,
                "suggested_reading": True
            }
        }
        
        try:
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            
            logger.info(f"Default configuration created at {config_path}")
        except Exception as e:
            logger.error(f"Error creating default config: {e}")
        
        return default_config
    
    def _create_processor(self):
        """Create and configure the notes processor."""
        processor = NotesProcessor(self.db_manager, self.llm_service)
        processor.processor_factory = ProcessorFactory(self.db_manager, self.llm_service)
        return processor
    
    def _setup_scheduled_tasks(self):
        """Set up scheduled tasks based on configuration."""
        schedule_config = self.config.get("schedule", {})
        
        # Weekly digest
        if schedule_config.get("weekly_digest", True):
            weekly_day = self.config.get("weekly_digest_day", "Sunday")
            schedule.every().sunday.do(self.generate_weekly_digest)
            logger.info(f"Scheduled weekly digest for every {weekly_day}")
        
        # Monthly digest
        if schedule_config.get("monthly_digest", True):
            monthly_day = self.config.get("monthly_digest_day", 1)
            
            # Schedule for the first day of each month
            if monthly_day == 1:
                # Use a different approach for monthly scheduling
                schedule.every(1).days.at("00:00").do(
                    lambda: self.generate_monthly_digest() if datetime.now().day == 1 else None
                )
                logger.info("Scheduled monthly digest for the 1st of each month")
        
        # Daily task list
        if schedule_config.get("task_list", True):
            schedule.every().day.at("08:00").do(self.generate_task_list)
            logger.info("Scheduled daily task list generation")
        
        # Weekly suggested reading
        if schedule_config.get("suggested_reading", True):
            schedule.every().friday.do(self.generate_suggested_reading)
            logger.info("Scheduled weekly suggested reading for Fridays")
    
    def start(self):
        """Start the application."""
        logger.info("Starting Notes Digest application")
        
        # Create notes folder if it doesn't exist
        notes_folder = self.config.get("notes_folder", "./notes_folder")
        if not os.path.exists(notes_folder):
            os.makedirs(notes_folder)
            logger.info(f"Created notes folder: {notes_folder}")
        
        # Set up scheduled tasks
        self._setup_scheduled_tasks()
        
        # Initialize and start the folder watcher
        self.watcher = NotesWatcher(notes_folder, self.processor)
        
        # Start the watcher in a separate thread
        import threading
        watcher_thread = threading.Thread(target=self.watcher.start, daemon=True)
        watcher_thread.start()
        
        logger.info(f"Started monitoring folder: {notes_folder}")
        
        try:
            while True:
                # Run scheduled tasks
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
            self.stop()
    
    def stop(self):
        """Stop the application."""
        if self.watcher:
            self.watcher.stop()
        
        logger.info("Notes Digest application stopped")
    
    def process_file(self, file_path):
        """Process a specific file."""
        logger.info(f"Processing file: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        # Determine file type
        from folder_monitor import NotesEventHandler
        handler = NotesEventHandler(self.processor)
        file_type = handler._determine_file_type(file_path)
        
        # Process the file
        try:
            result = self.processor.process_file(file_path, file_type)
            logger.info(f"Successfully processed file: {file_path} as {file_type}")
            return result
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return False
            
    def process_pdf_with_claude(self, pdf_path):
        """Specially process a PDF file using Claude's vision capabilities."""
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return False
            
        logger.info(f"Processing PDF with enhanced Claude capabilities: {pdf_path}")
        
        try:
            # Direct approach using PDFProcessor
            from file_processors import PDFProcessor
            
            # Ensure we have a properly initialized LLM service
            if not self.llm_service.api_key:
                logger.warning("No API key found. Setting from config for PDF processing.")
                self.llm_service.api_key = self.config.get("api_key")
                
            # Create a dedicated processor for this PDF
            pdf_processor = PDFProcessor(self.db_manager, self.llm_service)
            
            # Process the PDF
            result = pdf_processor.process(pdf_path)
            
            if result:
                logger.info(f"Successfully processed PDF: {pdf_path}")
                
                # Optional: Add to database if requested
                file_id = None
                if self.db_manager:
                    # Create a hash of the file
                    import hashlib
                    with open(pdf_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Add file to database
                    file_id = self.db_manager.add_file(
                        file_path=pdf_path,
                        file_type="pdf",
                        file_hash=file_hash,
                        metadata=result.get('metadata')
                    )
                    
                    if file_id:
                        # Make sure we have content to store
                        raw_text = result.get('raw_text', '')
                        
                        # Make sure we have processed content if LLM was used
                        processed_text = result.get('processed_text', None)
                        
                        # Format the raw text if it's a placeholder message and we have processed content
                        if (not raw_text or raw_text == "No text could be extracted - may be image-based PDF") and processed_text:
                            raw_text = f"PDF text extracted via LLM analysis:\n\n{processed_text}"
                            logger.info(f"Formatted raw text with LLM analysis notice for {os.path.basename(pdf_path)}")
                        
                        # Add content to database
                        content_id = self.db_manager.add_content(
                            file_id=file_id,
                            content_type='text',
                            content_text=raw_text,
                            processed_text=processed_text
                        )
                        
                        if content_id:
                            # Add tags
                            if 'tags' in result and result['tags']:
                                logger.info(f"Adding tags: {result['tags']}")
                                self.db_manager.add_tags(content_id, result['tags'])
                            
                            # Add tasks
                            if 'tasks' in result and result['tasks']:
                                logger.info(f"Adding tasks: {result['tasks']}")
                                for task_text in result['tasks']:
                                    self.db_manager.add_task(content_id, task_text)
                
                return result
            else:
                logger.warning(f"PDF processing produced no results for {pdf_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error in enhanced PDF processing for {pdf_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def generate_weekly_digest(self):
        """Generate a weekly digest."""
        try:
            # Calculate the end date (yesterday)
            end_date = datetime.now() - timedelta(days=1)
            
            # Generate the digest
            result = self.digest_generator.generate_weekly_digest(end_date)
            
            if result:
                logger.info(f"Weekly digest generated: {result['file_path']}")
                return True
            else:
                logger.warning("Failed to generate weekly digest")
                return False
        except Exception as e:
            logger.error(f"Error generating weekly digest: {e}")
            return False
    
    def generate_monthly_digest(self):
        """Generate a monthly digest."""
        try:
            # Calculate year and month for the previous month
            today = datetime.now()
            first_of_month = today.replace(day=1)
            last_month = first_of_month - timedelta(days=1)
            year = last_month.year
            month = last_month.month
            
            # Generate the digest
            result = self.digest_generator.generate_monthly_digest(year, month)
            
            if result:
                logger.info(f"Monthly digest generated: {result['file_path']}")
                return True
            else:
                logger.warning("Failed to generate monthly digest")
                return False
        except Exception as e:
            logger.error(f"Error generating monthly digest: {e}")
            return False
    
    def generate_task_list(self):
        """Generate a task list."""
        try:
            # Include completed tasks by default
            result = self.digest_generator.generate_task_list(include_completed=True)
            
            if result:
                logger.info(f"Task list generated: {result['file_path']}")
                return True
            else:
                logger.warning("Failed to generate task list")
                return False
        except Exception as e:
            logger.error(f"Error generating task list: {e}")
            return False
    
    def generate_suggested_reading(self):
        """Generate suggested reading."""
        try:
            result = self.digest_generator.generate_suggested_reading()
            
            if result:
                logger.info(f"Suggested reading generated: {result['file_path']}")
                return True
            else:
                logger.warning("Failed to generate suggested reading")
                return False
        except Exception as e:
            logger.error(f"Error generating suggested reading: {e}")
            return False

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Notes Digest application")
    parser.add_argument('--config', type=str, default='config.json', help='Path to configuration file')
    parser.add_argument('--process-file', type=str, help='Process a specific file')
    parser.add_argument('--weekly-digest', action='store_true', help='Generate a weekly digest')
    parser.add_argument('--monthly-digest', action='store_true', help='Generate a monthly digest')
    parser.add_argument('--task-list', action='store_true', help='Generate a task list')
    parser.add_argument('--suggested-reading', action='store_true', help='Generate suggested reading')
    
    args = parser.parse_args()
    
    # Initialize the application
    app = NotesDigestApp(args.config)
    
    # Check if any specific actions were requested
    if args.process_file:
        app.process_file(args.process_file)
    elif args.weekly_digest:
        app.generate_weekly_digest()
    elif args.monthly_digest:
        app.generate_monthly_digest()
    elif args.task_list:
        app.generate_task_list()
    elif args.suggested_reading:
        app.generate_suggested_reading()
    else:
        # Start the application normally
        app.start()

if __name__ == "__main__":
    main()
