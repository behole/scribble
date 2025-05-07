# Notes Digest Automation System

This project automates the processing, analysis, and digestion of various types of notes and documents using LLMs (Large Language Models).

## Overview

The Notes Digest Automation System monitors a specified folder for new files, processes them using appropriate methods based on file type, and generates various outputs including weekly digests, trend reports, task lists, and other structured information.

## Features

- **Folder Monitoring**: Automatically detect new files added to a specified folder
- **Multi-format Support**: Process various file types:
  - Handwritten Notes (as images)
  - Digital Notes
  - URLs
  - Web Clips
  - Screenshots
  - Images
  - AI Chats
- **Content Processing**:
  - Transcription of handwritten text
  - Text extraction from various formats
  - Content analysis and summarization
  - Task extraction
  - Topic/tag extraction
- **Automated Outputs**:
  - Weekly digests
  - Monthly digests
  - Comprehensive full digest
  - Task lists
  - Topic reports
  - Trend analysis
  - Reading suggestions

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/notes-digest.git
   cd notes-digest
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install additional system dependencies:
   - Tesseract OCR for image text extraction:
     - On Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
     - On macOS: `brew install tesseract`
     - On Windows: Download and install from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

4. Set up your API key:
   - Create a `.env` file with your API key:
     ```
     ANTHROPIC_API_KEY=your_api_key_here
     ```
   - Or set it in the configuration file (see below)

## Configuration

Create a `config.json` file with the following structure:

```json
{
  "notes_folder": "./notes_folder",
  "db_path": "notes_digest.db",
  "api_key": "your_api_key_here",
  "weekly_digest_day": "Sunday",
  "monthly_digest_day": 1,
  "output_dir": "digests",
  "schedule": {
    "weekly_digest": true,
    "monthly_digest": true,
    "task_list": true,
    "suggested_reading": true
  }
}
```

## Usage

### Starting the System

Run the main application to start folder monitoring and scheduled tasks:

```
python main_application.py
```

### Processing Individual Files

Process a specific file:

```
python main_application.py --process-file /path/to/your/file.txt
```

### Enhanced PDF Processing

For better PDF processing, especially for scanned or image-based PDFs:

```
python process_pdf.py /path/to/your/file.pdf
```

This uses a combination of OCR and Claude's vision capabilities to extract as much information as possible from the PDF.

### Generating Specific Outputs

Generate a weekly digest:

```
python main_application.py --weekly-digest
```

Generate a monthly digest:

```
python main_application.py --monthly-digest
```

Generate a task list:

```
python main_application.py --task-list
```

Generate suggested reading:

```
python main_application.py --suggested-reading
```

## File Structure

- `main_application.py`: Main entry point for the application
- `folder_monitor.py`: Monitors for new files and detects file types
- `database_manager.py`: Manages storage and retrieval of processed notes data
- `file_processors.py`: Contains processors for different file types
- `llm_service.py`: Interface to LLM API for content analysis
- `digest_generator.py`: Generates digests, reports, and outputs

## Custom Extensions

To add support for additional file types or processing methods:

1. Add a new processor class in `file_processors.py`
2. Register the new processor in the `ProcessorFactory` class
3. Update the file type detection in `NotesEventHandler._determine_file_type()`

## Dependencies

- watchdog: For file system monitoring
- PyPDF2: For PDF processing
- pytesseract: For OCR processing
- pdf2image: For converting PDFs to images
- PyMuPDF: Alternative PDF processing library with better image extraction
- Pillow: For image handling
- beautifulsoup4: For HTML/web content parsing
- requests: For HTTP requests
- markdown: For rendering markdown output
- schedule: For task scheduling
- flask: For the web interface

### Optional System Dependencies

- Poppler: Required by pdf2image for PDF-to-image conversion
  - On macOS: `brew install poppler`
  - On Ubuntu: `sudo apt-get install poppler-utils`
  - On Windows: Download precompiled binaries

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
