# Skill: Opportunity Classification

## Description
Maps identified technical gaps and digital presence footprints into the 8 formal Opportunity Categories.

## Schema Contracts

### Inputs
*   `detected_gaps` (array of strings, required): Raw technical presence gaps (e.g. `['no_analytics_script', 'slow_loading_mobile']`).

### Outputs
*   `opportunity_categories` (array of objects):
    *   `category_name` (string): Must match one of the 8 PRD categories.
    *   `description` (string)

### Tool Dependencies
None (Pure reasoning skill)
