import sys
import json
import re
import socket
import ipaddress
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
from servers.web_analyzer_server.config import (
    logger, SCRAPER_USER_AGENT, SCRAPER_RATE_LIMIT_DELAY, 
    TIMEOUT_SECONDS, MAX_PAYLOAD_SIZE, MAX_URL_LENGTH, ALLOWED_SCHEMES
)

# Instantiate FastMCP server
mcp = FastMCP("web_analyzer_server")

def validate_url_security(url: str) -> None:
    """Security helper to validate URL size and prevent SSRF attacks."""
    if len(url) > MAX_URL_LENGTH:
        logger.error("Security validation failure: URL exceeds length limit.")
        raise ValueError(f"URL length must not exceed {MAX_URL_LENGTH} characters.")
        
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ALLOWED_SCHEMES:
        logger.error(f"Security validation failure: Scheme {parsed_url.scheme} is forbidden.")
        raise ValueError(f"URL scheme must be one of {ALLOWED_SCHEMES}.")
        
    # Resolve host to verify IP address boundaries (SSRF Protection)
    try:
        hostname = parsed_url.hostname
        if not hostname:
            raise ValueError("Invalid URL hostname.")
            
        try:
            ip = ipaddress.ip_address(hostname)
            ip_address = str(ip)
        except ValueError:
            ip_address = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_address)
            
        # Blacklist private subnets, loopbacks, and link-locals
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            logger.error(f"Security validation failure: SSRF target '{ip_address}' blocked.")
            raise ValueError("SSRF protection: Target IP address is restricted.")
            
    except socket.gaierror:
        logger.warning(f"Could not resolve host: {parsed_url.hostname}. Continuing validation.")

_global_http_client = None

def get_http_client() -> httpx.AsyncClient:
    global _global_http_client
    if _global_http_client is None:
        headers = {"User-Agent": SCRAPER_USER_AGENT}
        _global_http_client = httpx.AsyncClient(headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=True)
    return _global_http_client

async def fetch_page(url: str) -> tuple[int, str]:
    """Helper to fetch webpage content with robots.txt parsing and payload size validation."""
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
    
    client = get_http_client()
    # Check robots.txt compliance
    allowed = True
    try:
        robots_res = await client.get(robots_url, timeout=5.0)
        if robots_res.status_code == 200:
            rp = RobotFileParser()
            rp.parse(robots_res.text.splitlines())
            allowed = rp.can_fetch(SCRAPER_USER_AGENT, url)
    except Exception as e:
        logger.warning(f"Failed to fetch robots.txt for {url}: {str(e)}. Defaulting to allowed.")
        
    if not allowed:
        logger.warning(f"Robots.txt Disallowed fetch for URL: {url}")
        return 403, "Robots.txt Blocked"
        
    # Stream response to enforce size limits
    try:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                return response.status_code, ""
                
            content_chunks = []
            bytes_read = 0
            async for chunk in response.aiter_text():
                content_chunks.append(chunk)
                bytes_read += len(chunk.encode("utf-8"))
                if bytes_read > MAX_PAYLOAD_SIZE:
                    logger.error(f"Payload size limit exceeded for URL: {url}")
                    raise ValueError("Target website payload size exceeded 2MB limit.")
                    
            return response.status_code, "".join(content_chunks)
    except httpx.TimeoutException:
        logger.error(f"Request timeout for URL: {url}")
        raise TimeoutError("Target website request timed out.")
    except Exception as e:
        logger.error(f"Request failed for URL: {url}: {str(e)}")
        return 500, f"Request failed: {str(e)}"

def detect_tech_stack(html: str) -> str:
    """Helper to detect CMS and UI framework using evidence-based heuristics."""
    html_lower = html.lower()
    
    # 1. Parsing with BS4 to inspect generator tags cleanly
    try:
        soup = BeautifulSoup(html, "html.parser")
        generator = soup.find("meta", attrs={"name": "generator"})
        if generator:
            gen_content = generator.get("content", "").lower()
            if "wordpress" in gen_content:
                return "wordpress"
            if "wix" in gen_content:
                return "wix"
            if "shopify" in gen_content:
                return "shopify"
            if "squarespace" in gen_content:
                return "squarespace"
    except Exception as e:
        logger.warning(f"Failed to parse generator tags with bs4: {str(e)}")
    
    # 2. String fallback checks
    if "wp-content" in html_lower or "wp-includes" in html_lower:
        return "wordpress"
    if "cdn.shopify.com" in html_lower or "shopify.theme" in html_lower:
        return "shopify"
    if "wix-static" in html_lower or "wixsite.com" in html_lower:
        return "wix"
    if "static1.squarespace.com" in html_lower or "squarespace" in html_lower:
        return "squarespace"
        
    # Framework Checks
    if "__next_data__" in html_lower or "_next/static" in html_lower:
        return "next.js"
    if "react.production" in html_lower or "data-reactroot" in html_lower or "id=\"root\"" in html_lower:
        return "react"
    if "vue" in html_lower or "data-v-" in html_lower:
        return "vue"
    if "ng-version" in html_lower or "_ngcontent-" in html_lower:
        return "angular"
        
    return "custom"

def detect_booking_widget(html: str) -> bool:
    """Helper to detect popular scheduling widgets."""
    html_lower = html.lower()
    booking_domains = ["calendly.com", "acuityscheduling.com", "appointlet", "bookafy", "scheduling"]
    return any(domain in html_lower for domain in booking_domains)

@mcp.tool()
async def web_page_fetcher(url: str) -> str:
    """Crawls a target website domain and retrieves raw content while adhering to robots.txt."""
    logger.info(f"Received web_page_fetcher request for URL: {url}")
    validate_url_security(url)
    
    status, content = await fetch_page(url)
    
    response_data = {
        "status": status,
        "content": content if status == 200 else None
    }
    return json.dumps(response_data)

@mcp.tool()
async def tech_footprint_scanner(url: str) -> str:
    """Detects CMS, framework, load time, and booking widgets on a domain."""
    logger.info(f"Received tech_footprint_scanner request for URL: {url}")
    validate_url_security(url)
    
    start_time = time.time()
    status, content = await fetch_page(url)
    load_time = time.time() - start_time
    
    if status != 200:
        logger.error(f"Cannot scan tech footprint, HTTP fetch failed with status {status}")
        raise RuntimeError(f"HTTP fetch failed with status {status}")
        
    cms = detect_tech_stack(content)
    has_booking = detect_booking_widget(content)
    
    response_data = {
        "cms": cms,
        "load_time_seconds": round(load_time, 2),
        "has_booking_widget": has_booking
    }
    return json.dumps(response_data)

@mcp.tool()
async def seo_auditor(url: str) -> str:
    """Parses on-page titles, descriptions, headings, and schema markups for a domain."""
    logger.info(f"Received seo_auditor request for URL: {url}")
    validate_url_security(url)
    
    status, content = await fetch_page(url)
    if status != 200:
        logger.error(f"Cannot perform SEO audit, HTTP fetch failed with status {status}")
        raise RuntimeError(f"HTTP fetch failed with status {status}")
        
    soup = BeautifulSoup(content, "html.parser")
    
    # Extract Meta Title
    title_tag = soup.find("title")
    meta_title = title_tag.get_text().strip() if title_tag else None
    if not meta_title:
        og_title = soup.find("meta", property="og:title")
        meta_title = og_title.get("content").strip() if og_title else None
        
    # Extract Meta Description
    desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = desc_tag.get("content").strip() if desc_tag else None
    if not meta_description:
        og_desc = soup.find("meta", property="og:description")
        meta_description = og_desc.get("content").strip() if og_desc else None
        
    # Extract H1 elements
    h1_elements = [h1.get_text().strip() for h1 in soup.find_all("h1") if h1.get_text().strip()]
    
    # Detect Schema Markup
    has_schema_markup = False
    ld_json = soup.find("script", type="application/ld+json")
    if ld_json:
        has_schema_markup = True
    else:
        if soup.find(attrs={"itemscope": True}):
            has_schema_markup = True
            
    response_data = {
        "seo_data": {
            "meta_title": meta_title,
            "meta_description": meta_description,
            "h1_elements": h1_elements,
            "has_schema_markup": has_schema_markup
        }
    }
    return json.dumps(response_data)

if __name__ == "__main__":
    mcp.run()
