# Skill: Competitor Analysis

## Description
Performs a comparative maps lookup to compare the target business's review scores and metrics against top competitors in the same geographic region.

## Schema Contracts

### Inputs
*   `niche` (string, required): Business vertical category.
*   `location` (string, required): Geographic city.
*   `target_rating` (number, required): Rating score of the target lead.
*   `target_review_count` (integer, required): Review count of the target lead.

### Outputs
*   `competitors` (array of objects):
    *   `business_name` (string)
    *   `google_rating` (number)
    *   `review_count` (integer)
*   `is_below_market_average` (boolean)

### Tool Dependencies
*   `local_business_search`
