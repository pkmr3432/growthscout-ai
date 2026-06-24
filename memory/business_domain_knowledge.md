# Business Domain Knowledge: GrowthScout AI

This document establishes the business domain rules, auditing criteria, and marketing heuristics utilized by GrowthScout AI to identify opportunities and compile Growth Intelligence Reports for small and medium-sized businesses (SMBs).

---

## 1. Local Lead Scoring and Valuation Heuristics

A lead is scored from **0 to 100** based on the severity of their digital gaps. Leads with higher scores represent high-priority sales opportunities:

```
Lead Score = (SEO Gap Weight * 30) + (Booking Gap Weight * 35) + (Analytics Gap Weight * 15) + (Social Gap Weight * 20)
```

| Digital Gap | Severity | Weight | Sales Pitch Value |
| :--- | :--- | :--- | :--- |
| **No Booking Widget** | Critical | 35% | "You are losing immediate bookings to competitors who allow online scheduling." |
| **Outdated/Slow Website** | High | 30% | "Slow mobile websites bounce 53% of local mobile visitors." |
| **Missing Social Pixels** | Medium | 20% | "You cannot retarget users who visited your services page but didn't convert." |
| **Missing Analytics** | Low | 15% | "You have zero visibility into where your website traffic is coming from." |

---

## 2. Technical Audit Thresholds

The Opportunity Agent classifies website audits according to the following thresholds:

*   **Mobile Loading Speed (Speed Index)**:
    *   *Good*: < 2.5 seconds
    *   *Needs Improvement*: 2.5 - 5.0 seconds
    *   *Critical*: > 5.0 seconds (High priority pitch target)
*   **On-Page SEO Compliance**:
    *   *Critical*: Missing Meta Title, Missing Meta Description, or multiple `<h1>` elements.
    *   *Warning*: Meta description is too long (> 160 characters) or too short (< 50 characters).
*   **Local SEO Schema Markup**:
    *   *Critical*: Missing LocalBusiness Schema, or missing telephone/address fields in structured data.

---

## 3. Growth Outreach Personalization Rules
To maximize conversion, generated outreach scripts must follow the **AIDA Structure** (Attention, Interest, Desire, Action) and incorporate three specific data facts:

1.  **Factual Hook**: Reference a specific page on their website or their exact Google maps rating (e.g., "Congratulations on your 4.8 rating on Maps, but did you know...").
2.  **Identified Gaps**: Reference exactly what was found (e.g., "Your site loads in 6.2 seconds and is missing meta tags...").
3.  **Low-Friction CTA**: Always suggest a 10-minute call or offer a free mockup instead of pitching a high-ticket contract immediately.
