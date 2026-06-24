# Tool Safety & Sandboxing Policies: GrowthScout AI

This document establishes the safety controls, sandboxing rules, and compliance boundaries for executing local and third-party tools within GrowthScout AI.

---

## 1. Web Scraper Sandboxing
Crawling external websites poses a risk of SSRF, system command execution via shell escaping, and IP blacklisting. Scrapers must abide by these rules:

*   **Isolated Subprocess Executions**: Playwright or BeautifulSoup parsers must run inside a container segment that is network-isolated from internal databases (e.g. Firestore and Redis instances).
*   **Allowed Protocols**: The scrapers may only fetch URL endpoints using `http` or `https` protocols. Attempts to access local endpoints (e.g. `file:///etc/passwd`, `http://localhost:8080`, `http://169.254.169.254` metadata services) must be dropped before socket generation.
*   **Response Payload Cap**: Crawlers must limit download buffers to **2MB** per page to prevent memory bloat attacks (Zip Bombs).

---

## 2. API Quotas & Rate Limits
To prevent quota exhaustion on Google Maps API and avoid IP bans during scraping, the following rate limits are hardcoded:

*   **Google Places Search**: Maximum of 10 queries per minute per API Gateway instance.
*   **Target Website Crawling**: Maximum of 1 page crawl request per 2 seconds targeting the same domain.
*   **Max Concurrent Scrapes**: A maximum of 5 target websites can be audited simultaneously across the platform session threads.
