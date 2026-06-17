# Spec: neo4j-retrieval-poc

- **Status:** Shipped
- **Owner:** author
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** retrieval architecture decision (hybrid routing spike)
- **Brief:** none
- **Contract:** none
- **Shape:** mixed (data + integration)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A local proof-of-concept that validates a hybrid graph + vector retrieval architecture
before committing to a production stack (Neptune + OpenSearch). The prototype runs Neo4j
(local, Homebrew) as the graph store and Qdrant (embedded local mode) as the vector store, seeded
with a two-domain enterprise architecture knowledge graph (Commerce + Payments).

The seed data models the full production node hierarchy: ValueStream → Capability
(L1/L2/L3) → Domain → Subdomain → BoundedContext → Component → Contract. It includes
an intentional ubiquitous language conflict ("Order" means different things in Commerce
vs Payments) to test semantic disambiguation.

Success means: two working retrieval scripts — one graph-first, one semantic-first —
both returning correct results from the same seed data, with findings documented that
answer the retrieval architecture design questions (routing decision, intent router need,
pattern trade-offs). The output feeds directly into the production architecture decision.

This is a local validation tool, not a production service. No AWS, no live external
connections.

## Boundaries

### Always do

- Use the 7 defined node types: `ValueStream`, `Capability`, `Domain`, `Subdomain`,
  `BoundedContext`, `Component`, `Contract`
- Use the 6 defined relationship types: `INVESTS_IN`, `HAS_CHILD`, `CONTAINS`,
  `IMPLEMENTS`, `DEPENDS_ON`, `EXPOSES`
- Embed `name + description` together (not name alone) for richer semantic vectors
- Document findings after each retrieval pattern in `docs/findings.md`
- Keep all scripts self-contained and runnable with `python3 <script>.py`

### Ask first

- Adding a node type or relationship type not in the schema above
- Changing the domain model beyond the two agreed domains (Commerce, Payments)
- Adding a dependency beyond: `neo4j` (driver), `qdrant-client`, `sentence-transformers`

### Never do

- Connect to AWS services (Neptune, OpenSearch, S3)
- Connect to any live external system or repository
- Write production-grade code (no error handling beyond what's needed to run the scripts)
- Add a web server, API layer, or any UI
- Persist data outside the local Neo4j instance and Qdrant files

## Testing Strategy

- **Goal-based check** — each retrieval script is verified by running it and inspecting
  the output: correct node types returned, correct relationships traversed, `entityId`
  bridge between Qdrant and Neo4j resolves correctly
- **Disambiguation check** — the query `"what handles an order?"` must return results
  from both the Commerce and Payments domains, confirming the ubiquitous language
  conflict is detectable via semantic search
- **Manual QA** — findings document reviewed against the retrieval architecture decision
  open questions; the POC is "done" when each question has a documented answer

No TDD — this is a spike/POC; the scripts are throwaway validation tools, not
production code.

## Acceptance Criteria

- [x] Neo4j running locally via Homebrew; schema loaded with 7 node types and
  6 relationship types (see Boundaries)
- [x] 24 entities seeded: 1 ValueStream, 6 Capabilities, 2 Domains, 2 Subdomains,
  4 BoundedContexts, 4 Components, 5 Contracts
- [x] One subdomain (Checkout) contains 2 bounded contexts with different ubiquitous
  language definitions for "Order"
- [x] Cross-domain dependency: `order-service` → `auth-gateway` (Commerce → Payments)
- [x] Qdrant loaded with vector embeddings of all 24 entities; `entityId` bridge
  to Neo4j verified on every entity
- [x] **Graph-first script:** given a node label + relationship + target label, the
  script traverses Neo4j and returns correct nodes with properties and `entityId`s
- [x] **Semantic-first script:** given a natural language query, (1) searches Qdrant,
  (2) resolves `entityId`s to Neo4j nodes, (3) hops to neighbors, (4) returns combined
  result
- [x] Disambiguation query `"what handles an order?"` returns results from both
  Commerce and Payments domains in top-3
- [x] `docs/findings.md` answers the three retrieval architecture questions:
  - Which pattern is more natural for each consumer type?
  - Is an intent routing layer needed?
  - What are the observed trade-offs?
- [x] Full smoke test run succeeds in project Python 3.12 environment:
  - `verify_stack.py`
  - `seed_neo4j.py`
  - `seed_qdrant.py`
  - `retrieve_graph_first.py ValueStream INVESTS_IN Capability "Digital Sales"`
  - `retrieve_semantic_first.py "what capabilities does Digital Sales invest in?" 5`
- [x] Qdrant query path is compatible with installed client API (`query_points`)
  while preserving support for clients exposing `search`

## Assumptions

- Technical: Python 3.12 required; tested on 3.12.x
- Technical: Neo4j provisioned via Homebrew; password configured in `AUTH` var in each script
- Technical: Retrieval client = Python scripts using raw `neo4j` driver + `qdrant-client`
- Technical: Qdrant simulates OpenSearch; Neptune is the target production graph engine
- Technical: Seed data hardcoded in `scripts/seed_neo4j.py` and `scripts/seed_qdrant.py` — 24 entities across Commerce and Payments domains
- Technical: Qdrant client API may differ by version (`search` vs `query_points`); scripts handle this explicitly
- Product: Done = both retrieval patterns working + findings documented
- Process: No formal review cadence; personal POC project
