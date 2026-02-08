#!/usr/bin/env python3
"""
Main entry point for the irrigation control application.
Run with: python3 run.py
"""
import sys
import logging
from waterapp import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('waterapp.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Initialize and run the Flask application."""
    try:
        app = create_app()
        logger.info("Starting irrigation control application on 0.0.0.0:8080")
        
        # Run on all interfaces, port 8080
        # debug=False prevents reloader which could cause GPIO conflicts
        app.run(
            host="0.0.0.0",
            port=8080,
            debug=False,
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
