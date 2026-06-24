# Examples: Business Impact Analysis Skill

## Example Run Trajectory

### Input
*   category_name: `"Performance Opportunity"`
*   technical_finding: `"Mobile load time: 6.8 seconds"`

### Agent Execution Log
1.  **Analyze Finding**:
    *   Technical parameter is a 6.8s load time.
    *   This exceeds the 5.0s critical speed threshold.
    *   Business consequence: Page bounce rates increase for mobile visitors.
2.  **Format Output**:
    ```json
    {
      "business_consequence": "Potential conversion loss due to mobile bounce rates. Over 53% of mobile visits are abandoned if loading takes more than 3 seconds."
    }
    ```
