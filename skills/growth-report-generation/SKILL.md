# Skill: Growth Report Generation

## Description
Compiles technical audits, competitive positioning benchmarks, opportunity scores, and impact analyses into a master Markdown Growth Intelligence Report.

## Schema Contracts

### Inputs
*   `business_name` (string, required)
*   `website_url` (string, null if No Website)
*   `audit_results` (object, required): Raw crawler audit outputs containing evidence.
*   `opportunity_scores` (object, required): Prioritization scores with confidence mappings.
*   `business_impact_analysis` (object, required): Mapped business impact consequences.
*   `competitor_profiles` (array, required): Competitive benchmark metrics.

### Outputs
*   `growth_report_markdown` (string): Structured master report containing verified, inferred, and unknown findings, with fully traceable recommendations.

### Tool Dependencies
None (Pure reasoning skill)
