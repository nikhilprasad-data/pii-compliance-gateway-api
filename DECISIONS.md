# Engineering Decisions

This document explains the main technical decisions behind the PII Compliance Gateway, the problems that led to them, and the trade-offs I considered while building the system.

The goal was not to make every part of the system AI-driven. Instead, I wanted each component to handle the part it is best suited for: AI for PII discovery, Python for deterministic sanitization, Redis for fast temporary operations, and PostgreSQL for persistent audit-related data.

---

## 1. LangGraph for PII Detection

### Problem

PII can appear in predictable formats, but users do not always write sensitive information in the same way.

A traditional rule-based system can handle patterns such as standard email addresses, phone numbers, or credit card formats, but it becomes harder to maintain when the input becomes less predictable or contains contextual information.

I wanted the gateway to have a workflow that could combine PII detection with structured processing instead of putting all of the logic directly inside the FastAPI route.

### Options considered

- Regular expressions and static rules
- A simple LLM call directly inside the API route
- LangGraph-based workflow

### Decision

I chose LangGraph to orchestrate the PII detection workflow.

FastAPI handles the API layer, while the LangGraph workflow handles the AI-related processing.

This keeps the API route focused on request handling, validation, caching, rate limiting, and persistence instead of making it responsible for the entire PII detection process.

### Why

LangGraph gives the project a structured way to organize the processing steps and makes it easier to add or change workflow logic later.

It also gives me more flexibility than keeping the entire detection process as a collection of static regular expressions.

### Trade-off

The main trade-off is complexity and latency.

A rule-based solution would be simpler and faster for predictable patterns. Using an LLM-based workflow introduces model dependency, additional processing time, and more moving parts.

For this project, I accepted that trade-off because the goal was to explore an AI-driven PII detection workflow rather than build only a traditional regex scanner.

---

## 2. Structured Pydantic Output Before Sanitization

### Problem

LLM output cannot be treated as trusted application data just because the model returned something that looks correct.

The sanitization workflow needs predictable information about the entities detected by the model.

### Decision

I used Pydantic models to define the expected structure of the detection results.

The model output is converted into structured data before the application uses it for the sanitization process.

The important information includes the detected entity type and the actual entity value.

### Why

Using a schema gives the application a clear contract for the AI output.

Instead of allowing arbitrary model-generated data to flow directly into the rest of the application, the output has to fit the structure expected by the system.

This also makes the LangGraph workflow easier to reason about and maintain.

### Trade-off

The schema adds some structure that needs to be maintained as the workflow changes.

If the model output changes, the Pydantic schema and related processing logic may also need to change.

I considered this a worthwhile trade-off because predictable application data is more important than keeping the AI output completely unstructured.

---

## 3. Deterministic Sanitization Instead of LLM-Controlled Indexes

### Problem

This was one of the main problems I encountered while building the project.

Initially, the `sanitize_text` step relied on the LLM returning the exact `start_index` and `end_index` of detected PII.

The idea was simple:

1. Ask the model to detect the PII.
2. Get the character indexes.
3. Use Python string slicing to replace that section with a redacted value.

The problem was that the indexes were not always reliable.

LLMs process text using tokens, while Python string operations work with character positions. As the text became longer or more complex, the model's calculated positions could drift by one or more characters.

That resulted in corrupted redaction such as:

```text
Lo[REDACTED]ission
```

instead of replacing the complete sensitive value.

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

The approach looked deterministic from the Python side, but it depended on the LLM providing mathematically accurate character positions.

### Decision

I changed the design so that the LLM identifies the actual sensitive value instead of being responsible for calculating the exact character range.

The new approach is:

```
LLM identifies entity_value
        ↓
Pydantic validates structured output
        ↓
Python performs the replacement
```

Python's native string replacement is then used for the actual sanitization.

### Why

This separates two different responsibilities.

The LLM is good at:

- Identifying what looks like PII.

Python is better at:

- Performing a deterministic string transformation.

There was no reason to make the LLM responsible for something that Python can do more reliably.

### Result

The change removed the index-based redaction problem I encountered and made the sanitization behavior much more predictable.

The main design principle that came out of this was:

> **AI identifies the entity; Python replaces the entity.**

### Trade-off

Using the actual entity value makes the sanitization logic simpler, but it also means the replacement strategy needs to be designed carefully when the same value appears multiple times or when more complex matching rules are required.

For the current project, the predictable behavior was more valuable than keeping the LLM responsible for character-level operations.

---

## 4. Redis for Response Caching

### Problem

PII detection can be an expensive part of the request path, especially when the same input is scanned repeatedly.

If the exact same text is submitted again, running the complete detection workflow again is unnecessary.

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

Cached results currently have a 24-hour expiration.

### Why Redis

Redis provides fast key-value access and works well for temporary application data such as cached responses.

It also allows the API to return a previously processed result without running the complete PII workflow again.

### Trade-off

Caching improves repeated-request latency, but it introduces a data-retention consideration.

The SHA-256 cache key does not contain the raw input text, but the cached value currently contains response data that includes the original input.

Because this project handles potentially sensitive information, the cache payload and retention policy need to be treated as part of the privacy design rather than only as a performance feature.

The current direction is to redesign the cache so that raw input is not retained unnecessarily.

---

## 5. Redis for IP-Based Rate Limiting

### Problem

Caching and rate limiting solve different problems.

Caching helps repeated requests become faster, but it does not stop a client from sending a large number of requests and consuming application resources.

The gateway therefore also needs a basic protection mechanism against excessive requests.

### Decision

I implemented IP-based rate limiting using Redis.

The current limit is:

> **50 requests per IP within 60 seconds**

When the limit is exceeded, the API returns:

> **HTTP 429 — Too Many Requests**

with a `Retry-After` response header.

### Why Redis

Redis is already part of the gateway for caching, so it provides a natural place to keep short-lived request counters.

The counter does not need to be stored permanently in PostgreSQL.

### Why Lua

The rate limiter uses a Redis Lua script to increment the counter and set the expiration atomically.

The important part is that the counter and its expiration are handled together instead of relying on separate application-level operations.

Conceptually:

```
Request
   ↓
INCR counter
   ↓
If first request → set expiration
   ↓
Check limit
   ↓
Allow or return 429
```

### Trade-off

IP-based limiting is simple to implement, but it is not a complete identity-based abuse-prevention system.

Multiple users can share an IP address, and clients behind proxies or NAT can make IP-based limits less precise.

For the current gateway, it provides a useful basic protection layer. Authentication-aware or distributed rate limiting can be added later.

---

## 6. PostgreSQL for Persistent Audit Data

### Problem

Redis is useful for temporary data, but it is not the right place for persistent audit-related records.

The gateway needs a persistent storage layer for information that may need to be reviewed later.

### Decision

I use PostgreSQL for audit-related persistence.

The FastAPI application uses SQLAlchemy's asynchronous database layer to interact with PostgreSQL.

### Why PostgreSQL

PostgreSQL provides durable storage and supports structured querying of audit records.

This makes it more appropriate for persistent application data than Redis, whose primary role in this project is temporary and fast-access data.

The separation is therefore:

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

The original implementation stored the raw input in the audit record.

That made the audit trail useful for development and debugging, but it also created an important privacy question: storing PII for auditing can itself become a data-retention risk.

I decided that the gateway should move toward storing sanitized or audit-safe information where possible instead of retaining raw PII unnecessarily.

This is an architectural improvement rather than a claim that the current implementation has already solved the entire data-retention problem.

### Current direction

The database retention model and Redis cache payload are both being reviewed as part of the project's privacy design.

The goal is to keep enough information for useful auditing and debugging without retaining sensitive input longer than necessary.

---

## 7. Separate Frontend and Backend Repositories

### Problem

The PII gateway is fundamentally an API service, but it also needs a user-friendly interface for testing and demonstrating the system.

I did not want the backend to depend on the dashboard in order to be useful.

### Decision

I separated the project into two repositories:

```
pii-compliance-gateway-api
        ↓
FastAPI backend

pii-compliance-gateway-client
        ↓
Next.js frontend
```

### Why

The backend can be consumed independently by other clients or services.

The frontend can also evolve without requiring the backend project structure to change.

This separation makes the gateway closer to a reusable backend service rather than an API that only exists to serve one UI.

It also makes the deployment responsibilities clearer:

```
Frontend  → Next.js
Backend   → FastAPI
Database  → PostgreSQL
Cache     → Redis
```

### Trade-off

Separating the repositories introduces additional configuration and deployment complexity compared with keeping everything inside a single application.

For this project, I accepted that complexity because the backend is intended to remain independently usable.

---

## 8. Why Performance Is Measured Separately

### Problem

It is easy to describe a cache as "fast" without actually measuring how much difference it makes.

I wanted the project to show the difference between the normal processing path and the Redis cache path using measured data rather than assumptions.

### Decision

I created a standalone asynchronous benchmark script using Python and HTTPX.

The benchmark sends unique payloads and compares:

```
Cold request   → Full PII processing path
Cached request → Redis cache hit
```

The current benchmark uses 20 iterations and 40 total requests.

### Result

The local benchmark showed:

| Metric | Value |
| --- | --- |
| Cold average | 14570.18 ms |
| Cached average | 10.41 ms |
| Average improvement | ~1399x |

These numbers are local measurements from the current implementation, not production performance guarantees.

The benchmark also showed that the cold path has significant latency variation, which indicates that the AI processing path is currently the expensive and variable part of the system.

### Trade-off

The benchmark demonstrates the difference between cold and cached requests, but it is not a full production load test.

It does not prove that the system can handle a specific number of concurrent users or requests per second.

A proper controlled load-testing setup is a separate future improvement.

---

## Summary

The main design principle behind the project is to avoid making one technology responsible for everything.

The system uses different components for different responsibilities:

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

The most important architectural lesson was the separation between AI-based discovery and deterministic data transformation.

The LLM does not need to control every step of the process. It is more reliable to use the model where semantic understanding is useful and traditional deterministic code where exact behavior matters.

That principle shaped several decisions in the project and is still guiding the areas that are being improved, especially privacy, performance, testing, and production readiness.