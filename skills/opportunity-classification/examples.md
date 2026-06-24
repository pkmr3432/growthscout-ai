# Examples: Opportunity Classification Skill

## Example Run Trajectory

### Input
*   detected_gaps: `["no_analytics_script", "slow_loading_mobile"]`

### Agent Execution Log
1.  **Read Gaps**:
    *   `"no_analytics_script"` maps to `"Analytics Opportunity"`.
    *   `"slow_loading_mobile"` maps to `"Performance Opportunity"`.
2.  **Format Output**:
    ```json
    {
      "opportunity_categories": [
        {
          "category_name": "Analytics Opportunity",
          "description": "Missing tag managers or GA4 scripts."
        },
        {
          "category_name": "Performance Opportunity",
          "description": "Website takes over 5 seconds to load on mobile."
        }
      ]
    }
    ```
