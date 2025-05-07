#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import threading
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('start')

def start_main_app():
    """Start the main application process."""
    logger.info("Starting main application...")
    try:
        subprocess.run([sys.executable, "main_application.py"], check=True)
    except KeyboardInterrupt:
        logger.info("Main application stopped")
    except Exception as e:
        logger.error(f"Error starting main application: {e}")

def start_web_interface(port=5000):
    """Start the web interface process."""
    logger.info(f"Starting web interface on port {port}...")
    try:
        # Try several ports starting with the specified one
        max_port_attempts = 5
        for port_attempt in range(port, port + max_port_attempts):
            try:
                subprocess.run([sys.executable, "web_interface.py", "--port", str(port_attempt)], check=True)
                break
            except subprocess.CalledProcessError:
                if port_attempt < port + max_port_attempts - 1:
                    logger.warning(f"Port {port_attempt} unavailable, trying {port_attempt + 1}")
                else:
                    raise
    except KeyboardInterrupt:
        logger.info("Web interface stopped")
    except Exception as e:
        logger.error(f"Error starting web interface: {e}")

def main():
    parser = argparse.ArgumentParser(description="Start Notes Digest application")
    parser.add_argument('--main-only', action='store_true', help='Start only the main application')
    parser.add_argument('--web-only', action='store_true', help='Start only the web interface')
    parser.add_argument('--port', type=int, default=5000, help='Port for web interface (default: 5000)')
    
    args = parser.parse_args()
    
    if args.main_only:
        # Start only the main application
        start_main_app()
    elif args.web_only:
        # Start only the web interface
        start_web_interface(args.port)
    else:
        # Start both in separate threads
        logger.info("Starting both main application and web interface...")
        
        main_thread = threading.Thread(target=start_main_app)
        web_thread = threading.Thread(target=lambda: start_web_interface(args.port))
        
        main_thread.daemon = True
        web_thread.daemon = True
        
        main_thread.start()
        time.sleep(2)  # Give the main app a moment to start
        web_thread.start()
        
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
            sys.exit(0)

if __name__ == "__main__":
    main()