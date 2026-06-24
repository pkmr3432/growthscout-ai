import os
import logging

# Configure structured JSON logging format
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("web_analyzer_server")

# Environment configurations with fallback defaults
SCRAPER_USER_AGENT = os.getenv("SCRAPER_USER_AGENT", "GrowthScoutBot/1.0")
SCRAPER_RATE_LIMIT_DELAY = int(os.getenv("SCRAPER_RATE_LIMIT_DELAY", "2"))
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "15"))

# Resource limits and payload boundaries
MAX_PAYLOAD_SIZE = 2 * 1024 * 1024  # 2MB response buffer cap
MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = ("http", "https")
