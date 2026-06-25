# Evidence Policy: GrowthScout AI Worker Agents

All opportunity scores, lead scores, growth assessments, and business recommendations must comply with the following evidence policies:

1.  **Tool Output Citations**:
    *   Every finding, opportunity, and score must cite the specific tool output or data source that verified the finding (e.g. citing `seo_auditor` for a missing title tag, or `tech_footprint_scanner` for a missing booking widget).
    *   Do not report any technical presence error or gap without referencing the tool execution that confirmed it.

2.  **Explainability**:
    *   Explain the business consequence of why a recommendation or score was generated.
    *   Always connect technical failures (e.g. slow load time) directly to measurable business impacts (e.g. increased visitor bounce rates and lost leads).

3.  **Fact vs. Assumption Separation**:
    *   Explicitly distinguish verified findings (directly grounded in tool outputs) from assumptions (e.g. assuming a lead has no booking widget because none was detected during scraping, or assuming standard conversion rates).

4.  **Incompleteness Reporting**:
    *   If evidence is incomplete, or a tool run failed, explicitly state that the finding is unverified or that tool limits prevented verification. Do not fill in missing data with LLM inference assumptions.
