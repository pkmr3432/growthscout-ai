# Grounding Policy: GrowthScout AI Worker Agents

To prevent hallucinations and guarantee the integrity of all growth reports, all worker agents must adhere to the following grounding policies:

1.  **Zero Invention of Presence Data**:
    *   You must not invent or assume websites, ratings, review counts, CMS frameworks, or SEO titles that are not present in the tool outputs.
    *   If a local business has no website listed in the Maps results, you must handle it strictly under the "No Website" classification, skip all scraping checks, and limit your analysis to geographical and reputation metadata.

2.  **Strict Data Adherence**:
    *   All opportunity calculations, scores, and comparisons must be calculated using only the data objects supplied in the input context.
    *   Do not leverage general model pre-training knowledge to assume custom details about specific local businesses.

3.  **Aborting on Missing Evidence**:
    *   If core verification evidence (e.g. audit results) is missing or unverified, you must abort score calculations for that specific category and flag the lack of verified data.
