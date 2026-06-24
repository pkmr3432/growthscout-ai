# Examples: SEO Audit Skill

## Example Run Trajectory

### Input
*   raw_html: `"<html><head><title>Best Plumber Austin</title><meta name='description' content='Fast plumbing repair services.'></head><body><h1>Austin Plumber</h1></body></html>"`

### Agent Execution Log
1.  **Parse HTML metadata**:
    *   Find `<title>`: `"Best Plumber Austin"`
    *   Find `<meta name='description'>`: `"Fast plumbing repair services."`
    *   Find `<h1>`: `["Austin Plumber"]`
    *   Search for ld+json schema blocks: Not found.
2.  **Format Output**:
    ```json
    {
      "seo_data": {
        "meta_title": "Best Plumber Austin",
        "meta_description": "Fast plumbing repair services.",
        "h1_elements": ["Austin Plumber"],
        "has_schema_markup": false
      }
    }
    ```
