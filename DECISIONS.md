# Engineering Decisions

This document walks through the main technical calls behind the PII Compliance Gateway — what broke, what I chose instead, and why.

I didn't want every part of this system to be AI-driven just because it's an "AI project." Each piece does the part it's actually good at: the model handles discovery, Python handles deterministic sanitization, Redis handles anything fast and temporary, Postgres holds anything that needs to persist.

---

## 1. LangGraph for PII Detection

### Problem

PII shows up in predictable shapes sometimes — a standard email regex catches most emails — but people don't write sensitive info consistently. Names buried mid-sentence, an SSN with spaces instead of dashes, a credit card split across lines. Regex alone falls apart once the input isn't clean.

I also didn't want to shove a raw LLM call directly into the FastAPI route and call it done. That gets messy fast the moment you need more than one step — validation, retries, structured output, whatever comes next.

### Options considered

- Regular expressions and static rules
- A bare LLM call inside the route handler
- A LangGraph-based workflow

### Decision

I chose LangGraph to orchestrate the detection workflow. FastAPI stays focused on the HTTP layer — validation, caching, rate limiting, persistence — and hands the actual PII-finding off to the workflow.

### Why

LangGraph gives me a real place to put processing steps instead of stacking logic inside one function. If I need to add a step later — a second validation pass, a different model, whatever — there's already a structure for that. A pile of regexes doesn't give you that room to grow.

### Trade-off

It's slower and heavier than regex, no question. Model dependency, extra latency, more moving parts to reason about. I took that trade-off on purpose — the goal was building an AI-driven detection workflow, not shipping another regex scanner with a fancier name.

---

## 2. Structured Pydantic Output Before Sanitization

### Problem

You can't just trust whatever the model hands back because it "looks right." Sanitization downstream needs something predictable to work with, not free-text that happens to resemble JSON.

### Decision

Pydantic models define the shape detection results have to take — entity type, entity value — before anything else touches that data.

### Why

This gives the AI output an actual contract instead of letting arbitrary model output flow straight into the rest of the app. If the model returns something malformed, it fails validation instead of silently corrupting a downstream step. It also keeps the LangGraph workflow easier to debug when something does go wrong.

### Trade-off

The schema has to be maintained alongside the workflow — if the model's output shape changes, the schema and whatever depends on it need updating too. Worth it. Predictable data beats flexible-but-untrustworthy data every time here.

---

## 3. Deterministic Sanitization Instead of LLM-Controlled Indexes

### Problem

This was the big one.

The first version of `sanitize_text` had the LLM return exact `start_index` and `end_index` values for each PII match. The plan:

1. Ask the model to detect the PII.
2. Get the character indexes.
3. Use Python string slicing to replace that section with a redacted value.

Sounded deterministic. Wasn't.

LLMs think in tokens, not characters. Python string ops think in character positions. Those two don't always line up, and the longer or messier the input got, the more the model's position guesses drifted — sometimes by one character, sometimes by more. That gave me redaction output like:

```text
Lo[REDACTED]ission
```

instead of catching the full sensitive value. Silent corruption, not a crash — which made it worse, because nothing was throwing an error to tell me it was wrong.

**Initial approach**

The initial flow was:

```
LLM
 ↓
PII + start_index + end_index
 ↓
Python string slicing
 ↓
Redacted text
```

Looked clean from the Python side. Was entirely dependent on the model doing accurate character math, which it just doesn't reliably do.

### Decision

I ripped the index logic out. The model's only job now is to identify the actual sensitive *value*, not where it sits in the string.

The new approach is:

```
LLM identifies entity_value
        ↓
Pydantic validates structured output
        ↓
Python performs the replacement
```

Python's native string replacement does the actual sanitization now.

### Why

Two different jobs, two different tools.

The LLM is good at:

- Identifying what looks like PII
- Identifying the type of PII

Python is better at:

- Performing a deterministic string transformation
- Applying the final redaction logic

There's no reason to make the model responsible for character-level precision when it's not built for that.

### Result

This killed the index-drift bug outright and made sanitization behavior actually predictable instead of "usually works." The principle that came out of it:

> **AI identifies the entity; Python replaces the entity.**

### Trade-off

Matching on the raw value is simpler, but it means I have to think harder about edge cases — what happens if the same value shows up twice, or if I need fuzzier matching later. For now, predictable behavior mattered more than handling every edge case up front.

---

## 4. Redis for Response Caching

### Problem

Detection isn't cheap — if the same text gets scanned twice, running the full workflow again is just wasted latency and wasted model calls.

### Decision

I added Redis response caching for repeated scan requests.

The cache key is generated from the SHA-256 hash of the input text:

```
input text
    ↓
SHA-256
    ↓
scan_cache:{hash}
```

Cached results expire after 24 hours.

### Why Redis

Fast key-value access, good fit for temporary application data like cached responses. Lets the API return a previously processed result without re-running the full PII workflow.

The cache key is derived from the input via SHA-256, so the raw input never sits directly in the Redis key.

### Cached data

The cached value holds what's needed to reproduce the API response:

- Sanitized text
- Detected PII metadata
- Processing time

The original raw input is not part of the cached response.

### Privacy consideration

Caching still has a privacy dimension because the system handles potentially sensitive text. That's why the cache is deliberately scoped to just what's needed to reproduce the response — nothing more.

The design keeps raw input out of both the cache key and the cached response, and entries expire after 24 hours regardless.

### Trade-off

Caching makes repeats much faster, but it also means sanitized response data sits in Redis temporarily. I accepted that because the expiration window is short and it saves repeating an expensive workflow for identical input.

---

## 5. Redis for IP-Based Rate Limiting

### Problem

Caching and rate limiting look similar — both live in Redis, both have a TTL — but they solve different problems. Caching makes repeats fast. It does nothing to stop someone from hammering the API with a thousand unique requests a minute. Needed a separate mechanism for that.

### Decision

I implemented IP-based rate limiting using Redis.

The current limit is:

> **50 requests per IP within 60 seconds**

Over the limit, the API returns:

> **HTTP 429 — Too Many Requests**

with a `Retry-After` response header.

### Why Redis

Redis was already in the stack for caching, so it's a natural spot for short-lived request counters too. No reason to make Postgres hold something that only matters for 60 seconds.

### Why Lua

The naive version of this — handling the counter across several separate Redis calls — creates a race condition when requests land at the same time: two requests can both read the counter before either one increments it, and the limit quietly stops holding.

The Lua script handles the counter increment and the initial expiration as one atomic Redis operation. Conceptually:

```
Request
   ↓
INCR counter
   ↓
If first request → set expiration
   ↓
Return current count
   ↓
Check limit
   ↓
Allow or return 429
```

Python checks the returned count against the configured limit. That keeps the counter update consistent even when multiple requests hit at once — no window for the race to sneak in.

### Trade-off

IP-based limiting is easy to build but not a complete abuse-prevention story. Multiple users behind the same IP, NAT, corporate proxies — all of that makes per-IP limits blunt rather than precise. Good enough as a first line of defense. Auth-aware or distributed rate limiting is a later problem if the project ever needs it.

---

## 6. PostgreSQL for Persistent Audit Data

### Problem

Redis is great for short-lived stuff, bad for anything that needs to survive a restart or actually be queried later. Audit records need to persist.

### Decision

I use PostgreSQL for persistent audit-related data, accessed through SQLAlchemy's async layer.

### Why PostgreSQL

Durable storage, real structured queries against audit records — something Redis isn't built for. The split is clean:

```
Redis
→ caching
→ rate limiting
→ short-lived data

PostgreSQL
→ persistent audit-related data
→ database-backed records
```

### Privacy trade-off

The first version of this stored the raw input directly in the audit record. Great for debugging, not great for privacy — storing PII specifically so you can audit for PII issues is its own kind of data-retention risk, and that started to bother me once I actually sat with it.

That made me rethink what the audit log actually needed to hold. The current `audit_logs` table stores:

- Sanitized text
- Detected PII metadata
- Processing time
- Timestamp

The original raw input is no longer stored, period.

The goal is simple: keep enough to understand what happened without turning the audit log into another place sensitive input quietly piles up.

### Schema changes

Database changes go through Alembic migrations. That means things like dropping the raw input column and changing the processing-time type are tracked in the repo instead of being hand-applied to production — and the exact same migration reproduces across dev and prod.

### Trade-off

Dropping the original input makes some debugging scenarios harder — I can't just look at the database and reconstruct the request that produced a record. I accepted that because keeping sensitive input around purely for debugging convenience defeats the entire point of a system built to reduce PII exposure.

---

## 7. Separate Frontend and Backend Repositories

### Problem

The gateway is fundamentally an API. It also needs a UI so people can actually see it work without curling endpoints. I didn't want the backend to depend on that UI existing to be useful.

### Decision

I split the project into two repos:

```
pii-compliance-gateway-api
        ↓
FastAPI backend

pii-compliance-gateway-client
        ↓
Next.js frontend
```

### Why

The backend stays consumable by anything, not just this one dashboard. The frontend can change without the backend project structure caring. This makes the gateway closer to an actual reusable service instead of a backend that only exists to feed one UI.

Deployment responsibilities fall out cleanly from that split too:

```
Frontend  → Next.js / Vercel
Backend   → FastAPI / Render
Database  → PostgreSQL / Neon
Cache     → Redis / Upstash
```

### Trade-off

Two repos means more config and deployment overhead than one monolith would have. Worth it here because the backend was always meant to stand on its own.

---

## 8. Why Performance Is Measured Separately

### Problem

It's easy to say "the cache makes this fast" without ever proving it. I wanted actual numbers, not a vibe.

### Decision

I built a standalone async benchmark script, Python + HTTPX, sending unique payloads and comparing:

```
Cold request
     ↓
Full PII processing path

Cached request
     ↓
Redis cache hit
```

20 iterations, 40 total requests.

### Result

The current local benchmark showed:

| Metric | Value |
| --- | --- |
| Cold average | 14570.18 ms |
| Cached average | 10.41 ms |
| Average improvement | ~1399x |

These are local numbers from the current implementation, not a production guarantee.

The benchmark also showed the cold path has significant latency variation — which tracks, since the cold path includes the AI processing workflow, currently the expensive and unpredictable part of the request.

### Trade-off

This shows the cold-vs-cached gap. It doesn't prove anything about concurrent users or requests-per-second at scale. A real controlled load test is separate future work I haven't done.

What matters here is the performance claims are backed by an actual benchmark instead of a number I made up because it sounded impressive.

---

## 9. Production Deployment

### Problem

A backend that only runs on localhost is fine for development, but it doesn't tell you anything about how the pieces actually behave once deployed. I wanted the API, database, Redis, and frontend talking to each other in a real environment, not just inside Docker Compose on my machine.

### Decision

I deployed using separate managed services:

```
Next.js
   ↓
Vercel
   ↓
FastAPI
   ↓
Render
   ↓
┌───────────────┬───────────────┐
↓               ↓
Neon            Upstash
PostgreSQL      Redis
```

Backend and frontend stay separate; database and Redis are managed independently of both.

### Why

This keeps each service focused on one job without me having to run database or Redis infrastructure myself. It also forced me into things that never show up when everything's local:

- Environment variables
- Production CORS configuration
- Managed PostgreSQL
- Managed Redis
- TLS connections
- Docker deployment
- Dynamic application ports
- Database migrations against a live schema
- Frontend-to-backend configuration
- Production health checks

### Trade-off

Managed services make deployment way easier, but they bring in external dependencies and platform-specific quirks to configure around. For a portfolio project, that's a fair trade — the point was proving this works as a deployed system, not just as a local prototype.

### Current deployment

It's live right now, and production frontend talks to production API. The backend also exposes a health endpoint so I can check the service is actually up independent of the frontend.

---

## 10. Docker for Local Development and Deployment

### Problem

The project depends on multiple services — PostgreSQL, Redis. Making everyone set those up manually on every machine is a pain and doesn't reproduce cleanly.

### Decision

Docker and Docker Compose for local dev. Main services: FastAPI, PostgreSQL, Redis.

### Why

Docker gives the project a consistent environment and gets the supporting services running without installing and configuring everything directly on the host. Compose also makes the relationship between the API, database, and Redis explicit instead of implicit.

### Production consideration

The backend is containerized for deployment too. I had to adjust the Docker config to work with the dynamic port the production platform assigns, instead of assuming the app always runs on one fixed port.

### Trade-off

Docker is another layer to understand — container networking, volumes, ports, env vars, all of it. Worth taking on given how many services this project actually depends on and how much reproducibility matters here.

---

## 11. Database Migrations with Alembic

### Problem

Changing a schema by hand works fine on a small local project. It stops working once the app is deployed. Dropping the raw input column from the audit table shouldn't mean manually opening the production database and running SQL.

### Decision

Alembic manages schema changes. Every change is a migration that lives in the repo.

### Why

This gives the project a real history of how the schema evolved, and makes production migrations reproducible instead of ad-hoc. Right now there are migrations for:

- Creating the initial audit schema
- Removing the raw input column
- Changing processing time storage from integer to float

The production Neon database got updated through the migration workflow, not a manual schema edit.

### Trade-off

Migrations are another workflow to understand and maintain, and there's a real responsibility to test them before they hit production. I accepted that because schema changes belong in versioned code, not as undocumented manual operations someone has to remember they did.

---

## 12. Environment Configuration and Secrets

### Problem

The app needs credentials for Postgres, Redis, and the LLM provider. Hardcoding any of that would make the project unsafe to publish, full stop.

### Decision

Environment variables for configuration and secrets. Local dev uses a `.env` file; production secrets live in the deployment platform's config. `.env` is excluded via `.gitignore`, and a `.env.example` ships with the variable names so the project's runnable without exposing real credentials.

### Why

Keeps secrets out of source code entirely and makes the same codebase portable across environments — the app code doesn't care whether it's talking to local Postgres or Neon, that's just a different env var.

### Trade-off

More values to get right when setting the project up, and a missing or misnamed env var can cause a runtime failure that's annoying to track down. Still the correct trade-off — secrets don't belong in the repo, no exceptions.

---

## 13. Keeping Raw PII Out of Persistent Storage

### Problem

Once I stopped thinking of this as just an "AI demo" and started thinking of it as an actual privacy-focused system, something bugged me: a gateway that detects and redacts PII while quietly storing that same PII somewhere is a contradiction. Redacting the response and then keeping the raw input in the database defeats the point.

### Decision

The current design intentionally keeps the original raw input out of persistent audit records, and out of the Redis cache key or cached response too.

The flow is:

```
Incoming request
      ↓
PII detection
      ↓
Sanitized response
      ↓
Audit-safe data
```

Not:

```
Incoming request
      ↓
PII detection
      ↓
Store original input everywhere
```

### Why

The gateway's job is to reduce unnecessary PII exposure, not create more copies of the same sensitive data in different places. The audit record holds sanitized text, detected PII metadata, processing time, and a timestamp. The Redis cache holds sanitized response data and expires after 24 hours.

### Trade-off

This makes debugging and forensic scenarios harder — I can't reconstruct the original request straight from the database. I accepted that because storing raw PII indefinitely for debugging convenience undercuts the entire reason this project exists.

And to be clear: this isn't a claim that the project is a finished compliance solution. Real production systems still need formal retention policies, access controls, encryption policies, and compliance review specific to whatever environment they run in.

---

## 14. What I Learned From These Decisions

The biggest lesson out of all of this: throwing more AI at a problem doesn't automatically make it better. In a few places, the right engineering call was actually to take responsibility *away* from the model.

Sanitization is the clearest example. I initially tried to make the model return exact character indexes — sounded smart, turned out to be unreliable. Moving that back into deterministic Python made the whole thing simpler and predictable instead of "usually works."

That same thinking runs through the rest of the architecture:

```
LLM
→ semantic PII discovery

Pydantic
→ structured validation

Python
→ deterministic sanitization

LangGraph
→ workflow orchestration

Redis
→ caching and rate limiting

PostgreSQL
→ persistent audit-related data

FastAPI
→ API and request handling

Next.js
→ user-facing dashboard
```

Each piece has one job. That mattered a lot more than trying to make the project look impressive by putting AI into every layer of it.

---

## Summary

The whole design comes down to not making one piece of tech responsible for everything:

| Component | Responsibility |
| --- | --- |
| FastAPI | API and request handling |
| Pydantic | Structured validation |
| LangGraph | AI workflow orchestration |
| Python | Deterministic sanitization |
| Redis | Caching and rate limiting |
| PostgreSQL | Persistent audit-related data |
| Next.js | User-facing dashboard |
| Docker | Consistent development environment |
| Alembic | Database schema migrations |

The biggest architectural lesson: the model doesn't need to control every step. Use it where semantic understanding actually matters, use deterministic code where exact behavior matters — and don't blur that line just because it's an "AI project." That's the same principle still steering what's left to fix: privacy controls, performance, testing, and production readiness.