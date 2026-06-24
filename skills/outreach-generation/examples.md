# Examples: Outreach Generation Skill

## Example Run Trajectory

### Input
*   business_name: `"Austin Boiler Experts"`
*   website_url: `"https://austinboilerexperts.com"`
*   opportunities: `["no_booking_widget"]`
*   tone: `"consultative"`

### Agent Execution Log
1.  **Format Hook**:
    *   Hook: "I noticed your site at https://austinboilerexperts.com looks great on desktop, but did you know..."
2.  **Compose Body**:
    *   Pitch: Introduce how a booking widget can increase plumber conversions by 30%.
3.  **Format Output**:
    ```json
    {
      "subject_line": "Idea for Austin Boiler Experts online booking",
      "body_text": "Hi team,\n\nI visited your site and wanted to suggest a quick fix..."
    }
    ```
// 
