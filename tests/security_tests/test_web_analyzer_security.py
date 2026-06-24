import pytest
from unittest.mock import patch, AsyncMock
from servers.web_analyzer_server.server import web_page_fetcher

@pytest.mark.asyncio
async def test_web_page_fetcher_url_too_long():
    long_url = "http://example.com/" + "a" * 2048
    with pytest.raises(ValueError, match="URL length must not exceed"):
        await web_page_fetcher(long_url)

@pytest.mark.asyncio
async def test_web_page_fetcher_forbidden_scheme():
    with pytest.raises(ValueError, match="URL scheme must be one of"):
        await web_page_fetcher("ftp://example.com")

@pytest.mark.asyncio
async def test_web_page_fetcher_loopback_blocked():
    with pytest.raises(ValueError, match="SSRF protection: Target IP address is restricted"):
        await web_page_fetcher("http://127.0.0.1")

@pytest.mark.asyncio
async def test_web_page_fetcher_private_ip_blocked():
    with pytest.raises(ValueError, match="SSRF protection: Target IP address is restricted"):
        await web_page_fetcher("http://192.168.1.1")

@pytest.mark.asyncio
async def test_web_page_fetcher_link_local_blocked():
    with pytest.raises(ValueError, match="SSRF protection: Target IP address is restricted"):
        await web_page_fetcher("http://169.254.169.254")

@pytest.mark.asyncio
async def test_web_page_fetcher_dns_rebind_blocked():
    # If the domain resolves to local address, it should be blocked
    with patch("socket.gethostbyname") as mock_resolve:
        mock_resolve.return_value = "10.0.0.1"
        with pytest.raises(ValueError, match="SSRF protection: Target IP address is restricted"):
            await web_page_fetcher("http://my-internal-service.local")
