import logging
import sys

def setup_logging(level="INFO"):
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Reduce noise from libraries but keep Flask startup info
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.INFO)  # Show startup messages
    
    # Filter out debug messages but keep important info
    class MinimalWerkzeugFilter(logging.Filter):
        def filter(self, record):
            # Allow startup messages and errors
            if "Running on" in record.getMessage() or record.levelno >= logging.WARNING:
                return True
            # Block debug noise like "HEAD /static/..." requests
            if record.levelno < logging.WARNING:
                return False
            return True
    
    werkzeug_logger.addFilter(MinimalWerkzeugFilter())