import os
import logging

# Configure structured JSON logging format
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("local_search_server")

# Environment configurations with fallback defaults
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "10"))

# Security bounds and input constraint constants
MAX_QUERY_LENGTH = 256
MIN_QUERY_LENGTH = 5
ALLOWED_QUERY_PATTERN = r"^[a-zA-Z0-9\s\,\-\.]+$"
