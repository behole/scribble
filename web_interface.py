import os
import json
import logging
from datetime import datetime
from pathlib import Path
import markdown
import flask
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load configuration
CONFIG_PATH = "config.json"
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
else:
    config = {
        "notes_folder": "./notes_folder",
        "db_path": "notes_digest.db",
        "output_dir": "digests"
    }

# Initialize database connection
from database_manager import DatabaseManager
db_manager = DatabaseManager(config.get("db_path", "notes_digest.db"))

@app.route('/')
def index():
    """Main dashboard page."""
    # Get latest digests
    latest_weekly = db_manager.get_latest_digest("weekly")
    latest_monthly = db_manager.get_latest_digest("monthly")
    
    # Get recent content
    recent_content = db_manager.get_recent_content(limit=5)
    
    # Get task statistics
    active_tasks = db_manager.get_tasks(completed=False)
    completed_tasks = db_manager.get_tasks(completed=True)
    
    # Get total content statistics
    content_stats = db_manager.get_content_statistics()
    
    return render_template(
        'index.html',
        latest_weekly=latest_weekly,
        latest_monthly=latest_monthly,
        recent_content=recent_content,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks,
        content_stats=content_stats
    )

@app.route('/digests')
def digests():
    """List all digests."""
    weekly_digests = db_manager.get_all_digests("weekly")
    monthly_digests = db_manager.get_all_digests("monthly")
    
    return render_template(
        'digests.html',
        weekly_digests=weekly_digests,
        monthly_digests=monthly_digests
    )

@app.route('/digest/<int:digest_id>')
def view_digest(digest_id):
    """View a specific digest."""
    digest = db_manager.get_digest_by_id(digest_id)
    
    if not digest:
        flash("Digest not found", "error")
        return redirect(url_for('digests'))
    
    # Convert markdown to HTML
    digest_content = markdown.markdown(digest[5])  # Assuming content is at index 5
    
    return render_template(
        'view_digest.html',
        digest=digest,
        digest_content=digest_content
    )

@app.route('/digest/download/<int:digest_id>')
def download_digest(digest_id):
    """Download a specific digest as markdown."""
    digest = db_manager.get_digest_by_id(digest_id)
    
    if not digest:
        flash("Digest not found", "error")
        return redirect(url_for('digests'))
    
    digest_type = digest[1]  # Assuming type is at index 1
    start_date = datetime.fromisoformat(digest[3]).strftime('%Y-%m-%d')  # Assuming start_date is at index 3
    
    # Create a temporary file
    temp_dir = os.path.join(app.root_path, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"{digest_type}_digest_{start_date}.md"
    file_path = os.path.join(temp_dir, filename)
    
    with open(file_path, 'w') as f:
        f.write(digest[5])  # Assuming content is at index 5
    
    return send_from_directory(directory=temp_dir, path=filename, as_attachment=True)

@app.route('/tasks')
def tasks():
    """View and manage tasks."""
    show_completed = request.args.get('show_completed', 'false') == 'true'
    
    if show_completed:
        all_tasks = db_manager.get_tasks()
    else:
        all_tasks = db_manager.get_tasks(completed=False)
    
    # Group tasks by source file
    tasks_by_source = {}
    for task in all_tasks:
        if len(task) >= 7:  # Check if we have the source file information
            source_file = os.path.basename(task[6]) if task[6] else "Unknown"
            if source_file not in tasks_by_source:
                tasks_by_source[source_file] = []
            tasks_by_source[source_file].append(task)
        else:
            # Fallback for older query format
            if "Unknown" not in tasks_by_source:
                tasks_by_source["Unknown"] = []
            tasks_by_source["Unknown"].append(task)
    
    return render_template(
        'tasks.html',
        tasks=all_tasks,
        tasks_by_source=tasks_by_source,
        show_completed=show_completed
    )

@app.route('/task/toggle/<int:task_id>', methods=['POST'])
def toggle_task(task_id):
    """Toggle task completion status."""
    task = db_manager.get_task_by_id(task_id)
    
    if not task:
        flash("Task not found", "error")
    else:
        current_status = task[3]  # Assuming completed status is at index 3
        new_status = not current_status
        success = db_manager.update_task_status(task_id, new_status)
        
        if success:
            status_text = "completed" if new_status else "marked active"
            flash(f"Task {status_text}", "success")
            
            # Log the change for debugging
            logger.info(f"Task {task_id} status updated to {'completed' if new_status else 'active'}")
        else:
            flash("Failed to update task status", "error")
            logger.error(f"Failed to update task {task_id} status")
    
    # Get the referrer URL to return to the same page
    referrer = request.referrer
    if referrer and 'tasks' in referrer:
        return redirect(referrer)
    else:
        return redirect(url_for('tasks'))

@app.route('/content')
def content():
    """View all content."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    content_items = db_manager.get_paginated_content(page=page, per_page=per_page)
    total_items = db_manager.get_content_count()
    
    total_pages = (total_items + per_page - 1) // per_page
    
    return render_template(
        'content.html',
        content=content_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@app.route('/content/<int:content_id>')
def view_content(content_id):
    """View a specific content item."""
    content_item = db_manager.get_content_by_id(content_id)
    
    if not content_item:
        flash("Content not found", "error")
        return redirect(url_for('content'))
    
    # Get file information
    file_id = content_item[1]  # Assuming file_id is at index 1
    file_info = db_manager.get_file_by_id(file_id)
    
    # Get tags for this content
    tags = db_manager.get_tags_for_content(content_id)
    
    # Get tasks for this content
    tasks = db_manager.get_tasks_for_content(content_id)
    
    # Process content before display
    processed_content = list(content_item)
    
    # If this is a PDF file with ClaudeGPT analysis, format it properly
    if file_info and file_info[1].lower().endswith('.pdf'):
        try:
            import markdown
            from markdown.extensions.extra import ExtraExtension
            
            # Use a more robust markdown conversion with extensions
            markdown_options = {
                'extensions': [ExtraExtension()],
                'output_format': 'html5'
            }
            
            # Process the raw content (index 3) if it contains Claude's analysis
            if processed_content[3] and "PDF text extracted via LLM analysis" in processed_content[3]:
                # We don't need to convert markdown here since we'll let the template handle it
                logger.info(f"Found Claude analysis for PDF in content_id {content_id}")
            
            # Convert Markdown for the processed content if present (index 4)
            if processed_content[4]:
                # Always convert processed content to HTML
                processed_content[4] = markdown.markdown(processed_content[4], **markdown_options)
                logger.info(f"Converted processed content to HTML for content_id {content_id}")
                
        except Exception as e:
            logger.error(f"Error converting markdown: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    return render_template(
        'view_content.html',
        content=tuple(processed_content),  # Convert back to tuple
        file_info=file_info,
        tags=tags,
        tasks=tasks
    )

@app.route('/tags')
def tags():
    """View all tags."""
    all_tags = db_manager.get_top_tags(limit=100)
    
    return render_template(
        'tags.html',
        tags=all_tags
    )

@app.route('/tag/<tag_name>')
def view_tag(tag_name):
    """View content with a specific tag."""
    content_items = db_manager.get_content_by_tag(tag_name)
    
    return render_template(
        'view_tag.html',
        tag=tag_name,
        content=content_items
    )

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """View and update application settings."""
    global config
    
    if request.method == 'POST':
        # Update basic settings
        config["notes_folder"] = request.form.get('notes_folder', config.get("notes_folder"))
        config["output_dir"] = request.form.get('output_dir', config.get("output_dir"))
        
        # Update schedule settings
        config.setdefault("schedule", {})
        config["schedule"]["weekly_digest"] = request.form.get('weekly_digest') == 'on'
        config["schedule"]["monthly_digest"] = request.form.get('monthly_digest') == 'on'
        config["schedule"]["task_list"] = request.form.get('task_list') == 'on'
        config["schedule"]["suggested_reading"] = request.form.get('suggested_reading') == 'on'
        
        # Update processing settings
        config.setdefault("processing", {})
        config["processing"]["enable_ocr"] = request.form.get('enable_ocr') == 'on'
        config["processing"]["enable_web_fetching"] = request.form.get('enable_web_fetching') == 'on'
        
        # Save configuration
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=4)
            flash("Settings saved successfully", "success")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            flash(f"Error saving settings: {str(e)}", "error")
    
    return render_template(
        'settings.html',
        config=config
    )

@app.route('/process', methods=['GET', 'POST'])
def process_file():
    """Manually process a file."""
    if request.method == 'POST':
        # Check if a file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        # If user did not select a file
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file:
            # Save file to notes folder
            notes_folder = config.get("notes_folder", "./notes_folder")
            os.makedirs(notes_folder, exist_ok=True)
            
            file_path = os.path.join(notes_folder, file.filename)
            file.save(file_path)
            
            # Process the file
            try:
                # Import NotesDigestApp to access processing methods
                from main_application import NotesDigestApp
                
                # Initialize app with the current configuration
                app_instance = NotesDigestApp(CONFIG_PATH)
                
                # Check if it's a PDF file that needs enhanced processing
                if file.filename.lower().endswith('.pdf'):
                    logger.info(f"Using enhanced PDF processing for {file.filename}")
                    
                    # Use enhanced PDF processing
                    result = app_instance.process_pdf_with_claude(file_path)
                    
                    if result:
                        # Extract useful information from the result
                        raw_text = result.get('raw_text', '')
                        processed_text = result.get('processed_text', '')
                        tasks = result.get('tasks', [])
                        tags = result.get('tags', [])
                        
                        # Get file information from the database
                        file_hash = result.get('metadata', {}).get('file_hash', '')
                        if not file_hash:
                            # Create a file hash if missing
                            import hashlib
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.md5(f.read()).hexdigest()
                        
                        # Get the file ID from the database, or create a new one
                        file_id = db_manager.add_file(
                            file_path=file_path,
                            file_type="pdf",
                            file_hash=file_hash,
                            metadata=result.get('metadata')
                        )
                        
                        # Apply any text transformations needed
                        if not raw_text or raw_text == "No text could be extracted - may be image-based PDF":
                            if processed_text:
                                # Use processed text as raw text if we couldn't extract the raw text
                                raw_text = f"PDF text extracted via LLM analysis:\n\n{processed_text}"
                        
                        # Save content to database with both raw and processed text
                        content_id = db_manager.add_content(
                            file_id=file_id,
                            content_type='text',
                            content_text=raw_text,
                            processed_text=processed_text
                        )
                        
                        # Add tags and tasks
                        if content_id:
                            if tags:
                                db_manager.add_tags(content_id, tags)
                            
                            if tasks:
                                for task_text in tasks:
                                    db_manager.add_task(content_id, task_text)
                        
                        # Show success message
                        msg = f"PDF {file.filename} processed successfully."
                        if tasks:
                            msg += f" Found {len(tasks)} tasks."
                        if tags:
                            msg += f" Generated {len(tags)} tags."
                            
                        flash(msg, "success")
                    else:
                        flash(f"PDF {file.filename} saved but could not be processed fully. It may be an image-based PDF.", "warning")
                else:
                    # Use standard processing for non-PDF files
                    success = app_instance.process_file(file_path)
                    if success:
                        flash(f"File {file.filename} processed successfully.", "success")
                    else:
                        flash(f"File {file.filename} saved but could not be processed fully.", "warning")
            except Exception as e:
                logger.error(f"Error processing file: {e}")
                flash(f"Error processing file: {str(e)}", "error")
            
            return redirect(url_for('index'))
    
    return render_template('process_file.html')

@app.route('/reset_database')
def reset_database():
    """Reset the database for debugging."""
    global db_manager
    
    try:
        # Get the database path
        db_path = config.get("db_path", "notes_digest.db")
        if os.path.exists(db_path):
            # Close any active connections
            db_manager.close()
            
            # Create a backup
            import shutil
            backup_path = f"{db_path}.bak"
            shutil.copy2(db_path, backup_path)
            
            # Delete the database file
            os.remove(db_path)
            
            # Reinitialize the database
            from database_manager import DatabaseManager
            db_manager = DatabaseManager(db_path)
            
            flash(f"Database reset successfully. Created backup at {backup_path}", "success")
        else:
            flash(f"Database file not found at {db_path}", "warning")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        flash(f"Error resetting database: {e}", "error")
    
    return redirect(url_for('index'))

@app.route('/content/delete/<int:content_id>', methods=['POST'])
def delete_content(content_id):
    """Delete a specific content item."""
    try:
        # Get the content item
        content_item = db_manager.get_content_by_id(content_id)
        
        if not content_item:
            flash("Content not found", "error")
            return redirect(url_for('content'))
        
        # Delete the content
        success = db_manager.delete_content(content_id)
        
        if success:
            flash(f"Content deleted successfully", "success")
        else:
            flash(f"Failed to delete content", "error")
    except Exception as e:
        logger.error(f"Error deleting content: {e}")
        flash(f"Error deleting content: {e}", "error")
    
    return redirect(url_for('content'))

@app.route('/clear_cache')
def clear_cache():
    """Clear application cache for debugging."""
    try:
        # Clear temp files
        import tempfile
        import shutil
        import glob
        
        # Try to clean up temporary directories
        temp_dirs = glob.glob(os.path.join(tempfile.gettempdir(), "tmp*"))
        cleared_dirs = 0
        for temp_dir in temp_dirs:
            if os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    cleared_dirs += 1
                except Exception as e:
                    logger.error(f"Error clearing temp dir {temp_dir}: {e}")
        
        # Clean up temp directory in app
        temp_dir = os.path.join(app.root_path, 'temp')
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
                flash(f"Cleared app temp directory.", "success")
            except Exception as e:
                logger.error(f"Error clearing app temp dir: {e}")
                flash(f"Error clearing app temp directory: {e}", "error")
        
        flash(f"Cache cleared. Removed {cleared_dirs} temporary directories.", "success")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        flash(f"Error clearing cache: {e}", "error")
    
    return redirect(url_for('index'))

@app.route('/generate/<digest_type>')
def generate_digest(digest_type):
    """Manually trigger digest generation."""
    # Import NotesDigestApp to access digest generation methods
    from main_application import NotesDigestApp
    
    try:
        # Initialize the app with the current configuration
        digest_app = NotesDigestApp(CONFIG_PATH)
        
        # Call the appropriate digest generation method
        success = False
        result_message = ""
        
        if digest_type == 'weekly':
            success = digest_app.generate_weekly_digest()
            result_message = "Weekly digest generated successfully" if success else "Failed to generate weekly digest"
        elif digest_type == 'monthly':
            success = digest_app.generate_monthly_digest()
            result_message = "Monthly digest generated successfully" if success else "Failed to generate monthly digest"
        elif digest_type == 'tasks':
            success = digest_app.generate_task_list()
            result_message = "Task list generated successfully" if success else "Failed to generate task list"
        elif digest_type == 'reading':
            # In case there's not enough recent content, we can still generate reasonably good suggestions
            # by using the LLM's knowledge
            from llm_service import LLMService
            llm = LLMService(api_key=digest_app.config.get("api_key"))
            
            # Get active tasks to inform suggestions
            task_list = []
            tasks = digest_app.db_manager.get_tasks(completed=False)
            if not tasks:
                tasks = digest_app.db_manager.get_tasks(completed=True)  # Fall back to completed tasks
            
            if tasks:
                task_list = [task[2] for task in tasks]
            
            # Manually generate suggestions if the task fails
            success = digest_app.generate_suggested_reading()
            
            if not success and llm.api_key:
                try:
                    # Collect any tags we might have
                    tags = []
                    all_content = digest_app.db_manager.get_all_content(limit=10)
                    for content in all_content:
                        content_id = content[0]
                        content_tags = digest_app.db_manager.get_tags_for_content(content_id)
                        tags.extend(content_tags)
                    
                    # Use LLM to generate suggestions
                    system_message = {
                        "role": "system",
                        "content": "You are a helpful assistant providing personalized reading suggestions."
                    }
                    
                    context = f"Tasks: {', '.join(task_list[:5])}\nTags/Interests: {', '.join(tags[:10])}" if task_list or tags else "No specific tasks or interests available."
                    
                    user_message = {
                        "role": "user",
                        "content": f"Please provide 5 reading suggestions based on this context:\n\n{context}\n\nFormat each suggestion with a title, author if applicable, and a 1-2 sentence reason why it's relevant."
                    }
                    
                    suggestions = llm._call_api([system_message, user_message])
                    
                    if suggestions:
                        # Save suggestions to file
                        file_name = f"suggested_reading_{datetime.now().strftime('%Y-%m-%d')}.md"
                        file_path = os.path.join(digest_app.digest_generator.output_dir, file_name)
                        
                        content = f"# Suggested Reading\n\nGenerated on: {datetime.now().strftime('%B %d, %Y')}\n\n"
                        content += suggestions
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        logger.info(f"Manually generated suggested reading saved to {file_path}")
                        success = True
                        result_message = "Suggested reading generated using available context"
                except Exception as e:
                    logger.error(f"Error generating manual suggestions: {e}")
                    success = False
                    result_message = "Failed to generate suggested reading"
            else:
                result_message = "Suggested reading generated successfully" if success else "Failed to generate suggested reading"
        else:
            flash(f"Unknown digest type: {digest_type}", "error")
            return redirect(url_for('index'))
        
        # Flash a message with the result
        flash(result_message, "success" if success else "error")
        
        # If successful, refresh digests in the database
        if success and digest_type in ['weekly', 'monthly']:
            flash("Digest saved to database and digests folder", "success")
    
    except Exception as e:
        logger.error(f"Error generating {digest_type} digest: {e}")
        flash(f"Error generating {digest_type} digest: {str(e)}", "error")
    
    return redirect(url_for('index'))

# Template filters
@app.template_filter('format_date')
def format_date(date_str):
    """Format an ISO date string."""
    if not date_str:
        return ""
    
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime('%B %d, %Y')
    except ValueError:
        return date_str

@app.template_filter('format_datetime')
def format_datetime(date_str):
    """Format an ISO datetime string."""
    if not date_str:
        return ""
    
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime('%B %d, %Y %H:%M')
    except ValueError:
        return date_str

@app.template_filter('truncate_text')
def truncate_text(text, length=100):
    """Truncate text to a specific length."""
    if not text:
        return ""
    
    if len(text) <= length:
        return text
    
    return text[:length] + "..."

def create_app():
    """Create and configure the Flask application."""
    # Create template folder if it doesn't exist
    template_dir = os.path.join(app.root_path, 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    # Create static folder if it doesn't exist
    static_dir = os.path.join(app.root_path, 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    # Create basic templates if they don't exist
    create_basic_templates(template_dir)
    
    # Create basic static files if they don't exist
    create_basic_static_files(static_dir)
    
    return app

def create_basic_templates(template_dir):
    """Create basic templates if they don't exist."""
    # Create base layout template
    base_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{% block title %}Notes Digest{% endblock %}</title>
        <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    </head>
    <body>
        <header>
            <div class="logo">Notes Digest</div>
            <nav>
                <ul>
                    <li><a href="{{ url_for('index') }}">Dashboard</a></li>
                    <li><a href="{{ url_for('digests') }}">Digests</a></li>
                    <li><a href="{{ url_for('tasks') }}">Tasks</a></li>
                    <li><a href="{{ url_for('content') }}">Content</a></li>
                    <li><a href="{{ url_for('tags') }}">Tags</a></li>
                    <li><a href="{{ url_for('process_file') }}">Process File</a></li>
                    <li><a href="{{ url_for('settings') }}">Settings</a></li>
                </ul>
            </nav>
        </header>
        
        <main>
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                <div class="flashes">
                  {% for category, message in messages %}
                    <div class="flash {{ category }}">{{ message }}</div>
                  {% endfor %}
                </div>
              {% endif %}
            {% endwith %}
            
            {% block content %}{% endblock %}
        </main>
        
        <footer>
            <p>Notes Digest &copy; {{ now.year }}</p>
        </footer>
    </body>
    </html>
    """
    
    create_template(os.path.join(template_dir, 'base.html'), base_template)
    
    # Create index template
    index_template = """
    {% extends 'base.html' %}
    
    {% block title %}Dashboard - Notes Digest{% endblock %}
    
    {% block content %}
    <h1>Dashboard</h1>
    
    <div class="dashboard-grid">
        <div class="dashboard-card">
            <h2>Recent Digests</h2>
            <div class="card-content">
                {% if latest_weekly %}
                <div class="digest-preview">
                    <h3>Weekly Digest: {{ latest_weekly[3]|format_date }} - {{ latest_weekly[4]|format_date }}</h3>
                    <p>{{ latest_weekly[5]|truncate_text }}</p>
                    <a href="{{ url_for('view_digest', digest_id=latest_weekly[0]) }}" class="button">View</a>
                </div>
                {% else %}
                <p>No weekly digests available</p>
                {% endif %}
                
                {% if latest_monthly %}
                <div class="digest-preview">
                    <h3>Monthly Digest: {{ latest_monthly[3]|format_date|format_date }} - {{ latest_monthly[4]|format_date }}</h3>
                    <p>{{ latest_monthly[5]|truncate_text }}</p>
                    <a href="{{ url_for('view_digest', digest_id=latest_monthly[0]) }}" class="button">View</a>
                </div>
                {% else %}
                <p>No monthly digests available</p>
                {% endif %}
                
                <div class="action-buttons">
                    <a href="{{ url_for('generate_digest', digest_type='weekly') }}" class="button">Generate Weekly</a>
                    <a href="{{ url_for('generate_digest', digest_type='monthly') }}" class="button">Generate Monthly</a>
                    <a href="{{ url_for('digests') }}" class="button">All Digests</a>
                </div>
            </div>
        </div>
        
        <div class="dashboard-card">
            <h2>Recent Content</h2>
            <div class="card-content">
                {% if recent_content %}
                <ul class="content-list">
                    {% for item in recent_content %}
                    <li>
                        <span class="content-type {{ item[2] }}">{{ item[2] }}</span>
                        <a href="{{ url_for('view_content', content_id=item[0]) }}">
                            {{ item[3]|truncate_text(50) }}
                        </a>
                        <span class="date">{{ item[6]|format_date }}</span>
                    </li>
                    {% endfor %}
                </ul>
                {% else %}
                <p>No content available</p>
                {% endif %}
                
                <div class="action-buttons">
                    <a href="{{ url_for('content') }}" class="button">All Content</a>
                    <a href="{{ url_for('process_file') }}" class="button">Add File</a>
                </div>
            </div>
        </div>
        
        <div class="dashboard-card">
            <h2>Tasks</h2>
            <div class="card-content">
                {% if active_tasks %}
                <ul class="task-list">
                    {% for task in active_tasks[:5] %}
                    <li>
                        <form action="{{ url_for('toggle_task', task_id=task[0]) }}" method="post" class="task-form">
                            <input type="checkbox" onchange="this.form.submit()">
                            <span class="task-text">{{ task[2] }}</span>
                        </form>
                    </li>
                    {% endfor %}
                </ul>
                {% else %}
                <p>No active tasks</p>
                {% endif %}
                
                <div class="action-buttons">
                    <a href="{{ url_for('tasks') }}" class="button">All Tasks</a>
                    <a href="{{ url_for('generate_digest', digest_type='tasks') }}" class="button">Generate Task List</a>
                </div>
            </div>
        </div>
        
        <div class="dashboard-card">
            <h2>Statistics</h2>
            <div class="card-content">
                <div class="stats">
                    <div class="stat-item">
                        <span class="stat-value">{{ content_stats[0] }}</span>
                        <span class="stat-label">Total Items</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{{ active_tasks|length }}</span>
                        <span class="stat-label">Active Tasks</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{{ completed_tasks|length }}</span>
                        <span class="stat-label">Completed Tasks</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    """
    
    create_template(os.path.join(template_dir, 'index.html'), index_template)
    
    # Create tasks template
    tasks_template = """
    {% extends 'base.html' %}
    
    {% block title %}Tasks - Notes Digest{% endblock %}
    
    {% block content %}
    <h1>Tasks</h1>
    
    <div class="task-controls">
        <a href="{{ url_for('tasks', show_completed='true' if not show_completed else 'false') }}" class="button">
            {{ 'Hide' if show_completed else 'Show' }} Completed
        </a>
        <a href="{{ url_for('generate_digest', digest_type='tasks') }}" class="button">Generate Task List</a>
    </div>
    
    {% if tasks %}
    <ul class="task-list full-list">
        {% for task in tasks %}
        <li>
            <form action="{{ url_for('toggle_task', task_id=task[0]) }}" method="post" class="task-form">
                <input type="checkbox" {% if task[3] %}checked{% endif %} onchange="this.form.submit()">
                <span class="task-text {% if task[3] %}completed{% endif %}">{{ task[2] }}</span>
                {% if task[4] %}
                <span class="due-date">Due: {{ task[4]|format_date }}</span>
                {% endif %}
            </form>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p>No tasks found</p>
    {% endif %}
    {% endblock %}
    """
    
    create_template(os.path.join(template_dir, 'tasks.html'), tasks_template)
    
    # Create other templates
    templates = {
        'digests.html': """
        {% extends 'base.html' %}
        
        {% block title %}Digests - Notes Digest{% endblock %}
        
        {% block content %}
        <h1>Digests</h1>
        
        <div class="digest-controls">
            <a href="{{ url_for('generate_digest', digest_type='weekly') }}" class="button">Generate Weekly</a>
            <a href="{{ url_for('generate_digest', digest_type='monthly') }}" class="button">Generate Monthly</a>
        </div>
        
        <div class="digest-section">
            <h2>Weekly Digests</h2>
            {% if weekly_digests %}
            <ul class="digest-list">
                {% for digest in weekly_digests %}
                <li>
                    <a href="{{ url_for('view_digest', digest_id=digest[0]) }}">
                        {{ digest[3]|format_date }} - {{ digest[4]|format_date }}
                    </a>
                    <div class="digest-actions">
                        <a href="{{ url_for('download_digest', digest_id=digest[0]) }}" class="button small">Download</a>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p>No weekly digests available</p>
            {% endif %}
        </div>
        
        <div class="digest-section">
            <h2>Monthly Digests</h2>
            {% if monthly_digests %}
            <ul class="digest-list">
                {% for digest in monthly_digests %}
                <li>
                    <a href="{{ url_for('view_digest', digest_id=digest[0]) }}">
                        {{ digest[3]|format_date|format_date }} - {{ digest[4]|format_date }}
                    </a>
                    <div class="digest-actions">
                        <a href="{{ url_for('download_digest', digest_id=digest[0]) }}" class="button small">Download</a>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p>No monthly digests available</p>
            {% endif %}
        </div>
        {% endblock %}
        """,
        
        'view_digest.html': """
        {% extends 'base.html' %}
        
        {% block title %}Digest - Notes Digest{% endblock %}
        
        {% block content %}
        <div class="digest-header">
            <h1>{{ digest[1]|title }} Digest</h1>
            <div class="digest-meta">
                <p>Period: {{ digest[3]|format_date }} - {{ digest[4]|format_date }}</p>
                <p>Created: {{ digest[6]|format_datetime }}</p>
            </div>
            <div class="digest-actions">
                <a href="{{ url_for('download_digest', digest_id=digest[0]) }}" class="button">Download</a>
                <a href="{{ url_for('digests') }}" class="button">Back to Digests</a>
            </div>
        </div>
        
        <div class="digest-content markdown-content">
            {{ digest_content|safe }}
        </div>
        {% endblock %}
        """,
        
        'content.html': """
        {% extends 'base.html' %}
        
        {% block title %}Content - Notes Digest{% endblock %}
        
        {% block content %}
        <h1>Content</h1>
        
        {% if content %}
        <table class="content-table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Content</th>
                    <th>Date Processed</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for item in content %}
                <tr>
                    <td class="content-type {{ item[2] }}">{{ item[2] }}</td>
                    <td>{{ item[3]|truncate_text(100) }}</td>
                    <td>{{ item[6]|format_date }}</td>
                    <td>
                        <a href="{{ url_for('view_content', content_id=item[0]) }}" class="button small">View</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="pagination">
            {% if page > 1 %}
            <a href="{{ url_for('content', page=page-1, per_page=per_page) }}" class="button">Previous</a>
            {% endif %}
            
            <span class="page-info">Page {{ page }} of {{ total_pages }}</span>
            
            {% if page < total_pages %}
            <a href="{{ url_for('content', page=page+1, per_page=per_page) }}" class="button">Next</a>
            {% endif %}
        </div>
        {% else %}
        <p>No content found</p>
        {% endif %}
        {% endblock %}
        """,
        
        'view_content.html': """
        {% extends 'base.html' %}
        
        {% block title %}Content - Notes Digest{% endblock %}
        
        {% block content %}
        <div class="content-header">
            <h1>Content</h1>
            <div class="content-meta">
                <p>Type: <span class="content-type {{ content[2] }}">{{ content[2] }}</span></p>
                <p>File: {{ file_info[1] }}</p>
                <p>Processed: {{ content[6]|format_datetime }}</p>
            </div>
            <div class="content-actions">
                <a href="{{ url_for('content') }}" class="button">Back to Content</a>
            </div>
        </div>
        
        {% if tags %}
        <div class="content-tags">
            <h2>Tags</h2>
            <div class="tag-list">
                {% for tag in tags %}
                <a href="{{ url_for('view_tag', tag_name=tag) }}" class="tag">#{{ tag }}</a>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        {% if tasks %}
        <div class="content-tasks">
            <h2>Tasks</h2>
            <ul class="task-list">
                {% for task in tasks %}
                <li>
                    <form action="{{ url_for('toggle_task', task_id=task[0]) }}" method="post" class="task-form">
                        <input type="checkbox" {% if task[3] %}checked{% endif %} onchange="this.form.submit()">
                        <span class="task-text {% if task[3] %}completed{% endif %}">{{ task[2] }}</span>
                    </form>
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
        
        <div class="content-sections">
            <div class="content-section">
                <h2>Raw Content</h2>
                <div class="content-text">
                    {{ content[3] }}
                </div>
            </div>
            
            {% if content[4] %}
            <div class="content-section">
                <h2>Processed Content</h2>
                <div class="content-text">
                    {{ content[4] }}
                </div>
            </div>
            {% endif %}
        </div>
        {% endblock %}
        """,
        
        'tags.html': """
        {% extends 'base.html' %}
        
        {% block title %}Tags - Notes Digest{% endblock %}
        
        {% block content %}
        <h1>Tags</h1>
        
        {% if tags %}
        <div class="tag-cloud">
            {% for tag, count in tags %}
            <a href="{{ url_for('view_tag', tag_name=tag) }}" class="tag" style="font-size: {{ 100 + (count * 20) }}%">#{{ tag }} ({{ count }})</a>
            {% endfor %}
        </div>
        {% else %}
        <p>No tags found</p>
        {% endif %}
        {% endblock %}
        """,
        
        'view_tag.html': """
        {% extends 'base.html' %}
        
        {% block title %}Tag: #{{ tag }} - Notes Digest{% endblock %}
        
        {% block content %}
        <div class="tag-header">
            <h1>Tag: #{{ tag }}</h1>
            <a href="{{ url_for('tags') }}" class="button">All Tags</a>
        </div>
        
        {% if content %}
        <table class="content-table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Content</th>
                    <th>Date Processed</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for item in content %}
                <tr>
                    <td class="content-type {{ item[2] }}">{{ item[2] }}</td>
                    <td>{{ item[3]|truncate_text(100) }}</td>
                    <td>{{ item[6]|format_date }}</td>
                    <td>
                        <a href="{{ url_for('view_content', content_id=item[0]) }}" class="button small">View</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>No content found with this tag</p>
        {% endif %}
        {% endblock %}
        """,
        
        'settings.html': """
        {% extends 'base.html' %}
        
        {% block title %}Settings - Notes Digest{% endblock %}
        
        {% block content %}
        <h1>Settings</h1>
        
        <form method="post" class="settings-form">
            <div class="settings-section">
                <h2>Basic Settings</h2>
                
                <div class="form-group">
                    <label for="notes_folder">Notes Folder:</label>
                    <input type="text" id="notes_folder" name="notes_folder" value="{{ config.notes_folder }}">
                </div>
                
                <div class="form-group">
                    <label for="output_dir">Output Directory:</label>
                    <input type="text" id="output_dir" name="output_dir" value="{{ config.output_dir }}">
                </div>
            </div>
            
            <div class="settings-section">
                <h2>Schedule Settings</h2>
                
                <div class="form-group checkbox">
                    <input type="checkbox" id="weekly_digest" name="weekly_digest" {% if config.schedule.weekly_digest %}checked{% endif %}>
                    <label for="weekly_digest">Enable Weekly Digest</label>
                </div>
                
                <div class="form-group checkbox">
                    <input type="checkbox" id="monthly_digest" name="monthly_digest" {% if config.schedule.monthly_digest %}checked{% endif %}>
                    <label for="monthly_digest">Enable Monthly Digest</label>
                </div>
                
                <div class="form-group checkbox">
                    <input type="checkbox" id="task_list" name="task_list" {% if config.schedule.task_list %}checked{% endif %}>
                    <label for="task_list">Enable Task List Generation</label>
                </div>
                
                <div class="form-group checkbox">
                    <input type="checkbox" id="suggested_reading" name="suggested_reading" {% if config.schedule.suggested_reading %}checked{% endif %}>
                    <label for="suggested_reading">Enable Suggested Reading</label>
                </div>
            </div>
            
            <div class="settings-section">
                <h2>Processing Settings</h2>
                
                <div class="form-group checkbox">
                    <input type="checkbox" id="enable_ocr" name="enable_ocr" {% if config.processing.enable_ocr %}checked{% endif %}>
                    <label for="enable_ocr">Enable OCR for Images and PDFs</label>
                </div>
                
                <div class="form-group checkbox">
                    <input type="checkbox" id="enable_web_fetching" name="enable_web_fetching" {% if config.processing.enable_web_fetching %}checked{% endif %}>
                    <label for="enable_web_fetching">Enable Web Content Fetching</label>
                </div>
            </div>
            
            <div class="form-actions">
                <button type="submit" class="button">Save Settings</button>
                <a href="{{ url_for('index') }}" class="button secondary">Cancel</a>
            </div>
        </form>
        {% endblock %}
        """,
        
        'process_file.html': """
        {% extends 'base.html' %}
        
        {% block title %}Process File - Notes Digest{% endblock %}
        
        {% block content %}
        <h1>Process File</h1>
        
        <div class="upload-form">
            <form method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="file">Select File:</label>
                    <input type="file" id="file" name="file">
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="button">Upload & Process</button>
                    <a href="{{ url_for('index') }}" class="button secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <div class="upload-info">
            <h2>Supported File Types</h2>
            <ul>
                <li>Text Documents (.txt, .md, .doc, .docx)</li>
                <li>Images (.jpg, .png, .gif)</li>
                <li>PDFs (.pdf)</li>
                <li>Web Content (.html, .htm)</li>
                <li>URL References (.url, .webloc)</li>
                <li>AI Chats (.json with chat format)</li>
            </ul>
        </div>
        {% endblock %}
        """
    }
    
    for template_name, template_content in templates.items():
        create_template(os.path.join(template_dir, template_name), template_content)

def create_template(path, content):
    """Create a template file if it doesn't exist."""
    if not os.path.exists(path):
        try:
            with open(path, 'w') as f:
                f.write(content.strip())
            logger.info(f"Created template: {path}")
        except Exception as e:
            logger.error(f"Error creating template {path}: {e}")

def create_basic_static_files(static_dir):
    """Create basic static files if they don't exist."""
    # Create CSS file
    css_content = """
    /* Main layout */
    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }
    
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
        line-height: 1.6;
        color: #333;
        background-color: #f5f5f5;
        margin: 0;
    }
    
    header {
        background-color: #2c3e50;
        color: white;
        padding: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .logo {
        font-size: 1.5rem;
        font-weight: bold;
    }
    
    nav ul {
        display: flex;
        list-style: none;
    }
    
    nav li {
        margin-left: 1rem;
    }
    
    nav a {
        color: white;
        text-decoration: none;
    }
    
    nav a:hover {
        text-decoration: underline;
    }
    
    main {
        max-width: 1200px;
        margin: 2rem auto;
        padding: 0 1rem;
    }
    
    h1 {
        margin-bottom: 2rem;
        color: #2c3e50;
    }
    
    footer {
        text-align: center;
        padding: 1rem;
        background-color: #2c3e50;
        color: white;
        margin-top: 2rem;
    }
    
    /* Buttons */
    .button {
        display: inline-block;
        background-color: #3498db;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        text-decoration: none;
        border: none;
        cursor: pointer;
        font-size: 0.9rem;
    }
    
    .button:hover {
        background-color: #2980b9;
    }
    
    .button.secondary {
        background-color: #95a5a6;
    }
    
    .button.secondary:hover {
        background-color: #7f8c8d;
    }
    
    .button.small {
        padding: 0.25rem 0.5rem;
        font-size: 0.8rem;
    }
    
    /* Flash messages */
    .flashes {
        margin-bottom: 2rem;
    }
    
    .flash {
        padding: 1rem;
        margin-bottom: 1rem;
        border-radius: 4px;
    }
    
    .flash.success {
        background-color: #dff0d8;
        color: #3c763d;
        border: 1px solid #d6e9c6;
    }
    
    .flash.error {
        background-color: #f2dede;
        color: #a94442;
        border: 1px solid #ebccd1;
    }
    
    /* Dashboard */
    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
        gap: 2rem;
    }
    
    .dashboard-card {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        overflow: hidden;
    }
    
    .dashboard-card h2 {
        padding: 1rem;
        background-color: #f8f9fa;
        border-bottom: 1px solid #e9ecef;
        margin: 0;
    }
    
    .card-content {
        padding: 1rem;
    }
    
    .digest-preview {
        margin-bottom: 1.5rem;
    }
    
    .digest-preview h3 {
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    
    .action-buttons {
        margin-top: 1rem;
        display: flex;
        gap: 0.5rem;
    }
    
    /* Content and tasks */
    .content-list, .task-list {
        list-style: none;
    }
    
    .content-list li, .task-list li {
        padding: 0.5rem 0;
        border-bottom: 1px solid #e9ecef;
    }
    
    .content-type {
        display: inline-block;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
        background-color: #e9ecef;
    }
    
    .content-type.document {
        background-color: #d1ecf1;
        color: #0c5460;
    }
    
    .content-type.image {
        background-color: #d4edda;
        color: #155724;
    }
    
    .content-type.pdf {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    .content-type.web_clip {
        background-color: #fff3cd;
        color: #856404;
    }
    
    .content-type.ai_chat {
        background-color: #e2e3e5;
        color: #383d41;
    }
    
    .date {
        font-size: 0.8rem;
        color: #6c757d;
    }
    
    /* Task list */
    .task-form {
        display: flex;
        align-items: center;
    }
    
    .task-text {
        margin-left: 0.5rem;
    }
    
    .task-text.completed {
        text-decoration: line-through;
        color: #6c757d;
    }
    
    .task-controls {
        margin-bottom: 1rem;
    }
    
    .task-list.full-list li {
        padding: 0.75rem 0;
    }
    
    .due-date {
        font-size: 0.8rem;
        color: #dc3545;
        margin-left: 1rem;
    }
    
    /* Statistics */
    .stats {
        display: flex;
        justify-content: space-around;
        text-align: center;
    }
    
    .stat-value {
        display: block;
        font-size: 2rem;
        font-weight: bold;
        color: #2c3e50;
    }
    
    .stat-label {
        display: block;
        color: #6c757d;
        font-size: 0.9rem;
    }
    
    /* Digests */
    .digest-controls {
        margin-bottom: 1.5rem;
        display: flex;
        gap: 0.5rem;
    }
    
    .digest-section {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 1.5rem;
        margin-bottom: 2rem;
    }
    
    .digest-list {
        list-style: none;
        margin-top: 1rem;
    }
    
    .digest-list li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 0;
        border-bottom: 1px solid #e9ecef;
    }
    
    .digest-actions {
        display: flex;
        gap: 0.5rem;
    }
    
    /* Viewing digest */
    .digest-header {
        margin-bottom: 2rem;
    }
    
    .digest-meta {
        color: #6c757d;
        margin-bottom: 1rem;
    }
    
    .digest-content {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 2rem;
    }
    
    .markdown-content h2 {
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid #e9ecef;
        padding-bottom: 0.5rem;
    }
    
    /* Content table */
    .content-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 2rem;
        background-color: white;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }
    
    .content-table th,
    .content-table td {
        padding: 0.75rem;
        text-align: left;
        border-bottom: 1px solid #e9ecef;
    }
    
    .content-table th {
        background-color: #f8f9fa;
        font-weight: bold;
    }
    
    .pagination {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 1rem;
        margin-top: 1rem;
    }
    
    .page-info {
        color: #6c757d;
    }
    
    /* View content */
    .content-header {
        margin-bottom: 2rem;
    }
    
    .content-meta {
        color: #6c757d;
        margin-bottom: 1rem;
    }
    
    .content-tags {
        margin-bottom: 2rem;
    }
    
    .tag-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    
    .tag {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        background-color: #e9ecef;
        border-radius: 4px;
        color: #495057;
        text-decoration: none;
    }
    
    .tag:hover {
        background-color: #dee2e6;
    }
    
    .content-sections {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 2rem;
    }
    
    .content-section {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 1.5rem;
    }
    
    .content-section h2 {
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #e9ecef;
    }
    
    .content-text {
        white-space: pre-wrap;
        font-family: monospace;
        overflow-x: auto;
    }
    
    /* Tag cloud */
    .tag-cloud {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 2rem;
        text-align: center;
    }
    
    .tag-cloud .tag {
        margin: 0.5rem;
        display: inline-block;
    }
    
    /* Settings form */
    .settings-form {
        max-width: 800px;
    }
    
    .settings-section {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 1.5rem;
        margin-bottom: 2rem;
    }
    
    .settings-section h2 {
        margin-bottom: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #e9ecef;
    }
    
    .form-group {
        margin-bottom: 1rem;
    }
    
    .form-group label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    
    .form-group input[type="text"] {
        width: 100%;
        padding: 0.5rem;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 1rem;
    }
    
    .form-group.checkbox {
        display: flex;
        align-items: center;
    }
    
    .form-group.checkbox input {
        margin-right: 0.5rem;
    }
    
    .form-group.checkbox label {
        margin: 0;
    }
    
    .form-actions {
        display: flex;
        gap: 1rem;
        margin-top: 2rem;
    }
    
    /* File upload form */
    .upload-form {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 1.5rem;
        margin-bottom: 2rem;
    }
    
    .upload-info {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        padding: 1.5rem;
    }
    
    .upload-info h2 {
        margin-bottom: 1rem;
    }
    
    .upload-info ul {
        list-style-position: inside;
    }
    
    @media (max-width: 768px) {
        header {
            flex-direction: column;
            padding: 0.5rem;
        }
        
        nav ul {
            flex-wrap: wrap;
            justify-content: center;
            margin-top: 0.5rem;
        }
        
        nav li {
            margin: 0.25rem;
        }
        
        .dashboard-grid {
            grid-template-columns: 1fr;
        }
        
        .content-sections {
            grid-template-columns: 1fr;
        }
    }
    """
    
    css_path = os.path.join(static_dir, 'style.css')
    if not os.path.exists(css_path):
        try:
            with open(css_path, 'w') as f:
                f.write(css_content.strip())
            logger.info(f"Created CSS file: {css_path}")
        except Exception as e:
            logger.error(f"Error creating CSS file {css_path}: {e}")

if __name__ == "__main__":
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the Notes Digest web interface")
    parser.add_argument('--port', type=int, default=5000, help='Port to run the web interface on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the web interface on')
    args = parser.parse_args()
    
    # Create the application
    app = create_app()
    
    # Add jinja2 context processor for current year
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}
    
    # Run the application
    port = args.port
    try:
        app.run(debug=True, host=args.host, port=port)
    except OSError as e:
        if "Address already in use" in str(e):
            # Try a different port
            logger.warning(f"Port {port} is in use, trying port {port+1}")
            port += 1
            app.run(debug=True, host=args.host, port=port)