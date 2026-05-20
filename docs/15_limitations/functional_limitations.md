# Functional Limitations

These concern what the platform does (or does not do) at the feature level.

## L18 — AI availability depends on external provider quotas

**The limitation.** AI features depend on GitHub Models (via LiteLLM), whose
free quotas are tight (`gpt-5-chat` 12/day + 1 concurrent; `gpt-4o` 2
concurrent). When all models are exhausted, AI generation stops until the
quota resets (`13_performance/bottlenecks.md`).

**Why.** The deployment uses free/low-cost provider tiers.

**Mitigation.** Strong, layered: AI is off the ingest hot path (the platform
keeps running without it), the smart-model cascade spreads load, cache-first
insights and the 24h AI response cache avoid re-billing, and partial-failure
merges never erase good content.

**Residual risk.** During exhaustion, *new* AI insights cannot be generated
(existing ones still serve from cache). **Remedy:** paid provider tiers / more
keys on the proxy (`16_future_work`).

## L19 — NVD throughput without an API key

**The limitation.** A full CVE backfill takes ~90 minutes without an
`NVD_API_KEY` (NVD allows ~5 req/30s unkeyed) (`13_performance/
bottlenecks.md`).

**Why.** No NVD key was provisioned.

**Mitigation.** Backfill runs as a non-blocking background task; steady-state
uses incremental `lastModified` pulls; a key (if added) lifts the limit 10×.

**Residual risk.** Initial CVE population is slow. **Remedy:** provision an
NVD API key (trivial, free) (`16_future_work`).

## L20 — No real-time push (WebSocket/SSE)

**The limitation.** The UI refreshes via SWR polling (dashboard 30s, lists
60s); there is no WebSocket/SSE for live updates (`12_technology_choices/
frontend_stack.md`).

**Why.** Polling was sufficient for an analyst tool; real-time was out of
scope.

**Mitigation.** Polling intervals are tuned per surface; the notification
subsystem provides event-driven email/Telegram alerts for the cases that
genuinely need push.

**Residual risk.** New data appears with up to one poll-interval of delay.
**Remedy:** SSE for live alert/feed updates (`16_future_work`).

## L21 — Deferred analyst features (watchlists / saved searches)

**The limitation.** Watchlists, saved searches, and a cross-service
"escalated items" inbox were explicitly deferred (the Phase 4 candidates).

**Why.** They require a notification surface that was scoped out of the
implemented phases.

**Mitigation.** The `analyst_status` triage (`relevant` / `not_relevant` /
`escalated`) and the notification subsystem provide the building blocks.

**Residual risk.** No persistent saved-filter subscriptions yet. **Remedy:**
the Phase 4 watchlist design (`16_future_work`).

## L22 — One-way CMDB↔ASM sync

**The limitation.** Profile changes propagate CMDB→ASM (targets), but there is
no ASM→CMDB back-channel for newly discovered subdomains
(Phase 3 design notes).

**Why.** v1 scoped the sync as one-directional.

**Mitigation.** The forward sync (profile → ASM targets) works and is
operator-visible via `profile_change_log` and ASM `/health/sources`.

**Residual risk.** ASM discoveries are not auto-proposed back into the
profile. **Remedy:** an ASM→profile back-channel (`16_future_work`).

## L23 — AI-extracted IOCs are not auto-promoted

**The limitation.** IOCs the AI extracts from articles/threats are written to
the insight payload, not auto-promoted into the IOC library; an analyst must
promote them.

**Why.** A deliberate operator decision — the analyst is the gate, to avoid
polluting the IOC store with unvetted AI output.

**Mitigation.** A `promote-iocs` endpoint lets the analyst promote selected
ones at a marked reliability.

**Residual risk.** None adverse — this is a *chosen* safeguard, listed here
only for completeness. **Remedy:** n/a (working as intended).

## Summary

| ID | Limitation | Severity | Remedy in §16 |
|---|---|---|---|
| L18 | AI quota dependence | medium | paid tiers / more keys |
| L19 | NVD throughput unkeyed | low | provision NVD key |
| L20 | No real-time push | low | SSE |
| L21 | Deferred watchlists | low | Phase 4 |
| L22 | One-way CMDB↔ASM | low | back-channel |
| L23 | No IOC auto-promote | n/a (by design) | — |
