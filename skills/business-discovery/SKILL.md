# Skill: Business Discovery

## Description
Finds local businesses within a target geographic location and niche vertical.

## Schema Contracts

### Inputs
*   `niche` (string, required): Business vertical search category (e.g. "chiropractor").
*   `location` (string, required): Geography search query (e.g. "Seattle, WA").
*   `max_results` (integer, optional): Maximum businesses to retrieve. Defaults to 5.

### Outputs
*   `leads` (array of objects):
    *   `business_name` (string)
    *   `address` (string)
    *   `website_url` (string, null if missing)
    *   `website_status` (string): "No Website", "Outdated Website", or "Modern Website"
    *   `google_rating` (number)
    *   `review_count` (integer)


### Tool Dependencies
*   `local_business_search`
