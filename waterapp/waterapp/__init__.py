# waterapp/__init__.py
import os
from flask import Flask

from .scheduler import start_scheduler
from .views import bp as main_bp


def create_app():
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(main_bp)
    
    from .hardware import init_hardware
    init_hardware()

    # Start scheduler *once* (avoid double-start in debug reloader)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler()

    return app
