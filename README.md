# Neo4j + LanceDB Hybrid Retrieval POC

Local proof-of-concept validating a **hybrid graph + vector retrieval architecture** —
graph-first and semantic-first patterns — before committing to a production stack
(Amazon Neptune + OpenSearch).

> **Purpose:** Test both retrieval patterns against real seed data and document the
> trade-offs to inform a retrieval architecture decision.

---

## What this demonstrates

- **Graph-first retrieval** — traverse the graph by node label + relationship type;
  deterministic, zero noise, best for structural questions ("what depends on X?")
- **Semantic-first retrieval** — embed a natural language query, search LanceDB for
  top-k matches, resolve their IDs to Neo4j nodes, and hop to neighbors
- **The `entityId` bridge** — a stable UUID on every node links the vector store and
  the graph store, enabling the hybrid pattern
- **Findings doc** — documents which pattern fits which consumer type and the observed
  trade-offs

---

## Stack

| Component | This POC | Production target |
|---|---|---|
| Graph store | Neo4j (Homebrew) | Amazon Neptune |
| Vector store | LanceDB (embedded, no server) | Amazon OpenSearch |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | OpenSearch embedding pipeline |
| Language | Python 3.9+ | — |

> Neo4j is used here because it runs locally with no cloud dependency. The Cypher
> queries and retrieval patterns transfer directly to Neptune.

---

## Prerequisites

- **macOS** with Homebrew installed (`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`)
- **Python 3.9+** — check with `python3 --version`
- **Java 17+** — required by Neo4j; installed automatically by Homebrew

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/jaynro-acn/ukp-neo4j-poc.git
cd ukp-neo4j-poc
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install neo4j lancedb sentence-transformers pyarrow
```

> The first run downloads the `all-MiniLM-L6-v2` model (~80MB). Requires internet access.

### 4. Install and start Neo4j

```bash
brew install neo4j
brew services start neo4j
```

Change the default password on first run:

```bash
echo "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'your-password';" | \
  cypher-shell -u neo4j -p neo4j -d system
```

> ⚠️ The scripts default to the password `ukpneo4j2026`.
> If you set a different password, update the `AUTH` variable at the top of each
> file in `scripts/`.

### 5. Verify the stack

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
# 1. Define schema and load the two-domain graph into Neo4j
#    Creates: 1 ValueStream, 6 Capabilities (L1/L2/L3), 2 Domains, 2 Subdomains,
#             4 BoundedContexts, 4 Components, 5 Contracts — 24 nodes total
python3 scripts/seed_neo4j.py

# 2. Embed the same 24 entities into LanceDB
#    Generates 384-dim vectors; runs the disambiguation verification query
python3 scripts/seed_lancedb.py
```

Entity IDs are persisted to `data/entity_ids.json` — the stable bridge between
the graph store and the vector store.

---

## Run retrieval

### Graph-first

Traverse Neo4j by node label + relationship + target label:

```bash
# Structural queries
python3 scripts/retrieve_graph_first.py Subdomain CONTAINS BoundedContext
python3 scripts/retrieve_graph_first.py Component DEPENDS_ON Component
python3 scripts/retrieve_graph_first.py Component EXPOSES Contract
python3 scripts/retrieve_graph_first.py Capability HAS_CHILD Capability

# Filter by a specific node name
python3 scripts/retrieve_graph_first.py Subdomain CONTAINS BoundedContext "Checkout"
```

### Semantic-first

Natural language query → LanceDB vector search → `entityId` bridge → Neo4j graph hop:

```bash
python3 scripts/retrieve_semantic_first.py "what handles an order?"
python3 scripts/retrieve_semantic_first.py "how does payment authorisation work?"
python3 scripts/retrieve_semantic_first.py "which services depend on each other?"
python3 scripts/retrieve_semantic_first.py "what capabilities does Digital Sales invest in?" 5
```

> The first query (`"what handles an order?"`) is the key disambiguation test — it should
> return results from **both** Commerce and Payments since "Order" means different things
> in each domain.

The second optional argument sets `top_k` (default: 3).

---

## Findings

See [`docs/findings.md`](docs/findings.md) for the full retrieval architecture analysis:

- Which pattern is more natural for each consumer type
- Whether an intent routing layer is needed
- Observed trade-offs (speed, result quality, query complexity)
- Implications for the Neptune + OpenSearch production design

---

## Project structure

```
ukp-neo4j-poc/
├── scripts/
│   ├── verify_stack.py            # Step 1 — confirms stack is working
│   ├── seed_neo4j.py              # Step 2 — loads entities into Neo4j
│   ├── seed_lancedb.py            # Step 3 — embeds entities into LanceDB
│   ├── retrieve_graph_first.py    # Step 4 — graph-first retrieval
│   └── retrieve_semantic_first.py # Step 5 — semantic-first retrieval
├── data/
│   └── entity_ids.json            # Stable UUID map (Neo4j ↔ LanceDB bridge)
├── docs/
│   ├── findings.md                # Retrieval architecture findings
│   └── specs/
│       └── neo4j-retrieval-poc/   # Spec + implementation plan
│           ├── spec.md
│           └── plan.md
├── requirements.txt
└── README.md
```

---

## Domain model

Two domains — **Commerce** and **Payments** — sharing a `Digital Sales` ValueStream.

```
Digital Sales (ValueStream)
  ├── INVESTS_IN → Order Management (L1 Capability)
  │     └── HAS_CHILD → Order Processing (L2)
  │           └── HAS_CHILD → Order Validation (L3)
  └── INVESTS_IN → Payment Management (L1 Capability)
        └── HAS_CHILD → Payment Authorization (L2)
              └── HAS_CHILD → Fraud Detection (L3)

Commerce (Domain)
  └── CONTAINS → Checkout (Subdomain)
        ├── CONTAINS → Cart Management (BoundedContext)  ← "Order" = basket
        └── CONTAINS → Order Confirmation (BoundedContext) ← "Order" = confirmed record

Payments (Domain)
  └── CONTAINS → Transaction Processing (Subdomain)
        ├── CONTAINS → Authorization (BoundedContext) ← "Order" = payment instruction
        └── CONTAINS → Settlement (BoundedContext)

Cross-domain: order-service ──DEPENDS_ON──▶ auth-gateway
```

The word **"Order"** has a different meaning in each bounded context — the key
ubiquitous language conflict for semantic disambiguation testing.

---

## Teardown

```bash
# Stop Neo4j
brew services stop neo4j

# Remove LanceDB data (regenerate any time with seed_lancedb.py)
rm -rf data/lancedb/

# Deactivate virtual environment
deactivate
```
