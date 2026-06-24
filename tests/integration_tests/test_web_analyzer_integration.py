import json
import pytest
from unittest.mock import patch, AsyncMock
from servers.web_analyzer_server.server import web_page_fetcher, tech_footprint_scanner, seo_auditor

@pytest.mark.asyncio
async def test_integrated_web_analyzer_flow():
    html_mock = """
    <html>
      <head>
        <title>Integration Title</title>
        <meta name="description" content="Description"/>
        <meta name="generator" content="WordPress 6.2"/>
      </head>
      <body>
        <h1>Headline</h1>
      </body>
    </html>
    """
    with patch("servers.web_analyzer_server.server.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (200, html_mock)
        
        # 1. Test page fetcher
        fetch_res = await web_page_fetcher("http://example.com/page")
        fetch_data = json.loads(fetch_res)
        assert fetch_data["status"] == 200
        assert "Headline" in fetch_data["content"]
        
        # 2. Test tech footprint
        tech_res = await tech_footprint_scanner("http://example.com/page")
        tech_data = json.loads(tech_res)
        assert tech_data["cms"] == "wordpress"
        
        # 3. Test SEO audit
        seo_res = await seo_auditor("http://example.com/page")
        seo_data = json.loads(seo_res)
        assert seo_data["seo_data"]["meta_title"] == "Integration Title"
        assert seo_data["seo_data"]["h1_elements"] == ["Headline"]
