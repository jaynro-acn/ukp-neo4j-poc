# Plan: neo4j-retrieval-poc

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Six sequential tasks: install the stack, seed the graph, seed the vector store,
implement both retrieval patterns, and document findings. Each task is a standalone
script a single session can complete. The riskiest part is the `entityId` bridge
between Qdrant and Neo4j — if IDs don't match, the semantic-first hop returns nothing.
The bridge is validated explicitly in T3 before building the retrieval scripts.

## Constraints

- Node types and relationship types must match the 7+6 schema defined in the spec
- Embed `name + description` together — not name alone — to produce rich vectors
- No AWS, no live external connections

## Construction tests

**Integration tests:** the semantic-first script (T5) is an end-to-end test across
Qdrant → `entityId` resolution → Neo4j traversal — runs as a single script.

**Disambiguation test:** query `"what handles an order?"` must return results from
both Commerce (Order Confirmation / order-service) and Payments (Authorization /
auth-gateway) domains in top-3. This is the key calibration check.

**Manual verification:**
- After T2: inspect Neo4j Browser at `http://localhost:7474` — confirm all 7 node types
  and 6 relationship types are present
- After T3: run Qdrant verify block — confirm all 24 `entityId`s resolve to Neo4j nodes
- After T5: run disambiguation query and confirm cross-domain results

## Design (LLD)

### Data & schema

**Neo4j node types:**

| Label | Key properties | Notes |
|---|---|---|
| `ValueStream` | `entityId`, `name`, `description` | Shared across domains |
| `Capability` | `entityId`, `name`, `level` (L1/L2/L3), `description` | Hierarchy via HAS_CHILD |
| `Domain` | `entityId`, `name`, `description` | Commerce, Payments |
| `Subdomain` | `entityId`, `name`, `description` | Checkout (2 BCs), Transaction Processing |
| `BoundedContext` | `entityId`, `name`, `ubiquitous_language`, `description` | UL conflict on "Order" |
| `Component` | `entityId`, `name`, `type`, `description` | One per bounded context |
| `Contract` | `entityId`, `name`, `type` (event/rest), `description` | |

**Neo4j relationship types:**

| Type | From → To | Meaning |
|---|---|---|
| `INVESTS_IN` | ValueStream → Capability | value stream funds this capability |
| `HAS_CHILD` | Capability → Capability | L1→L2→L3 hierarchy |
| `CONTAINS` | Domain→Subdomain, Subdomain→BoundedContext | structural containment |
| `IMPLEMENTS` | Component → BoundedContext | component realises this context |
| `DEPENDS_ON` | Component→Component, BoundedContext→BoundedContext | runtime dependency |
| `EXPOSES` | Component → Contract | component publishes this contract |

**Qdrant schema:**
Each document: `{ entityId, name, type, text, vector }` — `text` = name + description
(+ ubiquitous_language for BoundedContext nodes). `entityId` is the bridge key.

### Key design decisions

- **Two domains, one shared ValueStream** — tests cross-domain graph traversal via the
  shared `Digital Sales` ValueStream node
- **Subdomain with 2 BoundedContexts** — Checkout contains both Cart Management and
  Order Confirmation; demonstrates the DDD split at subdomain level
- **Ubiquitous language on BoundedContext nodes** — embedded in the text field so
  semantic search can distinguish "Order" as basket vs confirmed purchase vs payment
  instruction
- **EXPOSES replaces IMPLEMENTS for contracts** — contracts are leaf nodes attached to
  components, not to bounded contexts; add `Component -[:PRODUCES]-> Contract` incoming
  edges in future to make contracts traversal targets

## Tasks

### T1: Install and configure the stack
**Done when:** `python3 scripts/verify_stack.py` prints `Stack OK`

### T2: Seed Neo4j
**Done when:** 24 nodes across 7 labels, 23 relationships across 6 types confirmed

### T3: Seed Qdrant
**Done when:** 24 entities embedded; all `entityId`s resolve to Neo4j nodes;
disambiguation query returns cross-domain results

### T4: Graph-first retrieval script
**Done when:** `retrieve_graph_first.py Subdomain CONTAINS BoundedContext` returns
both bounded contexts under Checkout

### T5: Semantic-first retrieval script
**Done when:** `retrieve_semantic_first.py "what handles an order?"` returns results
from both Commerce and Payments in top-3

### T6: Document findings
**Done when:** all three retrieval architecture questions answered in `docs/findings.md`

## Rollout

Local only. No deployment.
- Stop Neo4j: `brew services stop neo4j`
- Remove Qdrant data: `rm -rf data/qdrant/`
- Deactivate venv: `deactivate`

## Changelog

- 2026-06-15: initial plan — 4-node schema (Workflow, Domain, Component, Contract)
- 2026-06-16: redesigned to full production node hierarchy (7 node types, 6 rel types);
  Commerce + Payments domains replace workflow-based seed; ubiquitous language conflict
  added for disambiguation testing; 11 → 24 entities
- 2026-06-16: post-migration smoke test completed end-to-end in `.venv312`; retrieval
  scripts updated for qdrant-client API compatibility (`query_points` path) and
  documentation/spec acceptance criteria aligned to validated command sequence
