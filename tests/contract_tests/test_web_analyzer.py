import json
import pytest
from unittest.mock import patch, AsyncMock
from servers.web_analyzer_server.server import web_page_fetcher, tech_footprint_scanner, seo_auditor

@pytest.mark.asyncio
async def test_web_page_fetcher_contract():
    with patch("servers.web_analyzer_server.server.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (200, "<html><body><h1>Hello</h1></body></html>")
        
        response = await web_page_fetcher("http://example.com")
        data = json.loads(response)
        
        assert "status" in data
        assert "content" in data
        assert data["status"] == 200
        assert "Hello" in data["content"]

@pytest.mark.asyncio
async def test_tech_footprint_scanner_contract():
    # WordPress detect
    html = "<html><head><meta name='generator' content='WordPress 6.2'/></head><body><a href='https://calendly.com/test'>Book</a></body></html>"
    with patch("servers.web_analyzer_server.server.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (200, html)
        
        response = await tech_footprint_scanner("http://example.com")
        data = json.loads(response)
        
        assert "cms" in data
        assert "load_time_seconds" in data
        assert "has_booking_widget" in data
        assert data["cms"] == "wordpress"
        assert data["has_booking_widget"] is True

@pytest.mark.asyncio
async def test_seo_auditor_contract():
    html = """
    <html>
      <head>
        <title>Example Page Title</title>
        <meta name="description" content="Example description metadata."/>
        <script type="application/ld+json">{"@context": "https://schema.org"}</script>
      </head>
      <body>
        <h1>H1 Heading 1</h1>
        <h1>H1 Heading 2</h1>
      </body>
    </html>
    """
    with patch("servers.web_analyzer_server.server.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (200, html)
        
        response = await seo_auditor("http://example.com")
        data = json.loads(response)
        
        assert "seo_data" in data
        seo = data["seo_data"]
        assert seo["meta_title"] == "Example Page Title"
        assert seo["meta_description"] == "Example description metadata."
        assert seo["h1_elements"] == ["H1 Heading 1", "H1 Heading 2"]
        assert seo["has_schema_markup"] is True
