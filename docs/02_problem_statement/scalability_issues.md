# Scalability Challenges

This document analyses the scalability dimensions the platform must handle
and the headroom of the chosen single-host architecture. It is honest
about where the design scales and where it does not.

## Dimensions of scale

| Dimension | Current order of magnitude | Bottleneck |
|---|---|---|
| Threat artefacts stored | ~39 000 CVEs, ~2 000 IOCs, ~140 actors, hundreds of articles/threats | Postgres disk + index size |
| Concurrent users | 3 named + occasional | Frontend SSR + BFF |
| Ingest sources | ~20 across 5 ingester services | External API rate limits, not TIP |
| Scheduled jobs | 12 built-in + watchdog | APScheduler single-process |
| AI calls/day | Tens (analyst-driven + 2 daily cycles) | Provider daily quota |
| IOC lookups/min | Bursty during incidents | Redis (handles 10⁴+/s trivially) |

## Where the architecture scales well

### Read-heavy lookup
The IOC hot path is Redis-backed. Redis on a single node handles tens of
thousands of ops/sec — orders of magnitude above the SOC's burst rate.
The lookup is O(1) and never touches Postgres on a cache hit.

### Stateless services
Every data service is stateless (state lives in Postgres / Redis). Any
service could be horizontally scaled by running N replicas behind a load
balancer with **no code change** — the only shared mutable state is the
database, already pooled through PgBouncer.

### Ingest parallelism
Within a single ingest cycle, sources run concurrently via
`asyncio.gather`. Adding sources adds tasks, not wall-clock time (bounded
by the slowest source, not the sum).

### Schema-per-service
Splitting a hot service (e.g. moving `vuln` to its own Postgres instance)
requires only changing that service's `DATABASE_URL` — no cross-schema
FK to untangle.

## Where the architecture does not scale (by design)

### Single Postgres instance
All 15 schemas share one Postgres process. This is a deliberate
single-host tradeoff. At the customer's data volume (tens of thousands of
rows) it is comfortable. The evolution path (read replicas, per-service
Postgres) is in `16_future_work/scalability_improvements.md`.

### Single scheduler process
APScheduler runs in one `scheduler` container with an in-Postgres job
store. Running two scheduler replicas would double-fire jobs. For one
organisation's cron cadence this is correct; a distributed scheduler
(e.g. moving to a queue + workers) is a future option.

### AI throughput is provider-bound
The platform cannot exceed the AI provider's quota. This is not a TIP
bottleneck — it is an external constraint. The platform's responses
(smart picker, cache-first, fallback cascade) maximise useful work per
quota unit but cannot manufacture quota. Mitigation: add an Anthropic /
OpenAI direct key with a paid tier to the vault; the LiteLLM proxy uses
it transparently.

### Single LiteLLM proxy
One proxy container fronts all AI. It is stateless and could be replicated
behind a load balancer, but at current call volumes (tens/day) a single
instance is far from saturated.

## Scaling triggers and responses

| If this grows… | First response | Then |
|---|---|---|
| IOC lookups → 10⁴/s sustained | Already Redis-served; no action | Redis cluster |
| Artefact count → millions | Add Postgres indexes (already partially done) | Read replica for read-heavy services |
| Users → dozens | Frontend is stateless; scale replicas | CDN for static assets |
| Ingest sources → hundreds | Still bounded by slowest source per cycle | Split ingesters into more services |
| AI calls → thousands/day | Add paid provider key to vault | Multiple proxy replicas |

## Capacity at the design point

For the stated customer (3 users, tens of thousands of artefacts, ~20
sources, tens of AI calls/day) the single-host architecture has
substantial headroom. The platform is **CPU-idle most of the time**;
the active work is bursty (ingest cycles, analyst clicks). The constraint
that bites first in practice is **AI provider quota**, which is external
and addressed operationally (provider choice on the LiteLLM proxy).

## Honest statement of limits

This is a **single-host, single-organisation** platform. It is not
designed to be a multi-tenant SaaS, and the documentation does not claim
horizontal-scale-to-millions. The architecture's statelessness means the
*path* to horizontal scale is open (replicate services, externalise
Postgres), but that path is documented as future work, not delivered.
