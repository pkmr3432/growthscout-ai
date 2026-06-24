# Skill: Opportunity Scoring

## Description
Calculates a transparent, explainable Opportunity Score prioritizing leads based on category severity, competitive comparisons, and verified evidence.

## Schema Contracts

### Inputs
*   `opportunity_categories` (array of objects, required): The classified opportunity categories.
*   `audit_results` (object, required): Verified website crawler audit findings.
*   `competitor_profiles` (array, optional): Benchmarked competitor metrics.

### Outputs
*   `opportunity_score` (integer): Value from 0 to 100.
*   `confidence_score` (string): "High", "Medium", or "Low" derived from evidence completeness.
*   `confidence_reasoning` (string): Explanation of confidence score derived from completeness heuristics.
*   `evidence_citation` (string): Specific tool outputs and logs cited.

### Tool Dependencies
None (Pure reasoning skill)
