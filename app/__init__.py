"""Task Tracker API: a small REST service for managing to-do tasks.

Use create_app() to build the Flask application. Tests pass their own
database path so every test run starts with an empty database.
"""

import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from . import db
from .routes import bp


def create_app(database_path=None):
    app = Flask(__name__)
    app.config["DATABASE"] = database_path or os.environ.get(
        "TASKS_DB", os.path.join(app.instance_path, "tasks.sqlite")
    )
    os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_schema()

    app.register_blueprint(bp)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        # Return every error as JSON so API clients never get an HTML page.
        return jsonify(error=err.name, message=err.description), err.code

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
