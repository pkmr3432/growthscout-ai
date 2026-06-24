# Examples: Growth Report Generation Skill

## Example Run Trajectory

### Input
*   `business_name`: `"Miami Pipe Masters"`
*   `website_url`: `"https://miamipipemasters.com"`
*   `audit_results`:
    ```json
    {
      "page_load_time_seconds": 6.8,
      "meta_title": "Miami Pipe Masters - Local Plumber",
      "google_analytics_detected": false
    }
    ```
*   `opportunity_scores`: 
    ```yaml
    opportunity_score: 82
    confidence_score: "High"
    confidence_reasoning: "High confidence due to successful website crawler audits and available competitor benchmark profiles."
    ```
*   `business_impact_analysis`:
    ```json
    {
      "Performance Opportunity": "Estimated 30% traffic bounce due to 6.8s load time.",
      "Analytics Opportunity": "Inability to track conversion path or traffic metrics from local campaigns."
    }
    ```
*   `competitor_profiles`:
    ```json
    [
      {"name": "Miami Express Plumbing", "page_load_time_seconds": 1.5, "google_analytics_detected": true}
    ]
    ```

### Agent Execution Log
1.  **Enforce Traceability**: Map `audit_results` (evidence) → `business_impact_analysis` (impact) → `opportunity_scores` (score) → recommendations.
2.  **Distinguish Finding Types**:
    *   *Verified findings*: Speed (6.8s), Missing Google Analytics script (both directly verified via crawler tools).
    *   *Inferred findings*: Bounced visitor estimates and market gap relative to Miami Express Plumbing.
    *   *Unknown or unavailable findings*: Exact AdWords conversion rates (tools couldn't access private ad accounts).
3.  **Generate Markdown sections**: Produce the complete Growth Intelligence Report Markdown.
4.  **Format Output**:
    ```json
    {
      "growth_report_markdown": "# Growth Intelligence Report: Miami Pipe Masters\n\n## 1. Executive Summary\nMiami Pipe Masters has a strong local presence but is experiencing digital drag due to slow site loading and unmonitored visitor traffic.\n\n## 2. Evidence & Findings\n*   **Verified Findings (Grounded)**:\n    *   Target site load time is 6.8s (Source: `audit_results`).\n    *   Google Analytics script is missing (Source: `audit_results`).\n*   **Inferred Findings (Calculated)**:\n    *   Estimated 30% visitor bounce rate (Source: `business_impact_analysis`).\n    *   Speed gap of 5.3s compared to direct competitor Miami Express Plumbing (Source: `competitor_profiles`).\n*   **Unknown or Unavailable Findings**:\n    *   Search console click-through rate statistics (private account access required).\n\n## 3. Prioritized Recommendations\n*   **Recommendation 1: Optimize mobile page speed to under 2.0s**\n    *   *Supporting Findings*: Verified site speed of 6.8s (`audit_results`), competitor average of 1.5s (`competitor_profiles`), and bounce rate impact (`business_impact_analysis`).\n    *   *Priority*: High (Opportunity Score: 82)"
    }
    ```
