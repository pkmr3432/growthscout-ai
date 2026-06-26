# agents/orchestrator_agent/service_names.py
from enum import Enum

class ServiceName(str, Enum):
    GOOGLE_MAPS = "GOOGLE_MAPS"
    GEMINI = "GEMINI"
    WEBSITE_SCRAPER = "WEBSITE_SCRAPER"
    LOCAL_SEARCH_MCP = "LOCAL_SEARCH_MCP"
    WEB_ANALYZER_MCP = "WEB_ANALYZER_MCP"
    FIRESTORE = "FIRESTORE"

