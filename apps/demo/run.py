#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo launcher script
Starts FastAPI server and opens web interface
"""

import os
import sys
import webbrowser
import logging
from pathlib import Path
from multiprocessing import Process

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required directories and files exist"""
    web_dir = Path(__file__).parent / "web"
    if not web_dir.exists():
        logger.error("Web directory not found!")
        return False
        
    if not (web_dir / "index.html").exists():
        logger.error("index.html not found in web directory!")
        return False
        
    return True

def setup_environment():
    """Setup the environment for running the demo"""
    # Change to script directory
    os.chdir(Path(__file__).parent)

def start_server():
    """Start FastAPI server"""
    try:
        import uvicorn
        from apps.demo.app import app
        
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        server.run()
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)

def open_browser():
    """Open web interface in default browser"""
    webbrowser.open('http://localhost:8000/static/index.html')

def main():
    """Main entry point"""
    logger.info("Starting Smart Home Device Control Demo")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Start server in a separate process
    server = Process(target=start_server)
    server.start()
    
    try:
        # Wait a bit for server to start
        import time
        time.sleep(2)
        
        # Open web interface
        open_browser()
        
        # Keep main process running
        server.join()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.terminate()
        server.join(timeout=1)
        if server.is_alive():
            logger.warning("Server process did not terminate cleanly")
            server.kill()
    
    except Exception as e:
        logger.error(f"Error running demo: {str(e)}")
        server.terminate()
        server.join()
        sys.exit(1)

if __name__ == "__main__":
    main()