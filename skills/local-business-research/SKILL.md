# Skill: Local Business Research

## Description
Validates and collects maps address coordinates, contact info, and Maps review metadata for specific business entities.

## Schema Contracts

### Inputs
*   `business_name` (string, required)
*   `location` (string, required): Approximate address/city details.

### Outputs
*   `phone` (string, null if missing)
*   `address` (string, null if missing)
*   `reviews` (array of objects):
    *   `author_name` (string)
    *   `text` (string)
    *   `rating` (number)

### Tool Dependencies
*   `local_business_search`
