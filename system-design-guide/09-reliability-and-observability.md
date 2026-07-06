# 09 · Reliability & Observability — Designing for Failure

Everything fails: disks, networks, dependencies, your own deploys. Reliability is not the absence
of failure — it's the containment of failure. This chapter is what separates "it works on the
diagram" from production engineering.

---

## 1. The language of reliability

```mermaid
flowchart LR
    SLI["SLI — a measurement<br/>'p99 latency', '% of 2xx responses'"] -->
    SLO["SLO — your internal target<br/>'99.9% of requests OK over 30d'"] -->
    SLA["SLA — the contract with $$ penalties<br/>always looser than the SLO"]
    SLO --> EB["Error budget = 1 − SLO<br/>99.9% ⇒ 43 min down/month.<br/>Budget left → ship fast.<br/>Budget burned → freeze & stabilize."]
```

| Nines | Downtime/year | Reality check |
|---|---|---|
| 99% | 3.65 days | hobby |
| 99.9% | 8.7 h | good SaaS |
| 99.99% | 52 min | serious infra, multi-AZ mandatory |
| 99.999% | 5 min | telecom-grade, enormously expensive |

- Serial dependencies **multiply**: five 99.9% services in a chain ≈ 99.5%. This is the math behind "keep call chains shallow."
- Redundancy math: two independent 99% replicas ≈ 99.99% *if* failures are truly independent (same rack/AZ/deploy = not independent). Hence **multi-AZ** as table stakes and **multi-region** for the highest tiers.
- **MTTR beats MTBF**: you can't prevent all failures; you can detect and recover in minutes. Optimize time-to-detect + time-to-mitigate.
- Percentiles, not averages: **p50/p95/p99** — the p99 is what your heaviest users feel, and **tail latency amplification** means a page fanning out to 100 backends hits somebody's p99 almost every time. (Mitigations: hedged requests, tight timeouts.)

## 2. Resilience patterns (the big six)

### Timeouts, retries, and their dark side

```mermaid
sequenceDiagram
    participant A as Service A
    participant B as Service B (degraded)
    A->>B: request (timeout 500ms)
    Note over B: slow…
    A->>B: retry 1 (after 100ms + jitter)
    A->>B: retry 2 (after 200ms + jitter)
    Note over A,B: ⚠️ Retries MULTIPLY load on an already-sick service —<br/>a retry storm turns degradation into outage.
```

Rules: every network call has a **timeout** (no infinite defaults) · retry only **idempotent** or
idempotency-keyed operations · **exponential backoff + jitter** · **retry budgets** (e.g. retries
≤ 10% of traffic) · cap total attempts across the chain (or only the edge retries).

### Circuit breaker

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Open: failure rate > threshold<br/>(e.g. 50% of last 20 calls)
    Open --> HalfOpen: after cool-down (30s)
    HalfOpen --> Closed: probe requests succeed
    HalfOpen --> Open: probe fails
    note right of Open: calls fail FAST (no waiting on timeouts),<br/>sick dependency gets room to recover,<br/>fallback served meanwhile
```

### Bulkheads, shedding, degradation

```mermaid
flowchart TB
    subgraph BULK["Bulkhead — isolate resources"]
        b1["Separate pools/quotas per dependency:<br/>slow Payments API can exhaust ITS 10 connections,<br/>but Search still has its own 10.<br/>(Same idea at macro scale = cell-based architecture)"]
    end
    subgraph SHED["Load shedding — reject early"]
        s1["Over capacity? Return 429/503 for<br/>low-priority traffic at the front door<br/>instead of slowly failing everything.<br/>Prioritize: checkout > browse > analytics."]
    end
    subgraph DEG["Graceful degradation — partial > none"]
        g1["Recommendations down → show bestsellers.<br/>Search down → category browse.<br/>Feature flags as kill switches."]
    end
```

### The one everyone forgets: metastable failures & cold starts

A system that's healthy at steady state can be unable to *recover*: cache flushed → DB
overwhelmed → timeouts → retries → more load. Defenses: cache warming, retry budgets, load
shedding at startup, slow-start traffic ramping. Name this in interviews; it's a strong signal.

## 3. Observability — the three pillars (+ one)

```mermaid
flowchart TB
    subgraph M["📈 Metrics (Prometheus/Grafana)"]
        m1["Numeric time series, cheap, aggregated.<br/>RED per service: Rate, Errors, Duration.<br/>USE per resource: Utilization, Saturation, Errors.<br/>+ business metrics (orders/min!)"]
    end
    subgraph L["📜 Logs (ELK/Loki)"]
        l1["Structured JSON events, searchable.<br/>Include trace_id in every line.<br/>Sample noisy ones; never log PII/secrets."]
    end
    subgraph T["🕸️ Traces (OpenTelemetry/Jaeger)"]
        t1["One request's journey across services;<br/>spans show WHERE the 2s went.<br/>Context propagated via headers (traceparent)."]
    end
    M & L & T --> CORR["Correlate by trace_id —<br/>metric alert → exemplar trace → logs of that request"]
```

### Distributed tracing view

```mermaid
gantt
    title One request, traced (total 900ms — where did it go?)
    dateFormat X
    axisFormat %L ms
    section Gateway
    auth + route          :0, 40
    section Order svc
    handler               :40, 860
    section Payment svc
    charge (external PSP) :120, 700
    section DB
    insert order          :830, 860
```

> The trace instantly shows the external payment call is 65% of latency → cache/parallelize/async it.

### Alerting & health

- Alert on **symptoms users feel** (SLO burn rate, error %, p99), not causes (CPU%) — causes go on dashboards.
- Two burn-rate alerts: fast-burn (page now) + slow-burn (ticket).
- Every alert must be **actionable** with a runbook; alert fatigue is an outage-multiplier.
- `/healthz` liveness vs `/ready` readiness (checks dependencies) — wired into LB/k8s ([Ch 02](02-scaling-and-load-balancing.md), [Ch 07](07-architecture-patterns.md)).
- **Synthetic monitoring**: scripted probes of key flows from outside, catching what internal metrics miss.

## 4. Deployment safety

```mermaid
flowchart TB
    subgraph ROLL["Rolling"]
        r1[Replace instances in batches<br/>default k8s behavior]
    end
    subgraph BG["Blue-Green"]
        b1[Two full environments,<br/>switch traffic atomically,<br/>instant rollback = switch back<br/>💰 2× infra during deploy]
    end
    subgraph CAN["Canary ⭐"]
        c1[1% → 5% → 25% → 100%<br/>auto-rollback on metric regression<br/>compare canary vs baseline cohort]
    end
    ROLL --> BG --> CAN
    FF["Feature flags: deploy ≠ release.<br/>Code ships dark, enable per cohort,<br/>kill switch in seconds."]
```

Zero-downtime requires: backward-compatible schema migrations (**expand → migrate → contract**),
connection draining, versioned APIs/events, and N and N+1 running simultaneously without conflict.

## 5. Disaster recovery

```mermaid
flowchart LR
    D[💥 Disaster] --> RPO["RPO — how much data<br/>can we lose?<br/>(backup/replication frequency)"]
    D --> RTO["RTO — how long until<br/>we're back?<br/>(failover automation)"]
    RPO & RTO --> STRAT{Strategy by cost}
    STRAT --> S1["Backups + restore<br/>RTO hours, cheapest"]
    STRAT --> S2["Pilot light<br/>data replicated, infra cold"]
    STRAT --> S3["Warm standby<br/>scaled-down copy running"]
    STRAT --> S4["Active-active multi-region<br/>RTO ~0, most complex ($$$)"]
```

Non-negotiables: **test your restores** (an untested backup is a hope, not a plan) · backups
isolated from prod credentials (ransomware) · run **game days / chaos drills** (Chaos Monkey:
inject failure on purpose, verify the system tolerates it) · practice failover before you need it.

## 6. Operational culture (say these words)

- **Blameless postmortems**: every incident → timeline, contributing causes, action items. Systems fail, processes fix.
- **Runbooks** per alert; **on-call rotations** with escalation.
- **Capacity planning**: forecast + load test (know **p99 under load**, find the knee of the curve) before Black Friday, not during.
- **Graceful shutdown**: catch SIGTERM → stop accepting → drain in-flight → close connections. The difference between "deploy" and "blip of 500s every deploy."

---

## Advanced corner 🔬

- **Hedged requests**: send a duplicate to a second replica if the first hasn't answered by p95 — Google's tail-latency killer; requires idempotent reads.
- **Adaptive concurrency limits** (Netflix): auto-discover a service's capacity from latency gradients instead of fixed limits.
- **Brownout**: deliberately disable expensive features under load (drop personalization, serve static fallbacks).
- **Watchdog vs cascading health checks**: a health check that checks dependencies can turn one dependency's blip into a full-fleet "unready" cascade — keep readiness checks shallow, use circuit breakers for deps.
- **Correlated failure domains**: rack, AZ, deploy pipeline, cert expiry, DNS, config push — the last three cause more global outages than hardware. Stagger config rollouts like code rollouts.
- **Jidoka / automation levels**: auto-rollback, auto-remediation (restart, failover) — with rate limits so automation itself can't run amok.

---

### ✅ You should now be able to answer
1. Your dependency's p99 jumped 10×. Trace the failure through your service (threads/conn pool exhaustion) and list the four patterns that would have contained it.
2. Define an SLO for a checkout API and design its two alerts.
3. Why can retries make an outage worse, and what three mechanisms bound them?
4. Design the deploy pipeline for a payments service (canary + flags + compatible migrations + auto-rollback).

**Next:** [10 · Low-Level Design →](10-low-level-design.md)
