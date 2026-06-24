# Skill: SEO Audit

## Description
Audits page HTML text for metadata titles, descriptions, headings, and schema markups.

## Schema Contracts

### Inputs
*   `raw_html` (string, required): HTML source page text.

### Outputs
*   `seo_data` (object):
    *   `meta_title` (string, null if missing)
    *   `meta_description` (string, null if missing)
    *   `h1_elements` (array of strings)
    *   `has_schema_markup` (boolean)

### Tool Dependencies
*   `seo_auditor`
