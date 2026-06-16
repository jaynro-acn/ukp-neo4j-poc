# Spec: neo4j-retrieval-poc

- **Status:** Shipped
- **Owner:** jaynro
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** ADR-4 (retrieval architecture — pending spike)
- **Brief:** none
- **Contract:** none
- **Shape:** mixed (data + integration)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A local proof-of-concept that validates the UKP graph schema and hybrid retrieval
architecture before committing to Neptune + OpenSearch in production. The prototype
runs Neo4j (local, Homebrew) as the graph store and LanceDB (embedded) as the vector
store, seeded with AI workflow entities from the `ai-workflow-entity-inventory`.

Success means: two working retrieval scripts — one graph-first, one semantic-first —
both returning correct results from the same seed data, with findings documented that
answer the ADR-4 design questions (routing decision, intent router need, pattern
trade-offs). The output feeds directly into the production architecture decision.

This is a local validation tool, not a production service. No AWS, no CE-KB live
connections.

## Boundaries

### Always do

- Use the UKP ontology entity types and relationship names from `[[metamodel-spec]]`
  when defining the Neo4j schema — nodes and edges must match the production model
- Seed from `ai-workflow-entity-inventory.md` only (static snapshot, no live connections)
- Document findings after each retrieval pattern in `docs/findings.md`
- Keep all scripts self-contained and runnable with `python3 <script>.py`

### Ask first

- Any deviation from the metamodel-spec node types or relationship names (e.g.
  adding a node type not in the ontology)
- Changing the seed data beyond the 5–10 entities agreed at spec time
- Adding a dependency beyond: `neo4j` (driver), `lancedb`, `sentence-transformers`

### Never do

- Connect to AWS services (Neptune, OpenSearch, S3)
- Connect to CE-KB or any live GitLab repo
- Write production-grade code (no error handling beyond what's needed to run the scripts)
- Add a web server, API layer, or any UI
- Persist data outside the local Neo4j instance and LanceDB files

## Testing Strategy

- **Goal-based check** — each retrieval script is verified by running it and inspecting
  the output: correct node types returned, correct relationships traversed, `entityId`
  bridge between LanceDB and Neo4j resolves correctly
- **Manual QA** — findings document reviewed against the ADR-4 open questions; the POC
  is "done" when each ADR-4 question has a documented answer (even if the answer is
  "needs more investigation")

No TDD — this is a spike/POC; the scripts are throwaway validation tools, not
production code.

## Acceptance Criteria

- [ ] Neo4j running locally via Homebrew; schema loaded with at least 4 node types
  (`Workflow`, `Domain`, `Component`, `Contract`) and 3 relationship types
  (`BELONGS_TO`, `DEPENDS_ON`, `IMPLEMENTS`)
- [ ] LanceDB loaded with vector embeddings of the same 5–10 seed entities;
  each document carries an `entityId` field matching its Neo4j node
- [ ] **Graph-first script:** given an entity type + relationship filter (e.g.
  "all Components that IMPLEMENT a Workflow in domain X"), the script traverses
  Neo4j and returns the correct nodes with their properties
- [ ] **Semantic-first script:** given a natural language query, the script (1)
  retrieves the top-k matching documents from LanceDB, (2) resolves their `entityId`s
  to Neo4j nodes, (3) hops to related nodes via graph traversal, and (4) returns a
  combined result
- [ ] Both scripts run against the same seed data and produce non-empty, correct results
- [ ] `docs/findings.md` answers the three ADR-4 questions:
  - Which pattern (graph-first / semantic-first) is more natural for the UKP's
    primary consumer queries?
  - Is an intent routing layer needed, or can the consumer choose the pattern?
  - What are the trade-offs observed (speed, result quality, query complexity)?

## Assumptions

- Technical: Python runtime is 3.14.6 (`python3 --version`)
- Technical: Neo4j provisioned via Homebrew (`brew install neo4j`) (user confirmation 2026-06-15)
- Technical: Retrieval client = Python scripts using raw `neo4j` driver + `lancedb` (user confirmation 2026-06-15)
- Technical: LanceDB used as embedded vector store to simulate OpenSearch queries (user confirmation 2026-06-15)
- Technical: Neo4j driver not yet installed — installed in T1
- Technical: LanceDB not yet installed — installed in T1
- Technical: Seed data at `vault/10-projects/knowledge-graph/spikes/unified-knowledge-platform/references/ai-workflow-entity-inventory.md` (file read 2026-06-15)
- Product: Done = working Cypher queries for both patterns + findings documented (user confirmation 2026-06-15)
- Product: LanceDB simulates OpenSearch; Neptune is the target production graph engine (user confirmation 2026-06-15)
- Process: No formal review cadence; owner = Jaynro; sign-off = Eugene async via Teams
