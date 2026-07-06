# 07 · Architecture Patterns — Shapes of Systems

How do you organize a whole product's backend? This chapter covers the macro-patterns —
monoliths, microservices, event-driven architecture, CQRS/event sourcing — and the honest costs of
each.

---

## 1. Monolith → modular monolith → microservices

```mermaid
flowchart TB
    subgraph MONO["Monolith"]
        m1[UI + Orders + Payments + Users<br/>one deployable, one DB]
    end
    subgraph MODMONO["Modular monolith ⭐ underrated"]
        mm1[Orders module] --- mm2[Payments module] --- mm3[Users module]
        mmdb[(one DB, schemas per module<br/>strict in-process interfaces)]
    end
    subgraph MICRO["Microservices"]
        s1[Orders svc] --> d1[(orders db)]
        s2[Payments svc] --> d2[(payments db)]
        s3[Users svc] --> d3[(users db)]
        s1 <-->|API / events| s2
    end
    MONO -->|module boundaries first| MODMONO -->|extract when forced| MICRO
```

| | Monolith | Microservices |
|---|---|---|
| Deploy | One unit — simple, but everything ships together | Independent deploys per team |
| Scale | Whole thing scales together | Scale hot services only |
| Failure | One bug can take everything down | Isolated (if built right) |
| Data | ACID transactions across features 🎉 | **No cross-service transactions** → sagas |
| Cost | Low ops overhead | Network hops, observability, service sprawl, org overhead |

**Rules that survive contact with reality:**
- Split by **business capability / bounded context** (DDD), never by technical layer ("the DAO service" is an anti-pattern).
- **Database-per-service** is what makes it real — shared databases recreate the monolith's coupling with extra steps ("distributed monolith").
- Extract when you have a *forcing function*: team scaling (Conway's law), divergent scaling needs, isolation requirements — not for fashion. At 2 YoE, defending a modular monolith is a strong senior signal.
- **Strangler fig** migration: put a facade/gateway in front of the legacy system, peel off one capability at a time, shrink the old system gradually — never big-bang rewrite.

```mermaid
flowchart LR
    U[Clients] --> F[Facade / Gateway]
    F -->|/payments/*| NEW[New payments svc]
    F -->|everything else| OLD[Legacy monolith]
    OLD -. shrinks over time .-> NEW
```

## 2. Communication between services

```mermaid
flowchart TB
    subgraph SYNC["Synchronous"]
        REST[REST/JSON<br/>simple, universal]
        GRPC[gRPC<br/>binary, streaming, contracts]
    end
    subgraph ASYNCC["Asynchronous"]
        EVT[Events via broker<br/>decoupled, resilient]
        CMD[Commands via queue<br/>directed work]
    end
    DECIDE{Does the caller need<br/>the answer to proceed?}
    DECIDE -->|yes| SYNC
    DECIDE -->|no| ASYNCC
```

- Chains of sync calls multiply latency and multiply failure probability → keep call depth shallow; prefer events for side effects.
- **Contracts**: OpenAPI / protobuf schemas, consumer-driven contract tests (Pact), backward-compatible evolution.
- **Service mesh** (Istio/Linkerd): sidecar proxies (Envoy) that handle retries, timeouts, mTLS, traffic splitting, and telemetry *outside* app code — platform-level reliability.

```mermaid
flowchart LR
    subgraph PodA["Service A pod"]
        A[App] --- PA[Envoy sidecar]
    end
    subgraph PodB["Service B pod"]
        PB[Envoy sidecar] --- B[App]
    end
    PA -->|mTLS, retries, LB,<br/>metrics, tracing| PB
    CP[Control plane: Istio<br/>policy & config] -.-> PA & PB
```

## 3. Event-driven architecture (EDA)

```mermaid
flowchart LR
    O[Order svc] -->|OrderPlaced| K[[Event broker]]
    K --> I[Inventory svc<br/>reserve stock]
    K --> N[Notification svc<br/>email]
    K --> A[Analytics svc]
    K --> S[Search indexer]
    NOTE["Order svc doesn't know or care who listens.<br/>New consumers added with ZERO producer changes."]
```

- **Event notification** ("something happened, come ask me") vs **event-carried state transfer** (event contains full data → consumers keep local copies, no callback needed) vs **event sourcing** (below). Know all three flavors.
- Costs: eventual consistency everywhere, harder debugging ("what called what?" → distributed tracing), duplicate delivery (idempotency, Ch 05), **event schema governance**.

## 4. CQRS — Command Query Responsibility Segregation

```mermaid
flowchart TB
    U[Client] -->|commands: POST/PUT| CS[Write model<br/>normalized, validated,<br/>transactional]
    CS --> WDB[(Write DB)]
    WDB -->|events / CDC| PROJ[Projector]
    PROJ --> RDB[(Read models:<br/>denormalized views,<br/>Elasticsearch, Redis, replicas)]
    U -->|queries: GET| QS[Read side] --> RDB
```

- Separate the write path (correctness, invariants) from read paths (each shaped exactly for a screen/query). Scale and optimize them independently.
- You already do lite-CQRS if you have read replicas or a search index. Full CQRS adds distinct models.
- Cost: **read models lag** the write model (eventual consistency) + projection rebuild machinery. Use for asymmetric read/write loads or wildly different read shapes — not for CRUD apps.

## 5. Event sourcing

```mermaid
flowchart LR
    subgraph LOG["Event store (source of truth, append-only)"]
        e1[AccountOpened] --> e2[Deposited $100] --> e3[Withdrew $30] --> e4[Deposited $5]
    end
    LOG -->|replay / fold| STATE["Current state: balance = $75"]
    LOG -->|project| RM[(Read models)]
    SNAP[Snapshots every N events<br/>to avoid replaying millions]
```

- Store **facts (events)**, derive state — instead of storing state and losing history.
- Superpowers: complete audit log, time travel/debugging, rebuild any new read model from history, natural fit with CQRS & EDA.
- Costs: event versioning/migration over years, snapshotting, no ad-hoc queries on the log (need projections), a real learning curve. Use where audit/history is the domain (ledgers, banking, compliance); don't use for a simple catalog.

## 6. Saga in practice (orchestration vs choreography)

```mermaid
flowchart TB
    subgraph ORCH["Orchestration — explicit conductor"]
        SO[Saga orchestrator /<br/>Temporal workflow] -->|1 reserve| I1[Inventory]
        SO -->|2 charge| P1[Payment]
        SO -->|3 ship| S1[Shipping]
        SO -->|on failure: compensate in reverse| I1
    end
    subgraph CHOR["Choreography — event chain"]
        O2[Order svc] -->|OrderPlaced| B[[broker]]
        B --> I2[Inventory] -->|StockReserved| B2[[broker]]
        B2 --> P2[Payment] -->|PaymentFailed| B3[[broker]]
        B3 --> I2
    end
```

| | Orchestration | Choreography |
|---|---|---|
| Flow visibility | Explicit in one place ✅ | Emergent, hard to trace at >3 steps |
| Coupling | Orchestrator knows all steps | Fully decoupled |
| Best for | Complex, long, business-critical flows | Simple 2–3 step reactions |

## 7. Other shapes worth knowing

```mermaid
flowchart TB
    subgraph BFF["Backend-for-Frontend"]
        W[Web BFF] & M[Mobile BFF] --> CORE[Core services]
    end
    subgraph CELL["Cell-based architecture"]
        R[Router] --> C1[Cell 1: full stack<br/>for customers 1–1000] & C2[Cell 2] & C3[Cell N]
        note["Blast radius = one cell.<br/>Used by AWS, Slack, DoorDash"]
    end
    subgraph SLESS["Serverless / FaaS"]
        EVQ[HTTP / queue / cron event] --> FN[Function<br/>scale-to-zero]
        FN --> MGD[(Managed state:<br/>DynamoDB, S3)]
        note2["Pay-per-use, no servers.<br/>Cold starts, execution limits,<br/>vendor lock-in. Great for spiky,<br/>event-shaped workloads."]
    end
```

- **BFF**: one aggregation layer per client type — avoids one-size-fits-none general APIs.
- **Cell-based**: shard *the entire stack* by customer; failures and deploys hit one cell, not everyone. The scaled-up version of "bulkheads" ([Ch 09](09-reliability-and-observability.md)).
- **Serverless**: also know **Lambda-behind-API-Gateway**, DynamoDB streams triggers; and the **12-factor app** principles that make services container/cloud-friendly (config in env, stateless processes, logs to stdout, disposability).
- **Hexagonal / clean architecture** (ports & adapters): domain logic at the center, infrastructure (DB, HTTP, brokers) behind interfaces at the edges — this is the LLD foundation that makes services testable ([Ch 10](10-low-level-design.md)).
- **Multi-tenancy models**: shared-everything (tenant_id column) → shared app, DB-per-tenant → silo-per-tenant. Trade isolation/noisy-neighbor protection against cost & ops.

## 8. Kubernetes-era deployment vocabulary (one diagram)

```mermaid
flowchart TB
    ING[Ingress / Gateway] --> SVC1[Service<br/>stable virtual IP]
    SVC1 --> P1[Pod] & P2[Pod] & P3[Pod]
    DEP[Deployment<br/>declares replicas & image] --> P1 & P2 & P3
    HPA[HorizontalPodAutoscaler] -.scales.-> DEP
    CM[ConfigMap / Secret] -.-> P1
    NOTE["Liveness probe → restart me if dead<br/>Readiness probe → route traffic to me only when ready<br/>Requests/limits → capacity planning per pod"]
```

You don't need to be a k8s expert for design interviews — you need this vocabulary: pod, service,
deployment, autoscaler, probes, and "the platform restarts failed containers and reschedules them."

---

## Advanced corner 🔬

- **Distributed monolith** — the failure mode to name: microservices that must deploy together, share a DB, or chain sync calls. All of the cost, none of the benefit.
- **Sidecar / ambassador / adapter patterns**: attach infrastructure behavior to a service via a companion container.
- **Feature flags** as an architecture tool: decouple deploy from release, canary by cohort, kill switches for risky paths.
- **Data mesh** (buzzword awareness): domain-owned analytical data products vs a central warehouse team.
- **Micro-frontends**: the same decomposition idea applied to UIs — know it exists.
- **Conway's law**: your architecture will mirror your org chart; team boundaries are architectural decisions.

---

### ✅ You should now be able to answer
1. Your startup has 8 engineers and a Django monolith struggling at 5k QPS. Microservices? (Probably not — argue the alternative.)
2. Design order fulfillment across 4 services with money involved. Orchestration or choreography, and why?
3. What breaks first when two services share one database?

**Next:** [08 · API Design & Security →](08-api-design-and-security.md)
