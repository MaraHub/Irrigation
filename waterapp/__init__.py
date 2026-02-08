"""
Flask application factory for the irrigation control system.
"""
import os
import logging
import atexit
from flask import Flask

from .scheduler import start_scheduler
from .views import bp as main_bp
from .hardware import cleanup_hardware

logger = logging.getLogger(__name__)


def create_app():
    """
    Create and configure the Flask application.
    
    Returns:
        Configured Flask app instance
    """
    app = Flask(__name__)
    
    # Configure Flask
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_AS_ASCII'] = False  # Support Greek characters in JSON
    
    # Register blueprints
    app.register_blueprint(main_bp)
    logger.info("[APP] Registered main blueprint")
    
    # Initialize hardware on startup
    try:
        from .hardware import init_hardware
        init_hardware()
        logger.info("[APP] Hardware initialized")
    except Exception as e:
        logger.error(f"[APP] Failed to initialize hardware: {e}", exc_info=True)
        # Continue anyway - hardware errors will be handled per-operation

    # Start scheduler (avoid double-start in debug mode)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            start_scheduler()
            logger.info("[APP] Scheduler started")
        except Exception as e:
            logger.error(f"[APP] Failed to start scheduler: {e}", exc_info=True)
    else:
        logger.info("[APP] Skipping scheduler start (debug reloader detected)")

    # Register cleanup on shutdown
    atexit.register(cleanup_on_shutdown)
    
    logger.info("[APP] Application created successfully")
    return app


def cleanup_on_shutdown():
    """Clean up resources on application shutdown."""
    logger.info("[APP] Application shutting down, cleaning up...")
    try:
        cleanup_hardware()
        logger.info("[APP] Cleanup complete")
    except Exception as e:
        logger.error(f"[APP] Error during cleanup: {e}", exc_info=True)
