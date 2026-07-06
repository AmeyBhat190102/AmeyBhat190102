# 08 · API Design, Gateways & Security — The Front Door

APIs are the contract your system makes with the world. This chapter covers designing them well
(REST/gRPC/GraphQL), protecting them (authN/Z, rate limiting), and fronting them (API gateway).

---

## 1. API styles

```mermaid
flowchart TB
    subgraph REST["REST (resource-oriented, HTTP+JSON)"]
        r1["GET /users/42/orders?status=open<br/>Uniform, cacheable, universal.<br/>Default for public APIs."]
    end
    subgraph GRPC["gRPC (RPC, protobuf/HTTP2)"]
        g1["orderService.GetOrders(userId)<br/>Binary, typed contracts, 4 streaming modes,<br/>codegen. Default service-to-service."]
    end
    subgraph GQL["GraphQL (query language)"]
        q1["query { user(id:42){ name orders{ total } } }<br/>Client picks fields, one round trip.<br/>Great for diverse frontends; costs: caching,<br/>N+1 resolvers (dataloader), query complexity limits."]
    end
    subgraph WH["Webhooks (reverse APIs)"]
        w1["You call the client when events happen.<br/>Sign payloads (HMAC), retry with backoff,<br/>consumers must be idempotent."]
    end
```

| Choose | When |
|---|---|
| REST | Public APIs, CRUD-ish domains, maximum compatibility |
| gRPC | Internal microservices, low latency, streaming, strict contracts |
| GraphQL | Many client types with divergent data needs; aggregating many services |
| Webhooks/events | Notifying external consumers |

## 2. REST design that passes review

- **Nouns for resources, verbs from HTTP**: `POST /orders`, not `POST /createOrder`. Nested only one level (`/users/42/orders`); beyond that, filter (`/orders?user_id=42`).
- **Status codes**: 200/201/202/204 · 400 (bad input) 401 (who are you) 403 (not allowed) 404 409 (conflict) 422 429 (slow down) · 500 502 503 504. Use 4xx vs 5xx correctly — clients decide retry behavior on it.
- **Errors**: structured body — `{ "code": "INSUFFICIENT_FUNDS", "message": "...", "trace_id": "..." }` (RFC 7807 Problem Details).
- **Versioning**: URL (`/v2/`) is the pragmatic default; header-based is cleaner but subtler. Real rule: **evolve compatibly** (additive fields, never repurpose), version rarely, sunset with deprecation headers & timelines.

### Pagination — offset vs cursor ⭐

```mermaid
flowchart TB
    subgraph OFFSET["Offset: ?page=50&limit=20"]
        o1["DB: OFFSET 1000 LIMIT 20 —<br/>scans & discards 1000 rows (slow deep pages);<br/>rows shift when data changes (skips/dupes)"]
    end
    subgraph CURSOR["Cursor: ?after=eyJpZCI6OTgw&limit=20"]
        c1["WHERE (created_at,id) < (cursor) ORDER BY ... LIMIT 20<br/>Index seek — O(page size) at any depth, stable.<br/>Cursor = opaque encoded (created_at,id)."]
    end
    OFFSET -->|at scale| CURSOR
```

### Idempotency keys ⭐ (payment-grade APIs)

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant D as DB
    C->>S: POST /payments {Idempotency-Key: 7f3a...}
    S->>D: INSERT key 7f3a (unique) + process + store response
    S-->>C: 201 {charge_id}
    Note over C: timeout! client retries
    C->>S: POST /payments {Idempotency-Key: 7f3a...}
    S->>D: key exists → return SAME stored response
    S-->>C: 201 {charge_id} (no double charge ✅)
```

Store the key + response atomically with the business write; expire after ~24 h. This is how
Stripe works, and the standard answer to "what if the client retries a POST?"

Other essentials: request validation at the edge · consistent naming (`snake_case` or `camelCase`, pick one) ·
timeouts on every call · **OpenAPI spec as the source of truth** (codegen clients/servers, contract tests) ·
HATEOAS exists (know the term; rarely used fully).

## 3. Authentication & authorization

```mermaid
flowchart LR
    AuthN["AuthN — who are you?"] --> AuthZ["AuthZ — what may you do?"]
```

### Sessions vs JWT

```mermaid
flowchart TB
    subgraph SESS["Server sessions"]
        s1["Login → session id in cookie →<br/>lookup in Redis per request.<br/>✅ instant revocation ✅ simple<br/>❌ shared store hop per request"]
    end
    subgraph JWT["JWT (stateless tokens)"]
        j1["Login → signed token {sub, roles, exp} →<br/>any service verifies the signature locally.<br/>✅ no lookup, cross-service ✅<br/>❌ can't revoke before expiry"]
    end
    HYB["✅ Production hybrid:<br/>short-lived access JWT (5–15 min)<br/>+ long-lived refresh token (stored server-side, revocable, rotated)"]
    SESS --> HYB
    JWT --> HYB
```

JWT hygiene: verify signature *and* `exp`/`aud`/`iss` · never put secrets in claims (payload is
only base64) · use `RS256`/asymmetric so services verify with a public key (JWKS endpoint) ·
maintain a small revocation/blocklist for logout-now cases.

### OAuth 2.0 + OIDC in one diagram

```mermaid
sequenceDiagram
    participant U as User
    participant App as Your app (client)
    participant IdP as Identity Provider (Google/Auth0)
    participant API as Resource server
    U->>App: "Login with Google"
    App->>IdP: redirect (authorization code flow + PKCE)
    U->>IdP: authenticate + consent
    IdP-->>App: authorization code
    App->>IdP: code + client secret → access token (+ id_token via OIDC)
    App->>API: request + Bearer access token
    API->>API: validate token (JWKS) → serve
```

Know the vocabulary: authorization code flow (+PKCE for public clients), client credentials flow
(service-to-service), scopes, id_token (OIDC = identity layer on OAuth).

### Authorization models

- **RBAC** — roles → permissions (`admin`, `editor`). Simple, coarse. Default.
- **ABAC** — rules over attributes (`user.dept == doc.dept && time < 6pm`). Flexible, complex.
- **ReBAC** — relationship-based (Google Zanzibar / SpiceDB): `user U is viewer of doc D because member of group G` — for Google-Docs-style sharing.
- Enforce **in the service layer, per resource** ("can THIS user touch THIS order"), not just at the gateway (which does coarse checks). Never trust client-supplied ids — the #1 real-world vuln (IDOR/BOLA).

## 4. Rate limiting ⭐ (a classic interview design on its own)

### Algorithms

```mermaid
flowchart TB
    subgraph TB1["Token bucket ⭐ default"]
        t1["Bucket capacity B, refills r tokens/sec.<br/>Request takes a token; empty → 429.<br/>Allows bursts up to B, sustained rate r."]
    end
    subgraph LB1["Leaky bucket"]
        l1["Queue drains at fixed rate —<br/>smooths output, no bursts."]
    end
    subgraph FW["Fixed window"]
        f1["Counter per minute.<br/>❌ 2× burst at window edges."]
    end
    subgraph SW["Sliding window (log / counter)"]
        s2["Weighted blend of adjacent windows —<br/>accurate, cheap. Common in production."]
    end
```

### Distributed rate limiter

```mermaid
flowchart LR
    C[Clients] --> GW[Gateway nodes] -->|"Lua script: atomic<br/>read-refill-decrement"| R[(Redis<br/>bucket per api_key)]
    GW -->|"429 + Retry-After +<br/>X-RateLimit-Remaining headers"| C
    NOTE["Local in-memory pre-limit per node (cheap first pass)<br/>+ Redis for the global limit.<br/>Fail-open vs fail-closed if Redis is down — decide explicitly!"]
```

Dimensions to limit on: per API key / user / IP / endpoint / tenant tier. Related: **quotas**
(daily caps), **concurrency limits** (max in-flight), **spike arrest**.

## 5. API Gateway — one front door

```mermaid
flowchart TB
    C[Web / Mobile / 3rd parties] --> GW[API Gateway<br/>Kong · APISIX · Envoy Gateway · AWS APIGW]
    GW --> F1[AuthN: validate JWT/API key]
    GW --> F2[Rate limiting & quotas]
    GW --> F3[Routing & versioning]
    GW --> F4[TLS termination, WAF, bot defense]
    GW --> F5[Request/response transform,<br/>caching, compression]
    GW --> F6[Metrics, logging, tracing headers]
    GW --> S1[Users svc] & S2[Orders svc] & S3[Payments svc]
```

Gateway (north-south: edge concerns, client traffic) vs **service mesh** (east-west:
service-to-service mTLS/retries). They coexist. Don't put business logic in the gateway.

## 6. Security essentials (the checklist)

```mermaid
flowchart TB
    subgraph EDGE["At the edge"]
        e1[TLS 1.2+ everywhere · HSTS<br/>WAF: SQLi/XSS signatures<br/>DDoS: CDN absorb + rate limit + anycast]
    end
    subgraph APPSEC["In the app"]
        a1[Parameterized queries — no SQLi<br/>Output encoding — no XSS<br/>CSRF tokens / SameSite cookies<br/>Input validation & size limits<br/>Secrets in a vault, never in code<br/>Least-privilege DB accounts]
    end
    subgraph DATA["Data"]
        d1[Encrypt in transit + at rest<br/>Hash passwords: bcrypt/argon2 + salt<br/>PII: minimize, mask in logs, GDPR delete paths<br/>Audit logs for sensitive actions]
    end
    EDGE --> APPSEC --> DATA
```

Also know: **OWASP Top 10** by name · **mTLS** for internal zero-trust · **signed URLs** for
direct-to-S3 upload/download (keeps large files off your app servers) · **HMAC request signing**
for machine-to-machine APIs (AWS SigV4 style) · **replay protection** via timestamp + nonce.

---

## Advanced corner 🔬

- **BOLA/IDOR** (`GET /orders/12345` — someone else's order): the top real-world API vuln; enforce object-level ownership checks in every handler.
- **GraphQL hardening**: depth & complexity limits, persisted queries, disable introspection publicly.
- **gRPC deadline propagation**: caller's deadline flows through the call chain so downstream work is cancelled when the client gave up — pairs with distributed tracing.
- **API keys vs OAuth for B2B**: keys are simple but coarse; OAuth client-credentials gives rotation, scopes, expiry.
- **Backpressure at the edge**: return `429` + `Retry-After` early rather than queueing to death — ties into load shedding ([Ch 09](09-reliability-and-observability.md)).
- **Schema-first dev**: write OpenAPI/proto first, generate stubs, contract-test in CI — prevents drift between docs and reality.

---

### ✅ You should now be able to answer
1. Design Stripe-style safe retries for `POST /payments`.
2. Access token vs refresh token — why both, and where is each stored/validated?
3. Build a per-API-key rate limiter for 100 gateway nodes: algorithm, storage, failure mode.
4. Cursor pagination: why, and what makes a stable cursor?

**Next:** [09 · Reliability & Observability →](09-reliability-and-observability.md)
