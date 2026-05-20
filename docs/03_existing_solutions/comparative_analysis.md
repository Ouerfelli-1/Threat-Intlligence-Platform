# Comparative Analysis

A consolidated, criterion-by-criterion comparison of the platform against
the realistic alternatives, scored for *this customer's* requirements.

## Scoring legend

- ●●● full fit
- ●●○ partial fit
- ●○○ weak fit
- ○○○ no fit / not applicable

## Capability matrix

| Capability | Commercial TIP | OpenCTI | MISP | SIEM intel | Point tools | **TIP (this)** |
|---|---|---|---|---|---|---|
| Self-hosted / on-prem | ●○○ | ●●● | ●●● | ●●● | ●●● | ●●● |
| Single auditable AI egress | ○○○ | ○○○ | ○○○ | ○○○ | ○○○ | ●●● |
| Multi-source ingest | ●●● | ●●● | ●●○ | ●○○ | ●●○ | ●●● |
| Indicator normalisation + corroboration | ●●● | ●●● | ●●○ | ●○○ | ○○○ | ●●● |
| Confidence scoring (per-type) | ●●● | ●●○ | ●○○ | ●○○ | ○○○ | ●●● |
| Sub-10s IOC lookup | ●●● | ●●○ | ●●○ | ●●○ | ●●● | ●●● |
| CVE relevance vs *our* stack | ●●○ | ●○○ | ○○○ | ●○○ | ○○○ | ●●● |
| Actor likelihood ranking | ●●● | ●●○ | ○○○ | ○○○ | ○○○ | ●●● |
| Detection correlation (SIEM × IOC × TTP) | ●●● | ●○○ | ○○○ | ●●○ | ○○○ | ●●○ |
| Executive daily brief | ●●● | ○○○ | ○○○ | ○○○ | ○○○ | ●●● |
| Geopolitical outlook | ●●○ | ○○○ | ○○○ | ○○○ | ○○○ | ●●● |
| AI hunting hypotheses + Wazuh rules | ●●○ | ○○○ | ○○○ | ●○○ | ○○○ | ●●● |
| ATT&CK attack-flow generation | ●○○ | ●○○ | ○○○ | ○○○ | ○○○ | ●●● |
| Passive single-indicator investigation | ●●● | ●●○ | ●○○ | ●○○ | ●●○ | ●●● |
| OSINT dorking integrated into investigate | ●○○ | ○○○ | ○○○ | ○○○ | ●○○ | ●●● |
| Configurable notifications | ●●● | ●●○ | ●●○ | ●●● | ○○○ | ●●○ |
| Cost fit for 3 users | ●○○ | ●●○ | ●●● | ●●○ | ●●● | ●●● |
| Operational simplicity | ●●● (SaaS) | ●○○ | ●●○ | ●●○ | ●●● | ●●○ |
| Relevance tunability | ●○○ | ●●○ | ●○○ | ●●○ | ○○○ | ●●● |

## Where TIP intentionally scores lower

The platform is honest about two cells where it is `●●○` not `●●●`:

- **Detection correlation** — TIP correlates Wazuh alerts against IOCs and
  TTPs (orchestrator step 3), but a mature SIEM has deeper, lower-latency,
  rule-engine correlation. TIP adds the *intel-side* correlation; it does
  not replace the SIEM's real-time engine.
- **Operational simplicity** — a SaaS TIP has zero operational burden.
  TIP is single-host Docker Compose: simpler than OpenCTI, but it is
  still software the bank operates. The `make` targets and diagnostic
  scripts (`check-llm`, `smoke-test`) are the mitigation.
- **Notifications** — `●●○` because v1 ships SMTP only; the webhook
  channel is scaffolded but not wired to Slack/PagerDuty.

## Decision summary

TIP is the only option that scores `●●●` on the three criteria the
customer ranked highest:

1. **Single auditable AI egress** (regulatory necessity)
2. **CVE relevance vs our stack** + **actor likelihood ranking** (the
   synthesis that eliminates the 40-minute manual workflow)
3. **Cost fit for 3 users** (build + host vs enterprise licence)

No existing solution scored `●●●` on all three simultaneously. That gap
is the entire justification for the build.
