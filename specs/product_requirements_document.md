# Product Requirements Document (PRD): GrowthScout AI

## 1. Executive Summary & Goals
GrowthScout AI is a **Growth Intelligence Platform**, **Business Opportunity Discovery Platform**, and **Digital Presence Analysis Platform** designed for freelance web developers, SEO consultants, and small digital agencies. Rather than functioning as a cold outreach or proposal-generation tool, its primary value is to help creators identify, understand, prioritize, and explain digital growth opportunities to local small and medium-sized businesses (SMBs).

The platform augments human decision-making by converting raw technical audits (site speed, meta tags, and CMS components) into high-value business intelligence. The primary goal is to help consultants solve their own client acquisition problem by identifying local businesses with measurable digital gaps, explaining the business impact of those gaps, and delivering data-backed, evidence-cited recommendations.

---

## 2. Target User Personas
For Version 1 (MVP), GrowthScout AI prioritizes the following initial users:
*   **Freelance Web Developer**: Identifies local businesses with slow loading times, poor mobile UX, or legacy CMS structures. Uses the platform to connect technical debt to business outcomes (e.g., customer bounce rates) to pitch redesign and optimization services.
*   **SEO Consultant**: Evaluates local SMB websites lacking sitemaps, semantic tags, and local schema markups. Uses the platform to pitch local SEO retainers by demonstrating how competitors dominate local search results.
*   **Small Digital Agency Owner**: Analyzes local businesses that lack modern conversions channels (such as online scheduling widgets or lead capture forms). Uses comparative insights to pitch digital transformation packages.

---

## 3. Core Functional Modules

```
┌────────────────────────────────────────────────────────────────────────┐
│                             GROWTHSCOUT AI                             │
├───────────────┬───────────────┬────────────────┬───────────────────────┤
│   Discovery   │   Analysis    │ Opportunities  │ Business Intelligence │
├───────────────┴───────────────┴────────────────┴───────────────────────┤
│                         Competitive Intelligence                       │
└────────────────────────────────────────────────────────────────────────┘
```

### Module A: Local Business Discovery
*   **Req 3.1.1**: The user must be able to search for local businesses by niche/vertical (e.g., "HVAC contractor") and geography (e.g., "Seattle, WA").
*   **Req 3.1.2**: Retrieve business name, phone, address, website URL, Google Maps rating, and review count.
*   **Req 3.1.3**: Classify discovered businesses into:
    *   *No Website*: Businesses with no URL found in maps search listings. These businesses remain eligible for growth campaigns and are assigned to the "No Website Opportunity" category.
    *   *Outdated Website*: Fails speed benchmarks (> 5.0 seconds), lacks mobile optimization, or uses legacy framework tech.
    *   *Modern Website*: Satisfies baseline UX, performance, and modern framework benchmarks.

### Module B: Web & Tech Presence Analysis
*   **Req 3.2.1**: Audit page response speed and metadata (meta titles, meta descriptions, headings) for leads with websites.
*   **Req 3.2.2**: Scrape CMS and technology footprints (e.g. WordPress, Webflow, Shopify, custom).
*   **Req 3.2.3**: Detect presence of specific widgets: Google Analytics, Facebook Pixel, booking tools (Calendly, Acuity), contact forms, and review embeds.

### Module C: Opportunity Identification Engine
*   **Req 3.3.1**: Map technical findings to business outcomes in alignment with the **Business Impact Principle**. Technical issues must not be presented in isolation. Gaps must be explained as:
    *   *Missing Schema Markup* -> Reduced local search visibility, causing loss of nearby buyer traffic.
    *   *Slow Mobile Speed* -> High page bounce rates, causing potential conversion loss.
    *   *Missing Booking Widget* -> Frictional checkout flow, causing lost lead opportunities.
    *   *No Website* -> Zero online presence, causing total loss of digital customer traffic.
*   **Req 3.3.2**: Flag opportunities across: Lost opportunities, Customer acquisition opportunities, Revenue-related opportunities, and Competitive weaknesses.

### Module D: Business Intelligence & Priority Engine
*   **Req 3.4.1**: Compile an **Opportunity Score** for each lead to prioritize opportunities based on gap severity and potential business return (see Section 6).
*   **Req 3.4.2**: Generate business impact explanations, growth recommendations, and competitive positioning statements based on audit traces.
*   **Req 3.4.3**: Ensure all insights adhere to the **Explainability and Evidence Principle**, citing the specific tool outputs, explaining the logic of recommendations, and distinguishing verified findings from assumptions.

### Module E: Competitive Intelligence
*   **Req 3.5.1**: Identify local competitors in the same geographic region using maps search tools.
*   **Req 3.5.2**: Compare the digital presence, website speed, and SEO indicators of the target SMB against competitors.
*   **Req 3.5.3**: Identify specific competitive advantages (e.g. "You have 100 more reviews than competitor X") and weaknesses (e.g. "Competitor Y uses schema markup, while you do not").
*   **Req 3.5.4**: Generate comparative opportunity reports explaining why an opportunity matters relative to the competitor landscape.

---

## 4. Opportunity Categories

To ensure consistency across the scoring systems, evaluation metrics, reporting modules, and multi-agent workflow routes, all opportunities must be classified into one of these formal categories:

1.  **No Website Opportunity**: Assigned to businesses lacking an online domain. Focuses on the business loss of local visibility and customer trust, pitching a complete web design package.
2.  **Website Modernization Opportunity**: Triggered by outdated CMS versions, non-responsive mobile views, missing sitemaps, or insecure SSL configurations. Connects technical debt to maintenance costs and brand perception.
3.  **SEO Opportunity**: Triggered by missing meta tags, duplicated headings, or lack of local schema markup. Connects to search ranking loss relative to local competitors.
4.  **Performance Opportunity**: Triggered by slow page load speeds (> 5.0 seconds). Connects page load times directly to customer bounce rates and Google Core Web Vitals search penalties.
5.  **Conversion Optimization Opportunity**: Triggered by the absence of booking engines, reservation widgets, lead capture forms, or click-to-call buttons. Focuses on lost user conversion traffic.
6.  **Analytics Opportunity**: Triggered by missing tag managers, analytics scripts, or retargeting pixels. Connects to the business's inability to track marketing ROI.
7.  **Reputation Opportunity**: Triggered by low ratings (< 4.2), low review counts (< 15), or unanswered review logs. Connects to lost local customer trust and visibility.
8.  **Competitive Positioning Opportunity**: Generated during competitive benchmarks. Identifies gaps where direct local competitors dominate the market.

---

## 5. Primary Product Deliverable: Growth Intelligence Report

The primary output of GrowthScout AI is the **Growth Intelligence Report**. Report generation and outreach copywriting are secondary capabilities derived entirely from the data, evidence, and structure compiled in the primary report.

### Growth Intelligence Report Structure
1.  **Executive Summary**: High-level summary of the business's digital posture.
2.  **Business Profile**: Base metadata (name, URL, contact info, ratings).
3.  **Website Findings**: Factual, verified HTML audit data (speed, meta tags, CMS) or "No Website" classification.
4.  **Opportunity Analysis**: Flagged opportunities mapped to formal categories and business outcomes.
5.  **Competitive Insights**: Digital presence comparison against local competitors.
6.  **Opportunity Scores**: Detailed, explainable scoring metrics.
7.  **Growth Recommendations**: Step-by-step actions prioritized by business impact.
8.  **Supporting Evidence**: Citations of specific tool outputs and logs.

---

## 6. Opportunity Scoring System

To prevent opaque or black-box scoring, every score generated by the platform must be explainable, cite supporting evidence, and communicate confidence levels.

### Scoring Structure Example
```
SEO Opportunity Score: 82 / 100
Priority: High
Confidence Level: High (All evidence verified via crawler logs)

Evidence:
  * Missing Local Schema Markup (Verified via SEO Auditor: No ld+json localBusiness tags found)
  * Weak Metadata (Verified via SEO Auditor: Meta description length is 12 characters; optimal is 120-160)
  * Competitors using structured data (Verified via local competitors analysis: 3 out of 4 top local competitors actively use schema markup)

Business Impact:
  * Reduced Local Search Visibility: The lack of schema and structured markup restricts Google from ranking this business for nearby search intents, causing a loss of local organic traffic.
```

---

## 7. MVP Scope (Version 1)

### Included in MVP
*   **Local Business Discovery**: Niche and location lookups with classification systems (No Website, Outdated, Modern).
*   **Website Analysis**: Base HTML scraper, speed logs, and tech scanners.
*   **Opportunity Detection**: Gaps mapped to the 8 formal Opportunity Categories.
*   **Competitive Intelligence**: Comparative reviews, rating, and SEO benchmarking.
*   **Opportunity Scoring**: Transparent, evidence-cited scoring.
*   **Growth Intelligence Report**: Fully structured Markdown and JSON export.
*   **Human-in-the-Loop Gate**: Manual review and edit screen before exporting reports.

### Not Included in MVP (Non-Goals)
*   **CRM (Customer Relationship Management)**: Lead pipelines and customer tracking.
*   **Email Campaign Automation**: Sequenced cold email blasting.
*   **Autonomous Outreach**: Sending emails or outreach scripts without human approval.
*   **Social Media Posting**: Automated scheduling of social media posts.
*   **Team Collaboration Features**: Multi-user permissions, sharing, and workspaces.
*   **Billing & Invoicing**: Payment processing systems and consultant invoice generators.
*   **Multi-Tenant Enterprise Management**: Advanced fleet controls.

---

## 8. Success Metrics

Evaluation-first success metrics that determine platform performance:

*   **Discovery Accuracy**: >= 95% of discovered leads must correspond to active physical businesses.
*   **Opportunity Detection Accuracy**: 100% of flagged opportunities must correspond to verified crawler logs or proven "No Website" maps records (zero hallucinated gaps).
*   **Competitive Insight Quality**: >= 90% of compared competitors must share the same geographic city and vertical niche.
*   **Growth Report Quality**: Evaluated via the `final_response_quality` metric, requiring a score of >= 0.82 for business impact analysis and explainability of opportunity scores.
*   **Time Saved**: Decrease user time spent researching and auditing a single local lead from ~45 minutes to < 2 minutes.
*   **Recommendation Relevance**: LLM-as-judge score for relevance of growth suggestions relative to the business niche (gate >= 0.85).
