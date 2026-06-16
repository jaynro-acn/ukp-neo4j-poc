# UKP Neo4j + LanceDB POC

Local proof-of-concept validating the **Unified Knowledge Platform** hybrid retrieval
architecture — graph-first and semantic-first patterns — before committing to the
production stack (Amazon Neptune + OpenSearch).

> **Purpose:** Answer ADR-4 (retrieval architecture) by running both retrieval patterns
> against real seed data and documenting findings. Results feed directly into
> `ukp-architecture-2026-06-16.md`.

---

## Stack

| Component | Local POC | Production target |
|---|---|---|
| Graph store | Neo4j (Homebrew) | Amazon Neptune |
| Vector store | LanceDB (embedded) | Amazon OpenSearch |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | OpenSearch embedding pipeline |
| Language | Python 3.14 | — |

> Neo4j is used here because it spins up locally with no AWS dependency. The Cypher
> queries and retrieval patterns transfer directly to Neptune.

---

## Setup

### 1. Install Neo4j

```bash
brew install neo4j
brew services start neo4j
```

Change the default password on first run:

```bash
echo "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'your-password';" | \
  cypher-shell -u neo4j -p neo4j -d system
```

> ⚠️ The scripts use `ukpneo4j2026` as the Neo4j password by default.
> If you set a different password, update the `AUTH` variable at the top of each
> script in `scripts/`.

### 2. Install Python dependencies

```bash
pip install neo4j lancedb sentence-transformers
```

### 3. Verify the stack

```bash
python3 scripts/verify_stack.py
```

Expected output:
```
  ✓ neo4j driver: 6.x.x
  ✓ lancedb: 0.x.x
  ✓ sentence-transformers: all-MiniLM-L6-v2 ok (dim=384)

Stack OK
```

---

## Seed the data

Run in order:

```bash
# 1. Load entities into Neo4j (4 Workflows, 2 Domains, 3 Components, 2 Contracts)
python3 scripts/seed_neo4j.py

# 2. Embed the same entities into LanceDB
python3 scripts/seed_lancedb.py
```

Entity IDs are persisted to `data/entity_ids.json` — the bridge between the two stores.

---

## Run retrieval

### Graph-first

Traverse Neo4j by node label + relationship + target label:

```bash
python3 scripts/retrieve_graph_first.py Workflow BELONGS_TO Domain
python3 scripts/retrieve_graph_first.py Workflow DEPENDS_ON Component
python3 scripts/retrieve_graph_first.py Component IMPLEMENTS Contract

# Filter by name
python3 scripts/retrieve_graph_first.py Workflow DEPENDS_ON Workflow "Domain Architecture"
```

### Semantic-first

Natural language query → LanceDB vector search → entityId bridge → Neo4j graph hop:

```bash
python3 scripts/retrieve_semantic_first.py "discovery workflow for domain synthesis"
python3 scripts/retrieve_semantic_first.py "what components store architecture artifacts"
python3 scripts/retrieve_semantic_first.py "integration contracts between workflows" 5
```

---

## Findings

See [`docs/findings.md`](docs/findings.md) for the full ADR-4 analysis:

- Which pattern is more natural for each consumer type
- Whether an intent routing layer is needed
- Observed trade-offs (speed, result quality, query complexity)
- Implications for the Neptune + OpenSearch production design

---

## Project structure

```
ukp-neo4j-poc/
├── scripts/
│   ├── verify_stack.py          # T1 — confirms stack is working
│   ├── seed_neo4j.py            # T2 — loads entities into Neo4j
│   ├── seed_lancedb.py          # T3 — embeds entities into LanceDB
│   ├── retrieve_graph_first.py  # T4 — graph-first retrieval
│   └── retrieve_semantic_first.py # T5 — semantic-first retrieval
├── data/
│   └── entity_ids.json          # Stable UUID map (Neo4j ↔ LanceDB bridge)
├── docs/
│   ├── findings.md              # ADR-4 answers from the POC
│   └── specs/
│       └── neo4j-retrieval-poc/ # Spec + plan (new-spec skill)
│           ├── spec.md
│           └── plan.md
└── README.md
```

---

## Seed data source

Entities are extracted from the `ai-workflow-entity-inventory` — 4 CE/MA workflows
(Solution Concept, Domain Synthesis, Domain Architecture, Blueprint Compilation) and
their associated domains, components, and contracts.

---

## Related

- Architecture doc: `ukp-architecture-2026-06-16.md`
- ADR-4 findings: `docs/findings.md`
- Production stack: Amazon Neptune + OpenSearch (AWS)
