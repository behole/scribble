import sqlite3
import json
import os
import logging
from datetime import datetime

class DatabaseManager:
    """Manages storage and retrieval of processed notes data."""
    
    def __init__(self, db_path="notes_digest.db"):
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self):
        """Create the database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            file_type TEXT,
            file_hash TEXT,
            date_added TIMESTAMP,
            last_processed TIMESTAMP,
            metadata TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            content_type TEXT,
            content_text TEXT,
            processed_text TEXT,
            embedding_id TEXT,
            date_processed TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_type TEXT,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            content TEXT,
            created_date TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_tags (
            content_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (content_id, tag_id),
            FOREIGN KEY (content_id) REFERENCES content (id),
            FOREIGN KEY (tag_id) REFERENCES tags (id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            task_text TEXT,
            completed BOOLEAN DEFAULT 0,
            due_date TIMESTAMP,
            created_date TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES content (id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_file(self, file_path, file_type, file_hash, metadata=None):
        """Add a new file to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            cursor.execute('''
            INSERT OR IGNORE INTO files 
            (file_path, file_type, file_hash, date_added, last_processed, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (file_path, file_type, file_hash, now, now, metadata_json))
            
            file_id = cursor.lastrowid
            conn.commit()
            return file_id
        except Exception as e:
            logging.error(f"Error adding file to database: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def add_content(self, file_id, content_type, content_text, processed_text=None):
        """Add processed content for a file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute('''
            INSERT INTO content 
            (file_id, content_type, content_text, processed_text, date_processed)
            VALUES (?, ?, ?, ?, ?)
            ''', (file_id, content_type, content_text, processed_text, now))
            
            content_id = cursor.lastrowid
            conn.commit()
            return content_id
        except Exception as e:
            logging.error(f"Error adding content to database: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def add_tags(self, content_id, tags):
        """Add tags to content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for tag in tags:
                # Add tag if not exists
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                
                # Get tag id
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                tag_id = cursor.fetchone()[0]
                
                # Associate tag with content
                cursor.execute('''
                INSERT OR IGNORE INTO content_tags (content_id, tag_id)
                VALUES (?, ?)
                ''', (content_id, tag_id))
            
            conn.commit()
        except Exception as e:
            logging.error(f"Error adding tags: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def add_task(self, content_id, task_text, due_date=None):
        """Add a task extracted from content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute('''
            INSERT INTO tasks 
            (content_id, task_text, due_date, created_date)
            VALUES (?, ?, ?, ?)
            ''', (content_id, task_text, due_date, now))
            
            task_id = cursor.lastrowid
            conn.commit()
            return task_id
        except Exception as e:
            logging.error(f"Error adding task: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def save_digest(self, digest_type, content, start_date=None, end_date=None):
        """Save a digest."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute('''
            INSERT INTO digests 
            (digest_type, start_date, end_date, content, created_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (digest_type, start_date, end_date, content, now))
            
            digest_id = cursor.lastrowid
            conn.commit()
            return digest_id
        except Exception as e:
            logging.error(f"Error saving digest: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_content_for_period(self, start_date, end_date):
        """Get all content processed between two dates."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT c.*, f.file_type, f.file_path
            FROM content c
            JOIN files f ON c.file_id = f.id
            WHERE c.date_processed BETWEEN ? AND ?
            ORDER BY c.date_processed
            ''', (start_date, end_date))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving content: {e}")
            return []
        finally:
            conn.close()
    
    def get_tags_for_content(self, content_id):
        """Get all tags for a content item."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT t.name
            FROM tags t
            JOIN content_tags ct ON t.id = ct.tag_id
            WHERE ct.content_id = ?
            ''', (content_id,))
            
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error retrieving tags: {e}")
            return []
        finally:
            conn.close()
    
    def get_tasks(self, completed=None, start_date=None, end_date=None):
        """Get tasks with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Join with the content and files tables to get file information
        query = """
        SELECT t.id, t.content_id, t.task_text, t.completed, t.due_date, t.created_date, 
               f.file_path, c.content_type
        FROM tasks t
        JOIN content c ON t.content_id = c.id
        JOIN files f ON c.file_id = f.id
        WHERE 1=1
        """
        params = []
        
        if completed is not None:
            query += " AND t.completed = ?"
            params.append(1 if completed else 0)
        
        if start_date:
            query += " AND t.created_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND t.created_date <= ?"
            params.append(end_date)
        
        # Sort by completion status, then due date if available, then creation date
        query += " ORDER BY t.completed ASC, t.due_date ASC NULLS LAST, t.created_date DESC"
        
        try:
            # SQLite might not support NULLS LAST, so we'll handle it differently
            query = query.replace("NULLS LAST", "")
            cursor.execute(query, params)
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving tasks: {e}")
            try:
                # Fallback to simpler query if the complex one fails
                simple_query = "SELECT * FROM tasks WHERE 1=1"
                if completed is not None:
                    simple_query += " AND completed = ?"
                simple_query += " ORDER BY created_date DESC"
                cursor.execute(simple_query, params[:1] if completed is not None else [])
                return cursor.fetchall()
            except Exception as e2:
                logging.error(f"Error in fallback query: {e2}")
                return []
        finally:
            conn.close()
    
    def get_latest_digest(self, digest_type):
        """Get the most recent digest of a specific type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT * FROM digests
            WHERE digest_type = ?
            ORDER BY created_date DESC
            LIMIT 1
            ''', (digest_type,))
            
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error retrieving digest: {e}")
            return None
        finally:
            conn.close()

# Additional methods needed for web interface
    def get_recent_content(self, limit=5):
        """Get the most recently processed content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT c.*, f.file_type, f.file_path
            FROM content c
            JOIN files f ON c.file_id = f.id
            ORDER BY c.date_processed DESC
            LIMIT ?
            ''', (limit,))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving recent content: {e}")
            return []
        finally:
            conn.close()
            
    def get_content_statistics(self):
        """Get general statistics about content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Total content count
            cursor.execute('SELECT COUNT(*) FROM content')
            total_count = cursor.fetchone()[0]
            
            # Content count by type
            cursor.execute('SELECT content_type, COUNT(*) FROM content GROUP BY content_type')
            type_counts = cursor.fetchall()
            
            # Tags count
            cursor.execute('SELECT COUNT(*) FROM tags')
            tags_count = cursor.fetchone()[0]
            
            return (total_count, type_counts, tags_count)
        except Exception as e:
            logging.error(f"Error retrieving content statistics: {e}")
            return (0, [], 0)
        finally:
            conn.close()
            
    def get_digest_by_id(self, digest_id):
        """Get a specific digest by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM digests WHERE id = ?', (digest_id,))
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error retrieving digest: {e}")
            return None
        finally:
            conn.close()
            
    def get_all_digests(self, digest_type=None):
        """Get all digests, optionally filtered by type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if digest_type:
                cursor.execute('''
                SELECT * FROM digests 
                WHERE digest_type = ? 
                ORDER BY created_date DESC
                ''', (digest_type,))
            else:
                cursor.execute('SELECT * FROM digests ORDER BY created_date DESC')
                
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving digests: {e}")
            return []
        finally:
            conn.close()
            
    def get_task_by_id(self, task_id):
        """Get a specific task by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error retrieving task: {e}")
            return None
        finally:
            conn.close()
            
    def update_task_status(self, task_id, completed):
        """Update a task's completion status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            UPDATE tasks 
            SET completed = ?
            WHERE id = ?
            ''', (1 if completed else 0, task_id))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Error updating task status: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            
    def get_tasks_for_content(self, content_id):
        """Get all tasks for a specific content item."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT * FROM tasks
            WHERE content_id = ?
            ORDER BY created_date DESC
            ''', (content_id,))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving tasks for content: {e}")
            return []
        finally:
            conn.close()
            
    def get_paginated_content(self, page=1, per_page=20):
        """Get paginated content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        offset = (page - 1) * per_page
        
        try:
            cursor.execute('''
            SELECT c.*, f.file_type, f.file_path
            FROM content c
            JOIN files f ON c.file_id = f.id
            ORDER BY c.date_processed DESC
            LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving paginated content: {e}")
            return []
        finally:
            conn.close()
            
    def get_content_count(self):
        """Get total content count."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT COUNT(*) FROM content')
            return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"Error retrieving content count: {e}")
            return 0
        finally:
            conn.close()
            
    def get_content_by_id(self, content_id):
        """Get a specific content item by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT c.*, f.file_type, f.file_path
            FROM content c
            JOIN files f ON c.file_id = f.id
            WHERE c.id = ?
            ''', (content_id,))
            
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error retrieving content: {e}")
            return None
        finally:
            conn.close()
            
    def get_file_by_id(self, file_id):
        """Get a specific file by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM files WHERE id = ?', (file_id,))
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error retrieving file: {e}")
            return None
        finally:
            conn.close()
            
    def get_top_tags(self, limit=10):
        """Get most used tags with counts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT t.name, COUNT(ct.content_id) as count
            FROM tags t
            JOIN content_tags ct ON t.id = ct.tag_id
            GROUP BY t.id
            ORDER BY count DESC
            LIMIT ?
            ''', (limit,))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving top tags: {e}")
            return []
        finally:
            conn.close()
            
    def get_content_by_tag(self, tag_name, limit=100):
        """Get content with a specific tag."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT c.*, f.file_type, f.file_path
            FROM content c
            JOIN files f ON c.file_id = f.id
            JOIN content_tags ct ON c.id = ct.content_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = ?
            ORDER BY c.date_processed DESC
            LIMIT ?
            ''', (tag_name, limit))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving content by tag: {e}")
            return []
        finally:
            conn.close()
            
    def get_related_tags(self, tag_name, limit=10):
        """Get tags that often appear with the given tag."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT t2.name, COUNT(*) as count
            FROM tags t1
            JOIN content_tags ct1 ON t1.id = ct1.tag_id
            JOIN content_tags ct2 ON ct1.content_id = ct2.content_id
            JOIN tags t2 ON ct2.tag_id = t2.id
            WHERE t1.name = ? AND t2.name != ?
            GROUP BY t2.id
            ORDER BY count DESC
            LIMIT ?
            ''', (tag_name, tag_name, limit))
            
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving related tags: {e}")
            return []
        finally:
            conn.close()
    
    def update_content_processed_text(self, content_id, processed_text):
        """Update processed text for content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            UPDATE content 
            SET processed_text = ?
            WHERE id = ?
            ''', (processed_text, content_id))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Error updating processed text: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            
    def get_unprocessed_content(self, limit=None):
        """Get content items that have not been processed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            query = '''
            SELECT c.id, c.file_id, c.content_type, c.content_text, c.processed_text, c.embedding_id, c.date_processed
            FROM content c
            WHERE c.processed_text IS NULL
            '''
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving unprocessed content: {e}")
            return []
        finally:
            conn.close()
            
    def get_all_content(self, limit=None):
        """Get all content items."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            query = '''
            SELECT c.id, c.file_id, c.content_type, c.content_text, c.processed_text, c.embedding_id, c.date_processed
            FROM content c
            ORDER BY c.date_processed DESC
            '''
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving all content: {e}")
            return []
        finally:
            conn.close()
            
    def delete_content(self, content_id):
        """Delete a content item and associated data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # First, delete associated tags and tasks
            cursor.execute('DELETE FROM content_tags WHERE content_id = ?', (content_id,))
            cursor.execute('DELETE FROM tasks WHERE content_id = ?', (content_id,))
            
            # Now delete the content itself
            cursor.execute('DELETE FROM content WHERE id = ?', (content_id,))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Error deleting content: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            
    def close(self):
        """Close any open database connections."""
        # In SQLite connections are usually closed after each operation
        # This method exists for consistency with other database APIs
        logging.info("Database connections closed")

# Example usage
if __name__ == "__main__":
    # Initialize the database manager
    db_manager = DatabaseManager("test_notes.db")
    
    # Test adding a file
    file_id = db_manager.add_file(
        file_path="test_note.txt",
        file_type="document",
        file_hash="abc123",
        metadata={"author": "User"}
    )
    
    # Test adding content
    if file_id:
        content_id = db_manager.add_content(
            file_id=file_id,
            content_type="text",
            content_text="This is a test note with a #task to complete.",
            processed_text="This is a processed test note."
        )
        
        # Test adding tags
        if content_id:
            db_manager.add_tags(content_id, ["test", "note"])
            
            # Test adding a task
            db_manager.add_task(
                content_id=content_id,
                task_text="Complete test task"
            )
    
    # Test saving a digest
    db_manager.save_digest(
        digest_type="weekly",
        content="This is a weekly digest for testing.",
        start_date="2023-01-01T00:00:00",
        end_date="2023-01-07T23:59:59"
    )
    
    print("Database tests completed.")
