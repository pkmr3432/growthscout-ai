# Agent Skill Architecture: GrowthScout AI

This document defines the reusable agent skill model, package specifications, dynamic binding protocols, and testing frameworks that govern capabilities in GrowthScout AI.

---

## 1. What is a Skill Package?
A Skill Package represents an isolated, reusable competence that can be dynamically bound to any agent. In alignment with Agentic Engineering, skills are decoupled from both agent persona prompts and backend infrastructure code.

Each Skill Package must be placed under the `skills/` directory and must contain exactly three files:
1.  **`SKILL.md`**: The declaration file. It specifies the skill's name, description, required input parameters (YAML schema), expected output format, and required MCP tools.
2.  **`examples.md`**: Illustrative multi-turn conversation logs and step trajectories demonstrating correct skill execution.
3.  **`evaluation_cases.json`**: An evaluation-first mock dataset mapping target prompts to expected structured outputs, used for regression checks.

```
skills/
└── <skill-package-name>/
    ├── SKILL.md                 # Manifest, inputs, outputs, tool bindings
    ├── examples.md              # Target run trajectories (examples)
    └── evaluation_cases.json    # Standard JSON test cases
```

To ensure governance and factual integrity, all skills must satisfy:
*   **Explainability**: Every calculation, assessment, or recommendation must be accompanied by supporting reasoning.
*   **Evidence Citation**: Outputs must explicitly cite the MCP tool logs or audit results that influenced the outcome.
*   **Constitution Compliance**: All generated outputs must connect technical data to business impact, redaction schemas, and security gates.

---

## 2. Directory Matrix & Core Skills

| Skill Directory | Core Purpose | Tool Dependencies | Internal Dependencies |
| :--- | :--- | :--- | :--- |
| `business-discovery` | Translates user prompts into localized business queries, discovers target leads and competitor candidates. | `local_business_search` | None |
| `website-analysis` | Fetches target and competitor page HTML, parses robots.txt compliance. | `web_page_fetcher` | None |
| `seo-audit` | Audits page tags, headings, schema configurations, and web performance metrics for targets and competitors. | `seo_auditor` | None |
| `competitor-analysis` | Benchmarks target business performance against top competitor candidates. | None (Pure reasoning) | Discovery data, website analysis results, SEO audit results, and competitor audit results. |
| `opportunity-classification` | Assigns identified presence gaps strictly to the 8 formal Opportunity Categories. | None (Pure reasoning) | Website and competitor analysis results. |
| `opportunity-scoring` | Prioritizes opportunities, calculates explainable scores (0-100), and computes confidence levels. | None (Pure reasoning) | Opp classification metrics. |
| `business-impact-analysis` | Maps technical findings directly to business consequences (e.g. lost traffic, low conversion). | None (Pure reasoning) | Opp classification metrics. |
| `growth-report-generation` | Compiles findings, scores, and competitive benchmarks into a master Growth Intelligence Report. | None (Pure reasoning) | Scores, competitor profiles, and impact analyses. |
| `outreach-generation` | Writes tailored email and LinkedIn outreach copy derived from report findings. | None (Pure reasoning) | Growth report summaries. |
| `local-business-research` | Collects maps details, reviews, address validation, and contact coordinates. | `local_business_search` | None |

---

## 3. Dynamic Skill Binding (The Manifest)
Agents bind to skills via the master `agents/agents-cli-manifest.yaml`. At start time, the ADK framework loads the declared skills, reads their prompts and tool contracts, and attaches them to the agent's LLM context window.

Example Agent manifest linking to skills:
```yaml
agent:
  name: "website_analysis_agent"
  skills:
    - "skills/website-analysis"
    - "skills/seo-audit"
```

---

## 4. Skill Evaluation & Quality Gates

To enforce Evaluation-First Development, each skill has defined evaluation objectives, success criteria, and quality gates:

### 4.1 business-discovery
*   **Evaluation Objective**: Identify targets and competitor candidates matching vertical niche and city coordinates.
*   **Success Criteria**: Retrieval rate of >= 3 leads and >= 3 competitors per valid query.
*   **Quality Gate**: Zero formatting text in outputs; must validate against JSON array schema.

### 4.2 website-analysis
*   **Evaluation Objective**: Crawl websites while obeying crawler speed limits and robots.txt.
*   **Success Criteria**: Correctly classify robots.txt allowance (100% accuracy).
*   **Quality Gate**: Handle redirects and 404 errors gracefully without throwing runtime execution exceptions.

### 4.3 seo-audit
*   **Evaluation Objective**: Extract HTML titles, meta descriptions, and schema blocks.
*   **Success Criteria**: Extracted metadata matches ground truth values exactly.
*   **Quality Gate**: Hallucination rate = 0.00 (Zero generation of tags not present in raw HTML).

### 4.4 competitor-analysis
*   **Evaluation Objective**: Compare ratings, review counts, and SEO metrics between targets and competitors.
*   **Success Criteria**: Market average rating and review benchmarks calculated with mathematical precision.
*   **Quality Gate**: Grounded comparison matrix matching input list.

### 4.5 opportunity-classification
*   **Evaluation Objective**: Assign gaps to the 8 formal categories defined in the PRD.
*   **Success Criteria**: Classification accuracy >= 95% against golden datasets.
*   **Quality Gate**: Category strings must validate exactly against approved PRD categories.

### 4.6 opportunity-scoring
*   **Evaluation Objective**: Compute transparent scores prioritizing opportunities, along with confidence assessments.
*   **Success Criteria**: Calculated Opportunity Scores match the target valuation heuristics.
*   **Quality Gate**: 
    *   Explanation details must cite the exact tool logs that influenced the score.
    *   Every opportunity score must include confidence reasoning.
    *   Scores without confidence justification must fail evaluation.
*   **Output Schema Extensions**:
    In addition to generating an `opportunity_score`, the skill must also produce:
    ```yaml
    opportunity_score:
    confidence_score:
    confidence_reasoning:
    ```
*   **Confidence Determination Heuristics**:
    Confidence must be derived from evidence completeness:
    *   **High**:
        *   Website successfully analyzed
        *   SEO audit completed
        *   Competitor comparison available
    *   **Medium**:
        *   Partial website analysis available
        *   Limited competitor data
    *   **Low**:
        *   Missing audit data
        *   Incomplete tool execution

### 4.7 business-impact-analysis
*   **Evaluation Objective**: Connect technical gaps to business consequences.
*   **Success Criteria**: Output maps 100% of detected gaps to lost revenue, traffic, or conversion opportunities.
*   **Quality Gate**: Opaque or technical jargon-only explanations without outcome mapping are blocked.

### 4.8 growth-report-generation
*   **Evaluation Objective**: Synthesize primary Growth Intelligence Reports.
*   **Success Criteria**: Generated report includes summary, findings, competitive benchmarks, opportunity scores, and recommendations.
*   **Quality Gate**: 
    *   `final_response_quality` metric score >= 0.82.
    *   Every recommendation must reference one or more supporting findings from:
        *   `audit_results`
        *   `competitor_profiles`
        *   `opportunity_scores`
        *   `business_impact_analysis`
    *   Recommendations without supporting evidence must be rejected.
    *   Reports must clearly distinguish:
        *   Verified findings
        *   Inferred findings
        *   Unknown or unavailable findings
    *   The Growth Intelligence Report must maintain traceability from evidence → business impact → opportunity score → recommendation.

### 4.9 outreach-generation
*   **Evaluation Objective**: Draft cold outreach messages derived from the primary report.
*   **Success Criteria**: Applied AIDA framework (Attention, Interest, Desire, Action) and requested tone.
*   **Quality Gate**: Customer PII masked with redaction tokens.

### 4.10 local-business-research
*   **Evaluation Objective**: Validate Maps address and phone parameters.
*   **Success Criteria**: Place metadata matches Maps result fields.
*   **Quality Gate**: Verification of address formats.

---

## 5. Skill Lifecycle & Compilation
The migration of a skill from design to production follows a strict lifecycle:

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│ 1. Spec Out │ ──> │ 2. Mock Test │ ──> │ 3. Code Bind │ ──> │ 4. Evaluate │
│  (SKILL.md) │     │ (examples.md)│     │  (MCP Tools) │     │(eval-cases) │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
```

1.  **Specification**: Create `SKILL.md` declaring inputs, outputs, and safety boundaries.
2.  **Mocking Examples**: Add step-by-step traces to `examples.md` to guide prompt optimization.
3.  **MCP Binding**: Map the skill to active MCP schemas in `mcp/schemas/`.
4.  **Harness Evaluation**: Rerun `agents-cli eval run` using the cases in `evaluation_cases.json` to verify accuracy before releasing to staging.

---

# 6. Skill Ownership Matrix

Document the authoritative mapping between agents and skills.

| Agent | Skills |
| --- | --- |
| Business Discovery Agent | business-discovery, local-business-research |
| Website Analysis Agent | website-analysis, seo-audit |
| Opportunity Agent | competitor-analysis, opportunity-classification, opportunity-scoring, business-impact-analysis |
| Growth Intelligence Agent | growth-report-generation, outreach-generation |
| Orchestrator Agent | No direct skills; routing and workflow management only |

Requirements:
* This matrix is the single source of truth for agent-to-skill assignments.
* Agent definitions, manifests, evaluations, and workflow specifications must remain consistent with this matrix.
* Any future skill assignment changes must be reflected here first before implementation changes are permitted.
