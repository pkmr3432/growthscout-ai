# Skill: Business Impact Analysis

## Description
Maps technical findings and presence gaps to direct, explainable business outcomes (e.g. bounce rates, visibility loss).

## Schema Contracts

### Inputs
*   `category_name` (string, required): One of the 8 Opportunity Categories.
*   `technical_finding` (string, required): Specific log detail (e.g. "Mobile load time: 6.8 seconds").

### Outputs
*   `business_consequence` (string): Direct explanation of business return or risk (e.g. "Slow mobile loading bounce rates cause potential conversion loss").

### Tool Dependencies
None (Pure reasoning skill)
