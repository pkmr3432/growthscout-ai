# Examples: Opportunity Scoring Skill

## Example Run Trajectory

### Input
*   `opportunity_categories`:
    ```json
    [
      {"category_name": "Performance Opportunity", "description": "Mobile load time: 6.8 seconds"},
      {"category_name": "SEO Opportunity", "description": "Missing schema markups"}
    ]
    ```
*   `audit_results`:
    ```json
    {
      "page_load_time_seconds": 6.8,
      "schema_org_tags_found": []
    }
    ```
*   `competitor_profiles`:
    ```json
    [
      {"competitor_name": "Fast Competitor LLC", "page_load_time_seconds": 1.2}
    ]
    ```

### Agent Execution Log
1.  **Assess Evidence Completeness**:
    *   Target website was crawled successfully (page_load_time_seconds available).
    *   SEO tags and sitemaps audited.
    *   Competitor profiles and comparison benchmark data available.
    *   Result: Evidence is complete. Set `confidence_score` to `"High"`.
2.  **Calculate Score**:
    *   Performance Opportunity weight: `45` (based on slow 6.8s load time vs. competitor's 1.2s).
    *   SEO Opportunity weight: `20` (missing schema).
    *   Combined weighted score: `82` out of 100.
3.  **Cite Evidence & Justify Confidence**:
    *   Confidence is "High" because target site analysis was fully executed, SEO audit is complete, and competitor comparisons are available.
4.  **Format Output**:
    ```json
    {
      "opportunity_score": 82,
      "confidence_score": "High",
      "confidence_reasoning": "Confidence is High because the target website was successfully crawled and analyzed, yielding concrete speed metrics (6.8s load time), and a direct competitor comparison profile was established.",
      "evidence_citation": "Verified mobile load time of 6.8s (exceeds 5.0s threshold and competitor speed) and missing LocalBusiness Schema in crawler html tags."
    }
    ```
