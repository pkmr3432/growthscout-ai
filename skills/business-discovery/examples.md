# Examples: Business Discovery Skill

## Example Run Trajectory

### User Request
"Find plumbers in Miami, Florida."

### Agent Execution Log
1.  **Read Inputs**:
    *   niche: `"plumbing"`
    *   location: `"Miami, FL"`
2.  **Tool Call**:
    *   Invocations: `local_business_search(query="plumbers Miami FL")`
    *   Tool Response:
        ```json
        {
          "results": [
            {
              "name": "Miami Pipe Masters",
              "formatted_address": "800 Biscayne Blvd, Miami, FL 33132",
              "website": "https://miamipipemasters.com",
              "rating": 4.8,
              "user_ratings_total": 120
            },
            {
              "name": "Quick Fix Plumbing",
              "formatted_address": "150 SE 2nd Ave, Miami, FL 33131",
              "website": null,
              "rating": 4.2,
              "user_ratings_total": 45
            }
          ]
        }
        ```
3.  **Process and Classify**:
    *   "Quick Fix Plumbing" has no website URL; its status is marked as "No Website" and it is assigned the "No Website Opportunity" category.
    *   "Miami Pipe Masters" has a website URL; its status is marked as "Modern Website" or "Outdated Website" pending auditing.
4.  **Format Output**:
    ```json
    {
      "leads": [
        {
          "business_name": "Miami Pipe Masters",
          "address": "800 Biscayne Blvd, Miami, FL 33132",
          "website_url": "https://miamipipemasters.com",
          "website_status": "Modern Website",
          "google_rating": 4.8,
          "review_count": 120
        },
        {
          "business_name": "Quick Fix Plumbing",
          "address": "150 SE 2nd Ave, Miami, FL 33131",
          "website_url": null,
          "website_status": "No Website",
          "google_rating": 4.2,
          "review_count": 45
        }
      ]
    }
    ```

