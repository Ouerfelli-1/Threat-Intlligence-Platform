# Global Architecture

## High-level system topology

This is the enterprise-level view: services, stores, boundaries — no
internal implementation. The companion `.mmd` file is
`diagrams/global_architecture.mmd`.

```mermaid
graph TB
    classDef ext fill:#222,stroke:#888,color:#ddd
    classDef store fill:#1a2a3a,stroke:#58a6ff,color:#fff
    classDef edge fill:#143,stroke:#3fb950,color:#fff
    classDef ai fill:#2a1a3a,stroke:#a371f7,color:#fff

    USER([SOC users<br/>Yassine / Amira / Karim])

    subgraph HOST["Single Docker Host — private bridge network"]
        FE["frontend (Next.js 16)<br/>SPA + BFF proxy :3000"]:::edge
        AUTH["auth :8000<br/>JWT issuer + RBAC"]:::edge

        subgraph INGEST["Ingestion services"]
            NEWS["news-collector :8001"]
            VULN["vuln-intel :8002"]
            THREAT["threat-intel :8003"]
            IOC["ioc-collector :8004"]
            ACTORS["threat-actors :8005"]
        end

        subgraph ANALYST["Analyst-facing services"]
            CMDB["cmdb :8007"]
            INTEG["integrations :8006"]
            ASM["asm :8009"]
            DW["domainwatch :8010"]
            II["indicator-intel :8013"]
        end

        subgraph BRAIN["AI synthesis"]
            ORCH["orchestrator :8014"]:::ai
            FLOW["flowviz :8008"]:::ai
        end

        subgraph PLATFORM["Platform services"]
            SCHED["scheduler :8011"]
            SEC["secrets :8012"]
            LLM["litellm :4000<br/>AI gateway"]:::ai
        end

        subgraph STORES["Data stores"]
            PGB[("PgBouncer :6432")]:::store
            PG[("Postgres<br/>15 schemas")]:::store
            RDS[("Redis")]:::store
        end
    end

    EXT["External sources<br/>CISA · NVD · EPSS · abuse.ch · OTX ·<br/>ransomware.live · HIBP · Shodan · crt.sh"]:::ext
    WAZUH["Wazuh SIEM"]:::ext
    MISP["MISP"]:::ext
    PROVIDER["AI provider<br/>(GitHub Models / OpenAI / Anthropic)"]:::ext
    SEARCH["Google CSE / DuckDuckGo"]:::ext

    USER --> FE
    FE --> AUTH
    FE --> INGEST
    FE --> ANALYST
    FE --> BRAIN
    FE --> SCHED

    INGEST --> EXT
    INTEG --> WAZUH
    INTEG --> MISP
    II --> SEARCH

    SCHED -.cron triggers.-> INGEST
    SCHED -.cron triggers.-> ORCH
    SCHED -.cron triggers.-> ASM
    SCHED -.cron triggers.-> DW
    SCHED -.cron triggers.-> INTEG

    ORCH --> INGEST
    ORCH --> ANALYST
    ORCH --> FLOW
    ORCH --> LLM
    INGEST --> LLM
    II --> LLM
    FLOW --> LLM
    LLM --> PROVIDER

    INGEST --> PGB
    ANALYST --> PGB
    BRAIN --> PGB
    AUTH --> PGB
    SCHED --> PGB
    SEC --> PGB
    PGB --> PG

    IOC --> RDS
    INGEST --> RDS
    ANALYST --> RDS

    AUTH --> SEC
    INGEST --> SEC
    ANALYST --> SEC
    BRAIN --> SEC
    LLM --> SEC
```

## Architectural layers

The system is best understood as five concentric layers:

| Layer | Members | Responsibility |
|---|---|---|
| **Edge** | frontend (SPA + BFF), auth | The only externally-reachable surface; authentication |
| **Capability** | 5 ingesters + 5 analyst-facing services | Business logic, owns data |
| **Synthesis** | orchestrator, flowviz | AI ranking + generation |
| **Platform** | scheduler, secrets, litellm | Cross-cutting platform services |
| **Storage** | PgBouncer, Postgres, Redis | Persistence + cache |

## Trust boundaries

```mermaid
flowchart LR
    subgraph internet["Internet (untrusted)"]
        U[User browser]
        EXT[External feeds + AI provider]
    end
    subgraph host["Docker host (trusted network)"]
        FE[frontend :3000]
        SVCS[14 internal services<br/>NOT externally exposed]
        STORES[(Postgres / Redis)]
    end
    U -- "HTTPS (only exposed port)" --> FE
    FE -- "private bridge net" --> SVCS
    SVCS -- "private bridge net" --> STORES
    SVCS -- "outbound only, via named sources + LiteLLM" --> EXT
```

Two boundaries matter:

1. **Browser ↔ frontend** — authenticated (JWT). The auth service
   validates tokens; the BFF forwards them.
2. **Host ↔ internet (outbound)** — constrained to named ingester
   sources and the single LiteLLM AI egress. No inbound path exists to
   any service except the frontend.

## Why this topology

- **One exposed port** minimises the external attack surface (P11).
- **Capability services own data** (P1/P2) so the topology can evolve
  service-by-service.
- **Synthesis isolated** behind LiteLLM (P3) so AI outages do not cascade.
- **Platform services centralise** cross-cutting concerns (one scheduler,
  one vault, one AI gateway) so "when/secrets/AI" each have one owner.
- **Storage shared but partitioned** (one Postgres, 15 schemas, one
  PgBouncer, one Redis) — single-host simplicity with logical isolation.

## Reading guide

- For *how requests flow*, see `request_lifecycle.md`.
- For *how services talk*, see `communication_patterns.md`.
- For *how it deploys*, see `deployment_architecture.md` and
  `infrastructure_topology.md`.
- For *one service in depth*, see `06_services/<service>/`.
