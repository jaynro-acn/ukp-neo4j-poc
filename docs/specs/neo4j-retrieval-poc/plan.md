# Plan: neo4j-retrieval-poc

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Seven sequential tasks: install the stack, define the schema, seed the graph,
seed the vector store, implement both retrieval patterns, and document findings.
Each task is a standalone script or config file a single session can complete.
The riskiest part is the `entityId` bridge between LanceDB and Neo4j (T4/T6) —
if the bridge breaks, the semantic-first pattern can't hop to the graph. Validate
the bridge explicitly in T4 before building the semantic-first script in T6.

## Constraints

- Follows retrieval architecture decision scope: validates retrieval architecture patterns for transfer to
  Neptune + OpenSearch production design
- Node types and relationship names must match `the graph schema spec`
- No AWS, no live external connections (spec Boundaries)

## Construction tests

**Integration tests:** T6 semantic-first script is an end-to-end integration test
across LanceDB → `entityId` resolution → Neo4j traversal — runs as a single script.

**Manual verification:**
- After T3: inspect Neo4j Browser at `http://localhost:7474` to confirm nodes and
  relationships are correct
- After T4: print top-3 LanceDB results for a test query and verify `entityId` fields
  match Neo4j node IDs
- After T7: findings doc reviewed against retrieval architecture decision questions before marking POC done

## Design (LLD)

### Data & schema

**Neo4j node types (minimum viable):**

| Label | Key properties | Source |
|---|---|---|
| `Workflow` | `entityId`, `name`, `purpose`, `domain` | enterprise workflow entity inventory |
| `Domain` | `entityId`, `name`, `level` (L0/L1) | enterprise workflow entity inventory |
| `Component` | `entityId`, `name`, `type` | enterprise workflow entity inventory |
| `Contract` | `entityId`, `name`, `interface_type` | enterprise workflow entity inventory |

**Neo4j relationship types (minimum viable):**

| Type | From → To | Meaning |
|---|---|---|
| `BELONGS_TO` | Workflow → Domain | workflow lives in this domain |
| `DEPENDS_ON` | Workflow → Component | workflow reads/uses this component |
| `IMPLEMENTS` | Component → Contract | component exposes this contract |

**LanceDB schema:**
Each document: `{ entityId, name, type, description, vector }` — `entityId` is
the bridge key that resolves to a Neo4j node.

### Dependencies & integration

- `neo4j` Python driver — talks to local Neo4j Bolt endpoint (`bolt://localhost:7687`)
- `lancedb` — embedded, file-based; database stored at `./data/lancedb/`
- `sentence-transformers` (`all-MiniLM-L6-v2`) — generates embeddings for LanceDB;
  small model (~80MB), runs on CPU

## Tasks

### T1: Install and configure the stack

**Depends on:** none

**Tests:**
- `brew services list | grep neo4j` returns `started`
- `python3 -c "import neo4j; print(neo4j.__version__)"` prints a version
- `python3 -c "import lancedb; print(lancedb.__version__)"` prints a version
- `python3 -c "from sentence_transformers import SentenceTransformer"` imports without error

**Approach:**
- `brew install neo4j` and `brew services start neo4j`
- Set Neo4j initial password: `neo4j-admin dbms set-initial-password` or via browser
- `pip3 install neo4j lancedb sentence-transformers`
- Verify connectivity: `scripts/verify_stack.py` — connects to Neo4j, creates and
  drops a test node, prints "Stack OK"

**Done when:** `python3 scripts/verify_stack.py` prints `Stack OK` with no errors.

---

### T2: Define the graph schema and load seed entities into Neo4j

**Depends on:** T1

**Tests:**
- After running the seed script, Neo4j Browser shows ≥5 `Workflow` nodes,
  ≥2 `Domain` nodes, and relationships connecting them
- A Cypher query `MATCH (w:Workflow)-[:BELONGS_TO]->(d:Domain) RETURN w, d` returns
  non-empty results

**Approach:**
- Create `scripts/seed_neo4j.py`
- Extract 5–10 entities manually from `enterprise workflow entity inventory.md`
  (Workflows 1–3 are enough: Solution Concept, Domain Synthesis, one more)
- Use the `neo4j` Python driver to run `MERGE` Cypher statements for each node
  and relationship
- Assign `entityId` as a UUID generated once per entity (store the mapping in
  `data/entity_ids.json` so LanceDB can reference the same IDs)

**Done when:** Cypher query above returns ≥5 workflow–domain pairs in Neo4j Browser.

---

### T3: Seed LanceDB with embeddings of the same entities

**Depends on:** T2

**Tests:**
- `python3 scripts/verify_lancedb.py` prints top-3 results for query
  `"solution concept discovery workflow"` with correct `entityId` fields
- `entityId` values in LanceDB results match node IDs in `data/entity_ids.json`

**Approach:**
- Create `scripts/seed_lancedb.py`
- Load the same entities from `data/entity_ids.json`
- For each entity, embed `name + " " + purpose` using `all-MiniLM-L6-v2`
- Write to LanceDB table `entities` at `./data/lancedb/`
- Create `scripts/verify_lancedb.py` — runs a test query and prints top-3 results

**Done when:** `verify_lancedb.py` returns results with `entityId`s that resolve to
Neo4j nodes.

---

### T4: Implement the graph-first retrieval script

**Depends on:** T2

**Tests:**
- `python3 scripts/retrieve_graph_first.py "Workflow" "BELONGS_TO" "Domain"` returns
  the correct workflow–domain pairs with all node properties
- Result includes `entityId` on every returned node

**Approach:**
- Create `scripts/retrieve_graph_first.py`
- Accept: `node_label`, `relationship_type`, `target_label` as CLI args
- Build and execute a parameterized Cypher query:
  `MATCH (a:<label>)-[:<rel>]->(b:<target>) RETURN a, b`
- Print results as JSON
- Document the query pattern and its output in `docs/findings.md` under
  "Graph-first pattern"

**Done when:** script returns correct JSON output and findings entry is written.

---

### T5: Implement the semantic-first retrieval script

**Depends on:** T3, T4

**Tests:**
- `python3 scripts/retrieve_semantic_first.py "discovery workflow for domain synthesis"`
  returns LanceDB top-k results, resolves their `entityId`s to Neo4j nodes, and hops
  to related nodes
- Final output includes both the matched entity and its graph neighbors

**Approach:**
- Create `scripts/retrieve_semantic_first.py`
- Accept: natural language query string as CLI arg
- Step 1: embed the query with `all-MiniLM-L6-v2`, search LanceDB for top-3
- Step 2: extract `entityId`s from results
- Step 3: query Neo4j — `MATCH (n {entityId: $id})-[r]->(m) RETURN n, r, m`
  for each resolved ID
- Step 4: print combined result as JSON
- Document the query pattern, latency, and result quality in `docs/findings.md`
  under "Semantic-first pattern"

**Done when:** script returns combined results and findings entry is written.

---

### T6: Write findings and answer retrieval architecture decision questions

**Depends on:** T4, T5

**Tests:**
- `docs/findings.md` contains entries for both patterns
- Each retrieval architecture decision question has a written answer (even if "needs more investigation")

**Approach:**
- Run both scripts against 3 representative queries; record results
- Fill `docs/findings.md` with:
  - Graph-first: best for, worst for, Cypher complexity, result quality
  - Semantic-first: best for, worst for, bridge reliability, result quality
  - retrieval architecture decision answers: routing recommendation, intent router need, observed trade-offs
- Share findings summary with the architecture team

**Done when:** all three retrieval architecture decision questions answered in `docs/findings.md`.

---

## Rollout

Local only. No deployment. Teardown: `brew services stop neo4j`. LanceDB files
at `./data/lancedb/` can be deleted. No irreversible steps.

## Risks

- `sentence-transformers` model download (~80MB) requires internet on first run
- Neo4j Homebrew install may conflict if Java version is incompatible — check
  `java -version` if Neo4j fails to start
- LanceDB → Neo4j `entityId` bridge is the most fragile step; if IDs don't match,
  the semantic-first script returns empty graph hops

## Changelog

- 2026-06-15: initial plan
