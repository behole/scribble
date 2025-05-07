#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import logging
import platform
import shutil
import json
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('install')

def check_python_version():
    """Check if Python version is 3.8 or higher."""
    major = sys.version_info.major
    minor = sys.version_info.minor
    
    if major < 3 or (major == 3 and minor < 8):
        logger.error("Python 3.8 or higher is required. You're using Python %s.%s", major, minor)
        return False
    
    logger.info("Python version check passed: %s.%s", major, minor)
    return True

def check_pip():
    """Check if pip is installed."""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
        logger.info("pip installation check passed.")
        return True
    except subprocess.CalledProcessError:
        logger.error("pip is not installed or not working properly.")
        return False

def check_tesseract():
    """Check if Tesseract OCR is installed."""
    try:
        if platform.system() == 'Windows':
            # On Windows, tesseract might be in PATH or installed but not in PATH
            tesseract_path = shutil.which('tesseract')
            if tesseract_path:
                logger.info("Tesseract OCR found in PATH: %s", tesseract_path)
                return True
            else:
                # Check common installation locations
                common_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe", 
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        logger.info("Tesseract OCR found at %s", path)
                        logger.warning("Tesseract is installed but not in PATH. You may need to add it to your PATH.")
                        return True
                
                logger.warning("Tesseract OCR not found. OCR functionality will be limited.")
                return False
        else:
            # On Linux/Mac
            result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.split("\n")[0]
                logger.info("Tesseract OCR check passed: %s", version)
                return True
            else:
                logger.warning("Tesseract OCR not found. OCR functionality will be limited.")
                return False
    except FileNotFoundError:
        logger.warning("Tesseract OCR not found. OCR functionality will be limited.")
        return False
    except Exception as e:
        logger.warning("Error checking for Tesseract OCR: %s", str(e))
        return False

def install_requirements(requirements_file, venv=None):
    """Install Python dependencies from requirements.txt."""
    if not os.path.exists(requirements_file):
        logger.error("Requirements file not found: %s", requirements_file)
        return False
    
    python_executable = sys.executable
    if venv:
        if platform.system() == 'Windows':
            python_executable = os.path.join(venv, 'Scripts', 'python.exe')
        else:
            python_executable = os.path.join(venv, 'bin', 'python')
    
    logger.info("Installing requirements from %s", requirements_file)
    try:
        subprocess.run([python_executable, "-m", "pip", "install", "-r", requirements_file], check=True)
        logger.info("Requirements installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to install requirements: %s", str(e))
        return False

def create_virtual_environment(venv_path):
    """Create a Python virtual environment."""
    if os.path.exists(venv_path):
        logger.info("Virtual environment already exists at %s", venv_path)
        return True
    
    logger.info("Creating virtual environment at %s", venv_path)
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
        logger.info("Virtual environment created successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to create virtual environment: %s", str(e))
        return False

def create_default_config(config_path):
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
        },
        "processing": {
            "enable_ocr": True,
            "enable_web_fetching": True,
            "max_text_length": 10000,
            "handwriting_threshold": 20
        },
        "llm": {
            "model": "claude-3-7-sonnet-20250219",
            "temperature": 0.7,
            "max_tokens": 4000,
            "analysis_depth": "standard"
        }
    }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        logger.info("Default configuration created at %s", config_path)
        return True
    except Exception as e:
        logger.error("Failed to create default configuration: %s", str(e))
        return False

def create_directories(config):
    """Create necessary directories."""
    directories = [
        config.get("notes_folder", "./notes_folder"),
        config.get("output_dir", "digests")
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                logger.info("Created directory: %s", directory)
            except Exception as e:
                logger.error("Failed to create directory %s: %s", directory, str(e))
                return False
    
    return True

def setup_api_key(config_path):
    """Set up the API key in the configuration."""
    if not os.path.exists(config_path):
        logger.error("Configuration file not found: %s", config_path)
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if config.get("api_key"):
            logger.info("API key already set in configuration.")
            return True
        
        api_key = input("Enter your Claude API key: ").strip()
        if not api_key:
            logger.warning("No API key provided. You'll need to set it later.")
            return True
        
        config["api_key"] = api_key
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        logger.info("API key saved to configuration.")
        return True
    except Exception as e:
        logger.error("Failed to set up API key: %s", str(e))
        return False

def setup_web_interface(venv=None):
    """Set up the Flask web interface."""
    python_executable = sys.executable
    if venv:
        if platform.system() == 'Windows':
            python_executable = os.path.join(venv, 'Scripts', 'python.exe')
        else:
            python_executable = os.path.join(venv, 'bin', 'python')
    
    try:
        logger.info("Checking Flask installation...")
        subprocess.run([python_executable, "-c", "import flask"], check=True, capture_output=True)
        logger.info("Flask is installed.")
    except subprocess.CalledProcessError:
        logger.info("Installing Flask...")
        try:
            subprocess.run([python_executable, "-m", "pip", "install", "flask", "markdown"], check=True)
            logger.info("Flask installed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error("Failed to install Flask: %s", str(e))
            return False
    
    web_interface_dir = "web_interface"
    if not os.path.exists(web_interface_dir):
        try:
            os.makedirs(web_interface_dir)
            os.makedirs(os.path.join(web_interface_dir, "templates"))
            os.makedirs(os.path.join(web_interface_dir, "static"))
            logger.info("Created web interface directories.")
        except Exception as e:
            logger.error("Failed to create web interface directories: %s", str(e))
            return False
    
    return True

def install(args):
    """Install the Notes Digest application."""
    # Check Python version
    if not check_python_version():
        return False
    
    # Check pip
    if not check_pip():
        return False
    
    # Create virtual environment if requested
    venv_path = None
    if args.venv:
        venv_path = args.venv if isinstance(args.venv, str) else ".venv"
        if not create_virtual_environment(venv_path):
            return False
    
    # Install requirements
    if not install_requirements("requirements.txt", venv_path):
        return False
    
    # Check for Tesseract OCR (optional)
    check_tesseract()
    
    # Create default configuration
    config_path = args.config if args.config else "config.json"
    if not os.path.exists(config_path):
        if not create_default_config(config_path):
            return False
    
    # Load configuration
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error("Failed to load configuration: %s", str(e))
        return False
    
    # Create necessary directories
    if not create_directories(config):
        return False
    
    # Setup API key
    if not args.no_api_key:
        if not setup_api_key(config_path):
            return False
    
    # Setup web interface
    if args.web:
        if not setup_web_interface(venv_path):
            return False
    
    logger.info("Installation completed successfully!")
    
    # Print usage instructions
    print("\n=== Notes Digest Usage Instructions ===\n")
    print("1. Configure the application:")
    print(f"   python config_utility.py --setup --config {config_path}")
    print("\n2. Start the application:")
    print("   python main_application.py")
    if args.web:
        print("\n3. Start the web interface:")
        print("   python web_interface.py")
    
    print("\nPlease refer to the README.md for more detailed instructions.")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Install the Notes Digest application")
    parser.add_argument("--venv", nargs="?", const=".venv", help="Create and use a virtual environment (optional path)")
    parser.add_argument("--config", type=str, help="Path to the configuration file (default: config.json)")
    parser.add_argument("--no-api-key", action="store_true", help="Skip API key setup")
    parser.add_argument("--web", action="store_true", help="Set up the web interface")
    
    args = parser.parse_args()
    
    if install(args):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()