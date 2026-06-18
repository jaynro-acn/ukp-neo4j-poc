# Architecture Overview

> The map of this repository. Read this first when exploring the codebase.

## Repository shape

This repo is a focused POC, not a general monorepo. Most of the meaningful
behavior lives in a small number of scripts and supporting docs.

```
.
├── AGENTS.md
├── README.md
├── requirements.txt
├── scripts/
│   ├── verify_stack.py
│   ├── seed_neo4j.py
│   ├── seed_qdrant.py
│   ├── retrieve_graph_first.py
│   └── retrieve_semantic_first.py
├── data/
│   ├── entity_ids.json
│   └── qdrant/
└── docs/
      ├── findings.md
      ├── architecture/
      │   ├── README.md
      │   ├── overview.md
      │   ├── retrieval-flow.md
      │   └── subdomains-bounded-contexts.md
      └── specs/
            └── neo4j-retrieval-poc/
                  ├── spec.md
                  └── plan.md
```

## What each top-level area does

- `scripts/` — executable core.
  - `verify_stack.py` checks the local stack.
  - `seed_neo4j.py` creates graph nodes and relationships.
  - `seed_qdrant.py` embeds the same entities into Qdrant.
  - `retrieve_graph_first.py` runs explicit structural traversal.
  - `retrieve_semantic_first.py` runs vector search, then graph hop.

- `data/` — generated local state.
  - `entity_ids.json` is the graph/vector bridge.
  - `qdrant/` is regenerable embedded vector data.

- `docs/findings.md` — decision output.

- `docs/specs/neo4j-retrieval-poc/` — delivery contract and implementation plan.

- `docs/architecture/` — current structure and retrieval flow.

## Runtime architecture

The key architectural seam is the `entityId` bridge:

1. `seed_neo4j.py` creates graph nodes with stable `entityId` values.
2. `seed_qdrant.py` embeds the same entities and stores the same `entityId` in payloads.
3. `retrieve_semantic_first.py` uses Qdrant to find relevant entities, then resolves them back into Neo4j by `entityId`.

That bridge is what makes the hybrid retrieval pattern possible.

See [retrieval-flow.md](retrieval-flow.md) for the execution path.

## Where to start

1. Read [README.md](/Users/jaynro.a.perez/Documents/vault/40-research/ukp-neo4j-poc/README.md) for setup and the happy path.
2. Read [retrieval-flow.md](retrieval-flow.md) to understand the two retrieval patterns.
3. Read [subdomains-bounded-contexts.md](subdomains-bounded-contexts.md) to understand the domain model and the “Order” ambiguity.
4. Read [findings.md](/Users/jaynro.a.perez/Documents/vault/40-research/ukp-neo4j-poc/docs/findings.md) for the architectural conclusions.
