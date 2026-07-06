# 02 · Scaling & Load Balancing — From 1 Server to Planet Scale

This chapter is the canonical "evolution of an architecture" story. Every real system walked
roughly this path; interviews expect you to narrate it with reasons.

---

## 1. The evolution, step by step

```mermaid
flowchart TB
    subgraph S1["Stage 1 — One box"]
        U1[Users] --> A1[App + DB on one server]
    end
    subgraph S2["Stage 2 — Separate the DB"]
        U2[Users] --> A2[App server] --> D2[(DB server)]
    end
    subgraph S3["Stage 3 — Horizontal app tier"]
        U3[Users] --> LB[Load Balancer]
        LB --> A3a[App 1] & A3b[App 2] & A3c[App N]
        A3a & A3b & A3c --> D3[(DB)]
    end
    subgraph S4["Stage 4 — Cache + read replicas"]
        U4[Users] --> LB4[LB] --> A4[App tier]
        A4 --> C4[(Cache)]
        A4 -->|writes| P4[(Primary DB)]
        A4 -->|reads| R4[(Replicas)]
        P4 -.replication.-> R4
    end
    S1 --> S2 --> S3 --> S4
```

```mermaid
flowchart TB
    subgraph S5["Stage 5 — Async + CDN + sharding (the 'standard web-scale' shape)"]
        U[Users] --> CDN[CDN / Edge]
        CDN --> GW[API Gateway / LB]
        GW --> SVC[Stateless app tier<br/>auto-scaled]
        SVC --> CACHE[(Distributed cache)]
        SVC --> Q[[Message queue]]
        Q --> W[Async workers]
        SVC --> SH1[(DB shard 1)] & SH2[(DB shard 2)] & SH3[(DB shard N)]
        SVC --> OS[(Object storage<br/>images, files)]
        W --> SH1
    end
```

**Why each step happened:**
| Bottleneck felt | Fix | Chapter |
|---|---|---|
| CPU/RAM contention between app & DB | Split tiers | here |
| One app server maxed out | Horizontal scale + LB | here |
| DB reads maxed out | Cache + read replicas | 03, 04 |
| Slow requests doing heavy work inline | Queue + workers | 05 |
| DB writes/storage maxed out | Sharding | 03 |
| Global users, static assets slow | CDN | here |

## 2. Vertical vs horizontal scaling

```mermaid
flowchart LR
    subgraph V["Vertical (scale UP)"]
        v1[Bigger machine<br/>more CPU/RAM]
    end
    subgraph H["Horizontal (scale OUT)"]
        h1[Server] --- h2[Server] --- h3[Server]
    end
```

| | Vertical | Horizontal |
|---|---|---|
| Ceiling | Hard hardware limit, cost grows super-linearly | Near unlimited |
| Availability | Still a single point of failure | Survives node loss |
| Complexity | None | State, coordination, LB, deployment |
| When | Databases early on, quick wins | Stateless services, everything at scale |

### The prerequisite: statelessness

```mermaid
flowchart LR
    subgraph BAD["❌ Sticky state in server memory"]
        U1[User] --> S1[Server A<br/>holds session]
        U1 -.next request routed to B.-> S2[Server B<br/>❓ who are you?]
    end
    subgraph GOOD["✅ State externalized"]
        U2[User] --> Sx[Any server]
        Sx --> R[(Redis: sessions)]
        Sx --> DB[(DB: data)]
    end
```

Rules: sessions → Redis/JWT; files → object storage; locks/counters → shared store. A server you
can kill at any moment with zero data loss is a server you can auto-scale.

## 3. Load balancers

### L4 vs L7

```mermaid
flowchart TB
    subgraph L4["Layer 4 (transport)"]
        a[Sees IP:port + TCP/UDP only<br/>NAT / passthrough<br/>Very fast, millions of conns<br/>e.g. AWS NLB, LVS]
    end
    subgraph L7["Layer 7 (application)"]
        b[Terminates TLS, reads HTTP<br/>Routes by path/host/header/cookie<br/>Retries, compression, WAF<br/>e.g. Nginx, Envoy, ALB, HAProxy]
    end
    Client --> L4 --> L7 --> Servers
```

Typical production stack: **DNS/GeoDNS → L4 LB → L7 LB / gateway → services.**

### Algorithms

```mermaid
flowchart TB
    LB{Load balancing<br/>algorithm}
    LB --> RR["Round Robin —<br/>equal servers, uniform requests"]
    LB --> WRR["Weighted RR —<br/>heterogeneous servers / canary %"]
    LB --> LC["Least Connections —<br/>requests vary in duration"]
    LB --> LRT["Least Response Time —<br/>latency-sensitive"]
    LB --> IPH["Hash (IP / cookie / header) —<br/>stickiness, per-user cache locality"]
    LB --> P2C["Power of Two Choices —<br/>pick 2 random, take less loaded<br/>(near-optimal, cheap — used by Envoy)"]
```

- **Consistent hashing** at the LB (hash on user/session key) keeps a user on the same backend even as servers join/leave — details in [Ch 03](03-databases.md#consistent-hashing).
- **Health checks**: active (LB probes `/healthz`) + passive (eject a backend after N failures). Distinguish **liveness** (process up) from **readiness** (able to serve — dependencies warm).
- **The LB itself must not be a SPOF**: pairs with VRRP/keepalived and a floating IP, or cloud LBs which are themselves distributed.

### Sticky sessions — know it, avoid it

Stickiness (cookie/IP-based) pins a user to one server. It fights auto-scaling and failover.
Prefer external session stores; accept stickiness only for legacy apps or WebSocket connection
affinity (and even then, store *state* externally).

## 4. Auto-scaling

```mermaid
flowchart LR
    M[Metrics: CPU, QPS,<br/>queue depth, p99 latency] --> P{Policy}
    P -->|threshold / target tracking| ASG[Add or remove instances]
    P -->|scheduled| ASG
    P -->|predictive| ASG
    ASG --> WARM[⚠️ cold start & warm-up time<br/>scale-out lag → keep headroom]
```

Advanced notes:
- Scale on the **customer-facing symptom** (latency, queue lag), not just CPU.
- **Scale out fast, scale in slow** (avoid flapping).
- Provisioned headroom ≈ expected peak while new capacity boots.

## 5. CDN & the edge

```mermaid
flowchart LR
    U[User in Mumbai] -->|~20ms| E[CDN edge PoP<br/>Mumbai]
    E -->|cache hit: done| U
    E -->|miss| O[Origin in Virginia<br/>~200ms]
    O --> E --> U
    subgraph Origin
        O --> S3[(Object storage)]
        O --> APP[App servers]
    end
```

- **Pull CDN** (lazy: edge fetches on first miss — default) vs **Push CDN** (you upload proactively — for large, predictable assets like video releases).
- Cache key = URL (+ selected headers). Control with `Cache-Control: max-age`, `s-maxage`, `ETag`/`If-None-Match`, and **cache busting** via versioned URLs (`app.v2.js`).
- CDNs can cache **API responses** too (public, read-heavy GETs) and run **edge compute** (auth token validation, A/B routing, personalization at the edge).
- Also your first line of **DDoS absorption** and TLS termination near the user.

## 6. Multi-region 🌍 (advanced)

```mermaid
flowchart TB
    GD[GeoDNS / Anycast] --> R1 & R2
    subgraph R1["Region: us-east"]
        LB1[LB] --> A1[Services] --> D1[(DB primary)]
    end
    subgraph R2["Region: ap-south"]
        LB2[LB] --> A2[Services] --> D2[(DB replica /<br/>regional primary)]
    end
    D1 <-.async replication.-> D2
```

Three postures, increasing cost & complexity:
1. **Active–passive**: one live region, warm standby; failover via DNS. Simple; minutes of RTO; replication lag = potential data loss (RPO > 0).
2. **Active–active, read-local/write-global**: all regions serve reads locally; writes routed to a single home region (per tenant/user — "home-region" partitioning).
3. **Active–active, write-anywhere**: multi-master with conflict resolution (CRDTs, last-write-wins) — hardest; needed for global low-latency writes (see [Ch 06](06-distributed-systems-theory.md)).

> Interview gold: mention **data residency laws** (e.g., data of EU users stays in EU) as a
> *non-technical* driver of multi-region design.

---

## Advanced corner 🔬

- **Thundering herd on scale events**: all clients reconnect to a fresh node at once → jittered reconnect/backoff.
- **Connection draining**: on deploy/scale-in, LB stops sending new requests and lets in-flight ones finish before killing the node.
- **Direct Server Return (DSR)**: L4 trick where responses bypass the LB — for very high egress (video).
- **Global Server Load Balancing (GSLB)**: health-aware DNS steering across regions.
- **Little's Law**: `concurrency = throughput × latency`. A service at 1,000 QPS with 200 ms latency holds 200 in-flight requests — sizes your thread pools and connection pools.

---

### ✅ You should now be able to answer
1. Walk from 1 server to a sharded, cached, multi-region system, naming the bottleneck that forces each step.
2. Why is "least connections" better than round robin for a mixed workload?
3. Why must services be stateless before horizontal scaling, and where does the state go?

**Next:** [03 · Databases →](03-databases.md)
