# Research Agents & Knowledge Management

Deep research during requirements, ongoing monitoring, and wiki-based knowledge storage.

## The Problem

Agents make better decisions when they have current, accurate information. A requirements agent proposing "use Stripe for payments" should know:
- What are the alternatives? (Stripe vs Square vs Paddle vs self-hosted)
- What are the integration patterns? (API, SDK, webhooks)
- What are the security requirements? (PCI-DSS, tokenization)
- What do similar projects do?
- What are the costs?

A senior engineer researches before proposing. Agents should too.

## Research Agent

A dedicated agent that conducts deep research on topics and stores findings for other agents to use.

### When it runs

| Trigger | Context | Output |
|---|---|---|
| **Requirements elicitation** | User mentions a domain (payments, auth, chat) | Research findings for that domain |
| **Architecture decision** | Agent needs to compare options | Comparison with pros/cons/recommendation |
| **Dependency audit** | Weekly scheduled scan | Update report, security advisories |
| **Security advisory** | CVE published for a used package | Alert + fix recommendation |
| **On-demand** | User asks "what's the best way to do X?" | Research findings |

### Tools it needs

| Tool | Purpose | Source | How |
|---|---|---|---|
| **SearXNG** | Web search (best practices, blog posts, tutorials, comparisons) | Self-hosted metasearch engine | `http://searxng:8080/search?q=...&format=json` |
| **Context7** | Library/framework documentation (API refs, code examples, config) | Context7 MCP server | `resolve-library-id` → `query-docs` |
| Package registry | Dependency versions, deprecation status | npm, PyPI APIs via SearXNG | SearXNG engines: `pypi`, `npm`, `docker_hub` |
| CVE database | Security vulnerabilities | NVD, GitHub Advisory DB via SearXNG | SearXNG category: `it` with security queries |
| Code search | Patterns in existing codebases | GitHub, GitLab via SearXNG | SearXNG engines: `github`, `stackoverflow` |
| Doc fetching | Read specific pages/URLs | Direct HTTP fetch | `httpx.get(url)` |

### SearXNG (search backbone)

SearXNG is a self-hosted metasearch engine that aggregates results from Google, DuckDuckGo, GitHub, StackOverflow, MDN, PyPI, npm, arXiv, and more. It provides a JSON API for programmatic access.

**Endpoints:**
```
GET http://searxng:8080/search?q={query}&format=json
GET http://searxng:8080/search?q={query}&format=json&engines=github,stackoverflow
GET http://searxng:8080/search?q={query}&format=json&categories=general,it,science
```

**Specialized search functions (in portal/app/search.py):**
- `search_web(query)` — general web search
- `search_code(query)` — GitHub, StackOverflow, GitLab
- `search_docs(query)` — MDN, ArchWiki, Wikipedia
- `search_packages(query)` — PyPI, npm, DockerHub
- `search_academic(query)` — arXiv, scientific sources
- `deep_research(topic)` — multi-round research combining all sources

**Engine categories:**
| Category | Engines | Use for |
|---|---|---|
| `general` | Google, DuckDuckGo | Best practices, blog posts, tutorials |
| `it` | GitHub, StackOverflow, MDN | Code patterns, technical Q&A |
| `science` | arXiv, Google Scholar | Academic research, algorithms |
| `packages` | PyPI, npm, DockerHub | Dependency research |

### Context7 (documentation lookup)

Context7 provides up-to-date library/framework documentation and code examples. It's used when the research agent needs specific API details, configuration syntax, or usage patterns.

**Workflow:**
1. `resolve-library-id("express.js")` → gets Context7 library ID
2. `query-docs(libraryId, "middleware authentication")` → gets relevant docs + code examples

**When to use Context7 vs SearXNG:**
| Need | Tool | Example |
|---|---|---|
| "What are the options for X?" | SearXNG | "What are the best Node.js ORMs?" |
| "How do I configure X?" | Context7 | "How do I set up Express middleware?" |
| "What's the API for X?" | Context7 | "Stripe checkout session create params" |
| "Compare X vs Y" | SearXNG | "Prisma vs Drizzle comparison" |
| "X best practices" | SearXNG | "JWT best practices 2026" |
| "X code example" | Context7 | "Express route handler example" |

### Research process

1. **Scope** — Define the research question clearly
2. **Search** — Gather information from multiple sources
3. **Synthesize** — Distill findings into actionable recommendations
4. **Source** — Cite sources for every claim
5. **Store** — Write findings to wiki
6. **Link** — Connect findings to relevant requirements/architecture

### Output format

```markdown
---
topic: payment-systems
researched: 2026-07-15
freshness: current           # current | stale | outdated
refresh_schedule: monthly
triggered_by: REQ-001
---

# Payment Integration Research

## Options Evaluated

### Stripe
- **Pros:** Best developer docs, widest ecosystem, handles PCI-DSS
- **Cons:** 2.9% + 30¢ per transaction, vendor lock-in
- **Integration:** REST API, SDKs for all languages, webhooks for events
- **Cost:** 2.9% + 30¢ per successful charge
- **Best for:** SaaS, marketplaces, subscription billing

### Square
- **Pros:** Good POS integration, lower fees for in-person
- **Cons:** Weaker developer docs, smaller ecosystem
- **Integration:** REST API, SDKs available
- **Cost:** 2.6% + 10¢ per transaction
- **Best for:** Retail, restaurants, in-person + online

### Self-hosted (Lemon Squeezy, Paddle)
- **Pros:** Merchant of record (handles tax), simpler pricing
- **Cons:** Less customization, higher base fees
- **Integration:** REST API, webhooks
- **Cost:** 5% + 50¢ per transaction
- **Best for:** Digital products, global SaaS (tax handling)

## Recommendation

**Stripe** for this project. Reasons:
1. Best developer experience (matches our TDD approach)
2. Extensive test helpers (stripe-mock, test clocks)
3. Handles PCI-DSS compliance (we never touch raw card data)
4. Webhooks for async event processing (matches our architecture)

## Sources
- https://stripe.com/docs
- https://docs.squareup.com
- https://developer.paddle.com
- https://blog.example.com/payment-comparison-2026
```

## Wiki Structure

The wiki becomes a living knowledge base. Research agent writes to it. Knowledge agent reads from it. Documentation agent maintains it.

```
wiki/
  Home.md                      — project overview + status dashboard
  Architecture.md              — tech stack, patterns, decisions
  API-Reference.md             — auto-generated from code
  Changelog.md                 — auto-generated from commits
  Development.md               — how to contribute
  
  Research/                    — deep research by topic
    payment-systems.md         — payment integration options
    real-time-chat.md          — real-time communication patterns
    authentication.md          — auth strategies (JWT, sessions, OAuth)
    deployment.md              — hosting and deployment options
  
  Monitoring/                  — automated monitoring reports
    dependencies.md            — current versions + available updates
    security-advisories.md     — active vulnerabilities
    tech-radar.md              — technology landscape for our stack
    freshness.md               — when each research item was last checked
```

### Research/ directory

Each file is a deep dive on a topic. Contains:
- Options evaluated (with pros/cons)
- Recommendation with rationale
- Sources cited
- Freshness metadata

### Monitoring/ directory

Auto-generated reports:

**dependencies.md:**
```markdown
# Dependency Status
Last scanned: 2026-07-15

| Package | Current | Latest | Type | Status |
|---|---|---|---|---|
| express | 4.18.2 | 4.21.0 | minor | update available |
| pg | 8.11.3 | 8.12.0 | minor | update available |
| lodash | 4.17.20 | 4.17.21 | patch | security fix |

## Action Required
- **lodash 4.17.21** — Security fix for prototype pollution (CVE-2021-23337)
  - Severity: High
  - Action: `npm update lodash`
```

**security-advisories.md:**
```markdown
# Security Advisories
Last checked: 2026-07-15

## Active Advisories

### CVE-2026-XXXX — Express body-parser DoS
- **Severity:** Medium
- **Package:** body-parser < 1.20.3
- **Affected:** Our version: 1.20.2
- **Fix:** Update to 1.20.3
- **Impact:** Denial of service via crafted payload
- **Action:** Update dependency
```

**tech-radar.md:**
```markdown
# Tech Radar
Last updated: 2026-07-15

## Adopt (use confidently)
- Express.js — mature, well-documented, our current framework
- PostgreSQL — reliable, feature-rich, our current database

## Trial (worth pursuing)
- Drizzle ORM — type-safe, lightweight alternative to Sequelize
- Hono — faster alternative to Express for API routes

## Assess (worth investigating)
- Bun — faster runtime, Node.js compatible
- Turso — edge SQLite, interesting for read-heavy workloads

## Hold (proceed with caution)
- MongoDB — not suitable for our relational data model
- GraphQL — overkill for our current API surface
```

## Freshness Management

Every research item has a freshness status and refresh schedule.

### Freshness states

| State | Meaning | Action |
|---|---|---|
| `current` | Recently researched, still valid | No action |
| `stale` | Older than refresh schedule | Research agent re-checks |
| `outdated` | Known to be wrong (new version, deprecated) | Research agent re-researches |
| `unknown` | Never researched | Research agent researches |

### Refresh schedules

| Topic type | Schedule | Rationale |
|---|---|---|
| Dependencies | Weekly | New versions frequently |
| Security advisories | Daily | Critical to catch quickly |
| Technology comparisons | Monthly | Landscape changes slowly |
| Best practices | Quarterly | Patterns evolve gradually |
| Architecture decisions | On-demand | When relevant code changes |

### Freshness check process

```
Documentation Agent (weekly):
  for each research item in wiki:
    if item.age > item.refresh_schedule:
      item.freshness = "stale"
      trigger Research Agent for item.topic
```

## Integration with Other Agents

### During requirements elicitation

```
User: "I need a payment system"
  ↓
Requirements Agent: "Let me research payment options for your stack"
  ↓
Research Agent: [searches web, reads docs, synthesizes]
  ↓
Research Agent: [stores findings in wiki Research/payment-systems.md]
  ↓
Requirements Agent: [incorporates findings into requirement.md]
  ↓
Requirements Agent: "Based on my research, Stripe is the best fit because..."
```

### During architecture decisions

```
Architecture Agent: "Should we use Redis or RabbitMQ for job queues?"
  ↓
Architecture Agent calls Research Agent: "Compare Redis vs RabbitMQ"
  ↓
Research Agent: [research + store in wiki]
  ↓
Architecture Agent: [makes informed decision]
  ↓
Architecture Agent: [stores decision + research link in knowledge/decisions.md]
```

### During implementation

```
Implementation Agent: "What's the current Express.js middleware pattern?"
  ↓
Knowledge Agent: [checks wiki Research/ for Express patterns]
  ↓
Knowledge Agent: [returns findings or triggers Research Agent]
  ↓
Implementation Agent: [uses current patterns in code]
```

### During security monitoring

```
Pipeline Watcher: [CI build runs]
  ↓
Pipeline Watcher: [checks for known vulnerabilities in dependencies]
  ↓
If vulnerability found:
  Pipeline Watcher: [creates issue, comments with fix recommendation]
  ↓
Documentation Agent: [updates wiki Monitoring/security-advisories.md]
```

## Portal Integration

The portal shows research and monitoring status:

**Project detail page — Research tab:**
- List of research topics with freshness indicators
- "Research this topic" button for on-demand research
- Links to wiki pages for deep dives

**Project detail page — Monitoring tab:**
- Dependency update alerts
- Security advisory alerts
- Tech radar visualization

**Dashboard — Global alerts:**
- Security advisories across all projects
- Stale research items that need refresh
- Dependency updates available

## Cost Estimation

| Research type | Model | Est. tokens | Est. cost (OpenCode Go) |
|---|---|---|---|
| Deep research (one topic) | kimi-k2.7-code | 150K | $0.22 |
| Dependency scan (weekly) | deepseek-v4-flash | 30K | $0.005 |
| Security scan (daily) | deepseek-v4-flash | 10K | $0.002 |
| Tech radar (monthly) | kimi-k2.7-code | 80K | $0.12 |

Monthly cost for a single project with active research: ~$1.50
