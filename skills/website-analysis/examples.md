# Examples: Website Analysis Skill

## Example Run Trajectory

### Input
*   website_url: `"https://austinboilerexperts.com"`

### Agent Execution Log
1.  **Check robots.txt**:
    *   Verify robots.txt allow rules for `"https://austinboilerexperts.com"`.
    *   Result: Allowed.
2.  **Tool Call**:
    *   Invocation: `web_page_fetcher(url="https://austinboilerexperts.com")`
    *   Tool Response:
        ```json
        {
          "status": 200,
          "content": "<html><head><title>Boiler Repair - Austin</title></head><body><h1>Boiler Services</h1></body></html>"
        }
        ```
3.  **Format Output**:
    ```json
    {
      "robots_status": "Allowed",
      "raw_html": "<html><head><title>Boiler Repair - Austin</title></head><body><h1>Boiler Services</h1></body></html>",
      "http_response_code": 200
    }
    ```
