#!/usr/bin/env python3
import os
import logging
from database_manager import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('test_setup')

def main():
    """Test the basic setup of the application."""
    logger.info("Starting test setup")
    
    # Check required directories
    directories = ["notes_folder", "digests"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")
        else:
            logger.info(f"Directory already exists: {directory}")
    
    # Initialize database
    db_path = "notes_digest.db"
    logger.info(f"Initializing database at {db_path}")
    db_manager = DatabaseManager(db_path)
    
    # Check if database was created successfully
    if os.path.exists(db_path):
        logger.info("Database file created successfully")
    else:
        logger.error("Failed to create database file")
        return False
    
    # Test adding a sample file and content
    try:
        # Create a sample test file
        sample_file = "notes_folder/test_note.txt"
        with open(sample_file, 'w') as f:
            f.write("This is a test note with a #task to complete.\n\nTask: Finish the setup.")
        
        logger.info(f"Created sample file: {sample_file}")
        
        # Add file to database
        file_id = db_manager.add_file(
            file_path=sample_file,
            file_type="document",
            file_hash="test123"
        )
        
        if file_id:
            logger.info(f"Added file to database with ID: {file_id}")
            
            # Add content
            content_id = db_manager.add_content(
                file_id=file_id,
                content_type="text",
                content_text="This is a test note with a #task to complete.\n\nTask: Finish the setup.",
                processed_text="This is a processed test note."
            )
            
            if content_id:
                logger.info(f"Added content to database with ID: {content_id}")
                
                # Add tags
                db_manager.add_tags(content_id, ["test", "setup"])
                logger.info("Added tags to content")
                
                # Add task
                task_id = db_manager.add_task(
                    content_id=content_id,
                    task_text="Finish the setup"
                )
                
                if task_id:
                    logger.info(f"Added task to database with ID: {task_id}")
                else:
                    logger.error("Failed to add task to database")
            else:
                logger.error("Failed to add content to database")
        else:
            logger.error("Failed to add file to database")
        
    except Exception as e:
        logger.error(f"Error during test setup: {e}")
        return False
    
    logger.info("Test setup completed successfully")
    return True

if __name__ == "__main__":
    main()