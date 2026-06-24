# Examples: Competitor Analysis Skill

## Example Run Trajectory

### Input
*   niche: `"chiropractor"`
*   location: `"Denver, CO"`
*   target_rating: `4.1`
*   target_review_count: `12`

### Agent Execution Log
1.  **Tool Call**:
    *   Invocation: `local_business_search(query="chiropractor Denver CO")`
    *   Tool Response:
        ```json
        {
          "results": [
            {"name": "Denver Chiropractic Center", "rating": 4.9, "user_ratings_total": 310},
            {"name": "Mile High Spine", "rating": 4.7, "user_ratings_total": 140}
          ]
        }
        ```
2.  **Calculate Average**:
    *   Market Average Rating: `4.8`
    *   Market Average Reviews: `225`
    *   Comparison: Target lead rating (`4.1`) and reviews (`12`) are below average.
3.  **Format Output**:
    ```json
    {
      "competitors": [
        {"business_name": "Denver Chiropractic Center", "google_rating": 4.9, "review_count": 310},
        {"business_name": "Mile High Spine", "google_rating": 4.7, "review_count": 140}
      ],
      "is_below_market_average": true
    }
    ```
