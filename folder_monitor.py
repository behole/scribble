import time
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import mimetypes
import hashlib

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

class NotesEventHandler(FileSystemEventHandler):
    """Handler for file system events in the notes folder."""
    
    def __init__(self, processor):
        self.processor = processor
        self.processed_files = set()
        
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            file_path = event.src_path
            # Generate a hash of the file to track if we've processed it
            file_hash = self._get_file_hash(file_path)
            
            if file_hash not in self.processed_files:
                logging.info(f"New file detected: {file_path}")
                self._process_file(file_path, file_hash)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            file_path = event.src_path
            file_hash = self._get_file_hash(file_path)
            
            if file_hash not in self.processed_files:
                logging.info(f"File modified: {file_path}")
                self._process_file(file_path, file_hash)
    
    def _get_file_hash(self, file_path):
        """Create a hash of the file to track changes."""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                return hashlib.md5(file_content).hexdigest()
        except Exception as e:
            logging.error(f"Error hashing file {file_path}: {e}")
            return None
    
    def _process_file(self, file_path, file_hash):
        """Send file for processing and mark as processed."""
        try:
            file_type = self._determine_file_type(file_path)
            logging.info(f"Processing {file_path} as {file_type}")
            
            # Send to processor
            self.processor.process_file(file_path, file_type)
            
            # Mark as processed
            self.processed_files.add(file_hash)
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
    
    def _determine_file_type(self, file_path):
        """Determine the type of file."""
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Determine mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Categorize file
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return 'image'
        elif ext in ['.pdf']:
            # Could be handwritten notes or digital document
            return 'pdf'
        elif ext in ['.txt', '.md', '.rtf', '.doc', '.docx']:
            return 'document'
        elif ext in ['.html', '.htm']:
            return 'web_clip'
        elif ext in ['.url', '.webloc']:
            return 'url'
        elif ext in ['.json'] and 'chat' in os.path.basename(file_path).lower():
            return 'ai_chat'
        else:
            # Default to unknown
            return 'unknown'

class NotesProcessor:
    """Processes files based on their type."""
    
    def __init__(self, db_manager=None, llm_service=None):
        self.db_manager = db_manager
        self.llm_service = llm_service
        self.processor_factory = None
    
    def process_file(self, file_path, file_type):
        """Process a file based on its type."""
        logging.info(f"Processing {file_path} as {file_type}")
        
        if not self.processor_factory:
            # Import here to avoid circular imports
            from file_processors import ProcessorFactory
            self.processor_factory = ProcessorFactory(self.db_manager, self.llm_service)
        
        # Get the appropriate processor for this file type
        processor = self.processor_factory.get_processor(file_type)
        
        # Process the file
        try:
            result = processor.process(file_path)
            
            if result and self.db_manager:
                # Create a hash of the file
                import hashlib
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                
                # Add file to database
                file_id = self.db_manager.add_file(
                    file_path=file_path,
                    file_type=file_type,
                    file_hash=file_hash,
                    metadata=result.get('metadata')
                )
                
                if file_id:
                    # Make sure we have content to store
                    raw_text = result.get('raw_text', '')
                    if not raw_text and file_type == 'pdf':
                        raw_text = "No text could be extracted - this appears to be an image-based PDF"
                    
                    # Make sure we have processed content if LLM was used
                    processed_text = result.get('processed_text', None)
                    if processed_text:
                        logging.info(f"Storing processed text ({len(processed_text)} chars) for {file_path}")
                    else:
                        logging.warning(f"No processed text available for {file_path}")
                    
                    # Add content to database
                    content_id = self.db_manager.add_content(
                        file_id=file_id,
                        content_type='text',  # Simplified for now
                        content_text=raw_text,
                        processed_text=processed_text
                    )
                    
                    if content_id:
                        # Add tags
                        if 'tags' in result and result['tags']:
                            logging.info(f"Adding tags: {result['tags']}")
                            self.db_manager.add_tags(content_id, result['tags'])
                        
                        # Add tasks
                        if 'tasks' in result and result['tasks']:
                            logging.info(f"Adding tasks: {result['tasks']}")
                            for task_text in result['tasks']:
                                self.db_manager.add_task(content_id, task_text)
                
                logging.info(f"Successfully processed and stored {file_path}")
                return True
            else:
                logging.warning(f"Processing {file_path} produced no results")
                return False
                
        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")
            return False

class NotesWatcher:
    """Monitors a folder for changes to notes files."""
    
    def __init__(self, path, processor):
        self.path = path
        self.processor = processor
        self.observer = Observer()
    
    def start(self):
        """Start monitoring the folder."""
        event_handler = NotesEventHandler(self.processor)
        self.observer.schedule(event_handler, self.path, recursive=True)
        self.observer.start()
        logging.info(f"Started monitoring folder: {self.path}")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop monitoring the folder."""
        self.observer.stop()
        self.observer.join()
        logging.info("Stopped monitoring folder")

# Example usage
if __name__ == "__main__":
    # Path to monitor
    NOTES_FOLDER = "./notes_folder"  # Replace with your actual folder path
    
    # Create folder if it doesn't exist
    if not os.path.exists(NOTES_FOLDER):
        os.makedirs(NOTES_FOLDER)
        logging.info(f"Created folder: {NOTES_FOLDER}")
    
    # Initialize processor and watcher
    processor = NotesProcessor()
    watcher = NotesWatcher(NOTES_FOLDER, processor)
    
    # Start monitoring
    watcher.start()
