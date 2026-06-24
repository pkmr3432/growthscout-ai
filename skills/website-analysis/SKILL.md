# Skill: Website Analysis

## Description
Crawls a target website domain to extract basic site configuration logs and check robots.txt compliance.

## Schema Contracts

### Inputs
*   `website_url` (string, required): Domain target URL.

### Outputs
*   `robots_status` (string): "Allowed" or "Blocked"
*   `raw_html` (string, null if blocked or failed)
*   `http_response_code` (integer)

### Tool Dependencies
*   `web_page_fetcher`
