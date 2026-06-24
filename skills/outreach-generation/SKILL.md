# Skill: Outreach Generation

## Description
Generates personalized cold email templates and social outreach scripts based on business audit outcomes.

## Schema Contracts

### Inputs
*   `business_name` (string, required)
*   `website_url` (string, required)
*   `opportunities` (array of strings, required)
*   `tone` (string, optional): "consultative", "assertive", "casual". Defaults to "consultative".

### Outputs
*   `subject_line` (string)
*   `body_text` (string)

### Tool Dependencies
None (Pure reasoning skill)
