import logging
import sys
from flask import has_request_context, g, session


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.game_id = session.get("game_id", "-")
        else:
            record.request_id = "-"
            record.game_id = "-"
        return True


class MinimalWerkzeugFilter(logging.Filter):
    def filter(self, record):
        # Allow startup messages and errors
        if "Running on" in record.getMessage() or record.levelno >= logging.WARNING:
            return True
        # Block debug noise like "GET /static/..." requests
        if record.levelno < logging.WARNING:
            return False
        return True


def setup_logging(level="INFO"):
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    # Add request correlation filter
    handler.addFilter(RequestContextFilter())

    # Formatter with request id
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | req=%(request_id)s | game=%(game_id)s | %(message)s"
    )
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers = [handler]

    # Configure werkzeug logger
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.addFilter(MinimalWerkzeugFilter())