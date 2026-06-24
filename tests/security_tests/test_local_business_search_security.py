import pytest
from unittest.mock import patch
from servers.local_search_server.server import local_business_search

@pytest.mark.asyncio
async def test_local_business_search_query_too_short():
    from servers.local_search_server import server
    with patch.object(server, "GOOGLE_MAPS_API_KEY", "dummy_key"):
        with pytest.raises(ValueError, match="Query length must be between"):
            await local_business_search("dent")

@pytest.mark.asyncio
async def test_local_business_search_query_too_long():
    from servers.local_search_server import server
    with patch.object(server, "GOOGLE_MAPS_API_KEY", "dummy_key"):
        long_query = "dentist " * 40  # > 256 characters
        with pytest.raises(ValueError, match="Query length must be between"):
            await local_business_search(long_query)

@pytest.mark.asyncio
async def test_local_business_search_query_command_injection():
    from servers.local_search_server import server
    with patch.object(server, "GOOGLE_MAPS_API_KEY", "dummy_key"):
        malicious_query = "dentist Austin; cat /etc/passwd"
        with pytest.raises(ValueError, match="Query contains invalid characters"):
            await local_business_search(malicious_query)

@pytest.mark.asyncio
async def test_local_business_search_query_sql_injection():
    from servers.local_search_server import server
    with patch.object(server, "GOOGLE_MAPS_API_KEY", "dummy_key"):
        malicious_query = "dentist' OR '1'='1"
        with pytest.raises(ValueError, match="Query contains invalid characters"):
            await local_business_search(malicious_query)

@pytest.mark.asyncio
async def test_local_business_search_missing_api_key():
    from servers.local_search_server import server
    with patch.object(server, "GOOGLE_MAPS_API_KEY", ""):
        with pytest.raises(ValueError, match="Google Maps API key is not configured"):
            await local_business_search("dentist Austin")
