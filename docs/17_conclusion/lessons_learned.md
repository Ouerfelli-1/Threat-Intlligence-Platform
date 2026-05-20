# Lessons Learned

An honest retrospective. These are the engineering lessons the project
actually taught — several were learned the hard way, through real bugs
documented in the git history.

## 1. Architectural discipline pays compounding dividends

The single decision to enforce **schema-per-service with no cross-schema FKs**
(`P1`) paid off repeatedly: it made services independently buildable and
deployable, made the fault model tractable (one service's failure cannot
corrupt another's data), and left the scaling path open (a service can be
split out with a connection-string change). The lesson: a few invariants,
applied without exception, produce more leverage than many local optimisations.

## 2. "Decide once, share" is worth the blast radius

Putting every cross-cutting concern in a `tip_*` library meant resilience,
engine tuning, error envelopes, and indicator normalisation were each correct
in **one** place. The cost — a `tip_common` change rebuilds many images — was
real but small next to the alternative of 15 drifting copies. The lesson:
centralising shared logic is almost always right, provided the dependency
direction is strict (services → packages, never the reverse).

## 3. Async makes parallelism easy — which means you must choose when *not* to

The most instructive bug: AI legs run in `asyncio.gather` tripped GitHub
Models' concurrency cap. The fix was to **serialize** them
(`10_implementation/async_implementation.md`). The lesson: an async runtime
removes the friction that would otherwise stop you from over-parallelising;
the discipline to respect an external constraint becomes the engineer's
responsibility, not the framework's.

## 4. Background tasks must be owned, not fired and forgotten

A bare `asyncio.create_task` for the KEV backfill was garbage-collected
mid-flight. Moving to FastAPI `BackgroundTasks` (which holds a reference) fixed
it. The lesson: in async Python, an unreferenced task is a task that may
vanish — lifecycle ownership matters as much as the work itself.

## 5. Caching is about cost, not just speed

The cache-first insight design was driven less by latency than by **provider
quota**: re-generating an insight on every view would exhaust a 12/day model
allowance in minutes. And the "hunting hypothesis disappeared" bug taught that
a cache must **never overwrite good content with empty** on partial failure.
The lesson: when the scarce resource is quota/money, caching policy (and
empty-rejection) is a correctness concern, not an optimisation.

## 6. External dependencies are the real constraints

Every genuine bottleneck turned out to be external — NVD's unkeyed rate limit,
GitHub Models' quotas — not the platform's code
(`13_performance/bottlenecks.md`). The lesson: for an I/O-bound system, design
effort belongs in *tolerating and avoiding* external calls (resilience +
caching), not in micro-optimising local code that the latency budget shows is
not the bottleneck.

## 7. Security simplification is a legitimate engineering decision — when bounded

Disabling inter-service auth (keeping it only at the BFF edge) was the right
call **given** that the services run only on an isolated Docker network with
nothing but the frontend exposed. It also resolved a real startup race. The
lesson: security is contextual; a relaxation that is bounded by another control
(network isolation) and reversible by design (the wiring is dormant, not
deleted) is sound engineering, not negligence — provided it is documented
honestly (`15_limitations/security_limitations.md`).

## 8. Honest documentation of gaps is more valuable than a flattering narrative

Writing `15_limitations` and the "no benchmark / no test suite" admissions in
`11_testing` and `13_performance` was uncomfortable but correct. The lesson: a
reviewer trusts a project more when it names its own gaps with remedies than
when it hides them — and the act of naming them produced a concrete,
prioritised `16_future_work` roadmap that a glossier account would not have.

## 9. A working stack on real data beats a mocked one for validation — but not for regression

Validating against live NVD/abuse.ch/MITRE data caught real-world quirks a
mock never would. But it also meant no reproducible regression net, so bugs
were caught by humans re-running flows. The lesson: live-data validation and
automated regression testing are complementary, not substitutes — the project
got the first and deferred the second, and felt the absence.

## 10. The frontend is a security boundary, not just a view

Moving auth to the BFF edge made the Next.js app the security boundary
(httpOnly cookie, token injection, no CORS). The lesson: in a BFF
architecture, frontend choices (where the token lives, what the proxy
injects) are security-architecture choices, and must be reasoned about as such
(`12_technology_choices/frontend_stack.md`).

## The meta-lesson

The recurring theme across all ten: **principled constraints, applied
consistently and documented honestly, are what turned 15 services and a
frontend into a coherent system rather than a pile of parts.** Where the
project fell short — automated testing, operational tooling — it was not for
lack of a principle but for lack of time, and the principles themselves made
those gaps cheap to close later.
