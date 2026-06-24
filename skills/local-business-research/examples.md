# Examples: Local Business Research Skill

## Example Run Trajectory

### Input
*   business_name: `"Miami Pipe Masters"`
*   location: `"Miami, FL"`

### Agent Execution Log
1.  **Tool Call**:
    *   Invocation: `local_business_search(query="Miami Pipe Masters Miami FL")`
    *   Tool Response:
        ```json
        {
          "results": [
            {
              "name": "Miami Pipe Masters",
              "formatted_phone_number": "+1 305-555-0199",
              "formatted_address": "800 Biscayne Blvd, Miami, FL 33132",
              "reviews": [
                {"author_name": "John Doe", "text": "Great speed!", "rating": 5}
              ]
            }
          ]
        }
        ```
2.  **Format Output**:
    ```json
    {
      "phone": "+1 305-555-0199",
      "address": "800 Biscayne Blvd, Miami, FL 33132",
      "reviews": [
        {"author_name": "John Doe", "text": "Great speed!", "rating": 5}
      ]
    }
    ```
