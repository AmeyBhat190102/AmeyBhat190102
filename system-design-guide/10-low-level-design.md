# 10 · Low-Level Design — From Boxes to Classes

HLD decides *what components exist*; LLD decides *what the code inside them looks like*: classes,
interfaces, state, concurrency, and the design patterns that keep it changeable. LLD interviews
give you a problem ("design a parking lot / BookMyShow / Splitwise") and expect clean, extensible
object design — often runnable.

---

## 1. The LLD method (use this every time)

```mermaid
flowchart LR
    A[1 Clarify requirements<br/>+ explicitly out-of-scope] --> B[2 Identify entities<br/>nouns → classes]
    B --> C[3 Define relationships<br/>is-a / has-a / uses]
    C --> D[4 Assign behavior<br/>verbs → methods, on the right class]
    D --> E[5 Apply patterns where<br/>change is expected]
    E --> F[6 Handle concurrency<br/>& persistence]
    F --> G[7 Walk a scenario<br/>end-to-end + edge cases]
```

Golden rules:
- **Composition over inheritance** — inherit for true "is-a", compose for capabilities.
- **Program to interfaces** — depend on `PaymentMethod`, not `CreditCard`.
- **Encapsulate what varies** — pricing rules, notification channels, storage backends behind interfaces.
- Small classes, single purpose; **no God objects** (a `Manager` that does everything).

## 2. SOLID — with the violation each one prevents

```mermaid
mindmap
  root((SOLID))
    S — Single Responsibility
      One reason to change
      ❌ UserService that validates, saves, emails, and logs
    O — Open/Closed
      Extend via new classes, don't edit stable code
      ❌ if type == 'A' … elif type == 'B' … growing forever
    L — Liskov Substitution
      Subtype must honor the base contract
      ❌ Square extends Rectangle breaking setWidth
    I — Interface Segregation
      Many small interfaces > one fat one
      ❌ Machine interface forcing print+scan+fax on all
    D — Dependency Inversion
      Depend on abstractions; inject them
      ❌ OrderService constructing MySQLConnection inside
```

**Dependency Injection** is D in practice: pass dependencies in via constructor → swappable →
**unit-testable with fakes**. This plus "hexagonal architecture" ([Ch 07](07-architecture-patterns.md))
is why well-designed services are easy to test.

Also know: **DRY** (but don't abstract prematurely — duplication is cheaper than the wrong
abstraction), **KISS**, **YAGNI**, **Law of Demeter** (talk to friends, not friends-of-friends),
**high cohesion / low coupling** (the umbrella goal of all of it).

## 3. Design patterns — the ones that actually appear

### Creational

```mermaid
classDiagram
    class NotificationFactory {
        +create(type) Notification
    }
    class Notification {
        <<interface>>
        +send()
    }
    class EmailNotification {
        +send()
    }
    class SmsNotification {
        +send()
    }
    class PushNotification {
        +send()
    }
    Notification <|.. EmailNotification
    Notification <|.. SmsNotification
    Notification <|.. PushNotification
    NotificationFactory ..> Notification : creates
```

- **Factory / Abstract Factory**: centralize "which concrete class?" decisions — new types without touching callers.
- **Builder**: construct complex objects step-by-step (`Request.builder().url(...).timeout(...).build()`) — beats 9-arg constructors.
- **Singleton**: one instance (config, connection pool). Use sparingly — hidden global state, test pain; prefer DI-scoped singletons. Know thread-safe init (double-checked locking / language idioms).
- **Prototype**: clone a configured template.
- **Object Pool**: reuse expensive objects — DB connections, threads (this is what connection pooling *is*).

### Structural

```mermaid
classDiagram
    class PaymentGateway {
        <<interface>>
        +charge(amount)
    }
    class StripeAdapter {
        +charge(amount)
    }
    class StripeSDK {
        +createPaymentIntent(cents)
    }
    PaymentGateway <|.. StripeAdapter
    StripeAdapter --> StripeSDK : wraps
    class CachedRepo {
        +get(id)
    }
    class Repo {
        <<interface>>
        +get(id)
    }
    class DbRepo {
        +get(id)
    }
    Repo <|.. CachedRepo
    Repo <|.. DbRepo
    CachedRepo --> DbRepo : decorates (adds caching)
```

- **Adapter**: make a third-party interface fit yours (every payment/notification vendor integration).
- **Decorator**: layer behavior (caching, retry, logging, metrics) around a component without changing it — how middlewares work.
- **Facade**: one simple interface over a messy subsystem (also the strangler-fig front).
- **Proxy**: stand-in controlling access — lazy loading, RPC stubs, access control.
- **Composite**: tree of parts treated uniformly (folders/files, UI, org charts).
- **Flyweight**: share immutable heavy state across many objects (glyphs, map tiles).

### Behavioral

```mermaid
classDiagram
    class PricingStrategy {
        <<interface>>
        +price(ride)
    }
    class SurgePricing {
        +price(ride)
    }
    class FlatPricing {
        +price(ride)
    }
    class RideService {
        -strategy: PricingStrategy
        +quote(ride)
    }
    PricingStrategy <|.. SurgePricing
    PricingStrategy <|.. FlatPricing
    RideService o--> PricingStrategy : injected
```

```mermaid
stateDiagram-v2
    [*] --> Created
    Created --> Paid: pay()
    Paid --> Shipped: ship()
    Shipped --> Delivered: deliver()
    Created --> Cancelled: cancel()
    Paid --> Refunded: refund()
    note right of Paid: State pattern — each state class defines<br/>which transitions are legal —<br/>illegal ones throw. No if-else jungles.
```

- **Strategy** ⭐: swap algorithms (pricing, routing, eviction, matching) — the most-used pattern in LLD interviews.
- **Observer** ⭐: publish state changes to subscribers — the in-process version of event-driven architecture; UI listeners, domain events.
- **State** ⭐: entity with lifecycle (order, ride, elevator) — legal transitions as first-class design.
- **Command**: reify an action as an object → queues, undo/redo, audit (a queue message *is* a serialized Command).
- **Chain of Responsibility**: pipeline of handlers, each passes along (middleware, approval workflows, support-ticket escalation).
- **Template Method**: skeleton algorithm with overridable steps.
- **Iterator**, **Mediator**, **Memento** (undo snapshots), **Visitor** (operations over object trees): recognize on sight.

> **Anti-pattern awareness** (name these when you avoid them): God object, anemic domain model
> (all logic in "services", entities are dumb structs), spaghetti if-else on type codes
> (→ Strategy/State/polymorphism), premature abstraction, singleton overuse.

## 4. Concurrency — the LLD differentiator

```mermaid
flowchart TB
    subgraph PROB["The problem"]
        p1["Two threads: read seat=FREE →<br/>both book it 💥 (race condition)<br/>Check-then-act is never atomic by default"]
    end
    subgraph TOOLS["The toolbox"]
        t1["Mutex/lock — one at a time"]
        t2["ReadWriteLock — many readers OR one writer"]
        t3["Atomic ops / CAS — lock-free counters"]
        t4["Semaphore — at most N concurrent (rate/pool limits)"]
        t5["Immutability — nothing to race on ✅ best fix"]
        t6["Concurrent collections, thread-safe queues"]
        t7["DB-level: unique constraints, SELECT FOR UPDATE,<br/>optimistic version columns"]
    end
```

### Deadlock — the 4 conditions & the standard fix

```mermaid
sequenceDiagram
    participant T1 as Thread 1
    participant T2 as Thread 2
    T1->>T1: lock(A) ✅
    T2->>T2: lock(B) ✅
    T1->>T1: lock(B) …waiting
    T2->>T2: lock(A) …waiting
    Note over T1,T2: 💀 Deadlock. Fix: GLOBAL LOCK ORDERING —<br/>always acquire A before B (e.g. lock accounts<br/>by ascending id in transfer(from,to)).<br/>Also: lock timeouts, tryLock, minimize hold time.
```

### Producer–consumer & thread pools

```mermaid
flowchart LR
    P1[Producers] -->|put — blocks when full<br/>= built-in backpressure| BQ[["BlockingQueue<br/>(bounded!)"]]
    BQ -->|take — blocks when empty| W[Worker threads<br/>fixed pool]
```

- **Thread pool sizing**: CPU-bound ≈ cores; IO-bound ≈ cores × (1 + wait/compute) — or use async IO.
- Know your language's model: Java executors & `synchronized`/`j.u.c`; Python GIL (threads fine for IO, processes for CPU, asyncio for high-concurrency IO); Go goroutines + channels ("share memory by communicating"); Node's single-threaded event loop (never block it).
- In interviews, booking/inventory problems **require** you to volunteer the race condition and fix it (lock, atomic DB op, or unique constraint) before being asked.

## 5. Persistence-aware LLD

- **Repository pattern**: `OrderRepository.save/findById` interface between domain and DB — swap Postgres for in-memory in tests.
- **Entities vs value objects** (DDD-lite): entities have identity (`User#42`); value objects are immutable data (`Money(50, "USD")` — never a float! store cents as integers).
- **Aggregate**: cluster of entities changed as one transactional unit through a root (Order + its lines) — your transaction boundary.
- **Schema design flows from the class model**: 1-N → foreign key; N-M → join table; inheritance → single-table (nullable columns) vs table-per-type. Enforce invariants in the DB too (unique, FK, checks) — the last line of defense.
- **Domain events**: aggregate emits `OrderPaid` in-process → handlers (and the outbox, [Ch 05](05-async-and-messaging.md)) react. This is how LLD connects to HLD event-driven design.

## 6. Worked mini-LLD — Parking Lot (the classic)

```mermaid
classDiagram
    class ParkingLot {
        -floors: List~Floor~
        -pricing: PricingStrategy
        -allocator: SpotAllocator
        +parkVehicle(v) Ticket
        +unpark(ticket) Receipt
    }
    class Floor {
        -spots: List~Spot~
    }
    class Spot {
        -type: SpotType
        -state: SpotState
        +assign(v)
    }
    class Vehicle {
        <<abstract>>
        -plate
    }
    class Bike
    class Car
    class Truck
    class Ticket {
        -id
        -entryTime
        -spot
    }
    class PricingStrategy {
        <<interface>>
        +fee(ticket) Money
    }
    class HourlyPricing
    class WeekendPricing
    class SpotAllocator {
        <<interface>>
        +find(vType) Spot
    }
    class NearestFirstAllocator
    ParkingLot o-- Floor
    Floor o-- Spot
    Vehicle <|-- Bike
    Vehicle <|-- Car
    Vehicle <|-- Truck
    ParkingLot o--> PricingStrategy
    ParkingLot o--> SpotAllocator
    PricingStrategy <|.. HourlyPricing
    PricingStrategy <|.. WeekendPricing
    SpotAllocator <|.. NearestFirstAllocator
    ParkingLot ..> Ticket : issues
```

Design notes to say out loud:
- Strategy for pricing & allocation (**O** in SOLID: add `EVPricing` without touching `ParkingLot`).
- Spot assignment is a **check-then-act race** → lock per spot / atomic claim (`UPDATE spots SET state='HELD' WHERE id=? AND state='FREE'`).
- `Ticket` is the persistence aggregate; money is a value object in cents.
- Extension probes they'll ask: multiple gates (concurrency), EV spots (new SpotType — enum + allocator handles it), reservations (State pattern on Spot: FREE→RESERVED→OCCUPIED).

## 7. Code-level API & error design

- Validate at the boundary; deeper layers assume valid inputs (parse, don't validate repeatedly).
- Exceptions vs result types: exceptional failures throw; expected outcomes ("insufficient funds") are modeled results.
- Make illegal states unrepresentable: enums/sealed types over strings, non-null by default, constructor-enforced invariants.
- **Composition roots**: wire dependencies at startup (DI container or plain factory functions), not scattered `new` calls.

---

## Advanced corner 🔬

- **Idempotent domain methods**: `order.markPaid()` safe to call twice — LLD's contribution to at-least-once delivery.
- **Optimistic locking in the ORM**: `@Version` column; catch the conflict exception and retry — the code-level view of [Ch 03](03-databases.md) OCC.
- **Event-sourced aggregates**: `apply(event)` + `decide(command) → events` — the LLD inside [Ch 07](07-architecture-patterns.md)'s event sourcing.
- **Lock striping**: N locks by `hash(key) % N` instead of one global lock — ConcurrentHashMap's trick; use it in your LLD rate limiter.
- **Double-checked locking & memory visibility**: locks also publish memory (happens-before); a flag without synchronization may never be *seen* by another thread — say "volatile/atomic" when you share flags.
- **Designing for testability** is designing well: if it's hard to test, the coupling is wrong.

---

### ✅ You should now be able to answer
1. Design BookMyShow seat booking: classes + the exact mechanism preventing double-booking under concurrency.
2. Refactor `if (type=="gold") … else if (type=="platinum") …` pricing — which pattern and why?
3. Implement an in-memory rate limiter (token bucket) that's thread-safe — where's the lock, and how do you avoid one global lock?

**Next:** [11 · Interview Blueprint →](11-interview-blueprint.md)
