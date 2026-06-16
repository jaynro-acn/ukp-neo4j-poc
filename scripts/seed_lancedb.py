"""T3 — Seed LanceDB with embeddings of the same entities seeded in Neo4j."""
import json
from pathlib import Path

import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer

ENTITY_IDS_PATH = Path(__file__).parent.parent / "data" / "entity_ids.json"
LANCEDB_PATH    = Path(__file__).parent.parent / "data" / "lancedb"

# ── Entity text corpus (name + description — same entities as seed_neo4j.py) ─

ENTITIES = [
    # Domains
    {
        "name": "Discovery",
        "type": "Domain",
        "text": "Discovery domain. Encompasses solution concept and domain synthesis workflows — the problem-space framing stage of the SDLC.",
    },
    {
        "name": "Architecture",
        "type": "Domain",
        "text": "Architecture domain. Encompasses domain architecture and blueprint compilation — the solution-space design stage of the SDLC.",
    },
    # Workflows
    {
        "name": "Discovery — Solution Concept",
        "type": "Workflow",
        "text": "Discovery Solution Concept workflow. Synthesizes ingested research and business context into a solution concept that frames all downstream domain discovery and architecture work. 9 steps.",
    },
    {
        "name": "Discovery — Domain Synthesis",
        "type": "Workflow",
        "text": "Discovery Domain Synthesis workflow. Transforms raw event storming outputs into a formal domain model package. Applies DDD modeling expertise to cluster events into bounded contexts, map relationships, and build ubiquitous language. 11 steps.",
    },
    {
        "name": "Domain Architecture",
        "type": "Workflow",
        "text": "Domain Architecture workflow. Generates the Domain Architecture foundation document. Translates the domain model into service decomposition, integration architecture, and foundational technical decisions. 7 steps.",
    },
    {
        "name": "Architecture Blueprint Compilation",
        "type": "Workflow",
        "text": "Architecture Blueprint Compilation workflow. Compiles all six architecture view artifacts into a single validated architecture blueprint. Performs cross-view consistency validation and flags conflicts. 4 steps.",
    },
    # Components
    {
        "name": "Knowledge Ingestion Pipeline",
        "type": "Component",
        "text": "Knowledge Ingestion Pipeline component. Five-stage ingestion pipeline: Fetch, Validate, Reconcile identity, Map to ontology, Emit. One instance per source.",
    },
    {
        "name": "S3 Artifact Store",
        "type": "Component",
        "text": "S3 Artifact Store component. Stores raw workflow output artifacts as markdown files. Source of record for all produced documents.",
    },
    {
        "name": "PostgreSQL Event Register",
        "type": "Component",
        "text": "PostgreSQL Event Register component. Live register for integration events, personas, and components. Fed by solution repo YAMLs and workflow outputs.",
    },
    # Contracts
    {
        "name": "solution-concept-output",
        "type": "Contract",
        "text": "solution-concept-output contract. Output contract of Discovery Solution Concept workflow. Required input to Domain Synthesis and Domain Architecture.",
    },
    {
        "name": "domain-synthesis-output",
        "type": "Contract",
        "text": "domain-synthesis-output contract. Seven-artifact output package of Discovery Domain Synthesis. Enables domain-model-driven mode in Domain Architecture workflow.",
    },
]


def main():
    entity_ids = json.loads(ENTITY_IDS_PATH.read_text())

    print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"Embedding {len(ENTITIES)} entities...")
    texts  = [e["text"] for e in ENTITIES]
    vectors = model.encode(texts, show_progress_bar=True)

    rows = []
    for entity, vector in zip(ENTITIES, vectors):
        name = entity["name"]
        if name not in entity_ids:
            raise ValueError(f"entityId missing for '{name}' — run seed_neo4j.py first")
        rows.append({
            "entityId":   entity_ids[name],
            "name":       name,
            "type":       entity["type"],
            "text":       entity["text"],
            "vector":     vector.tolist(),
        })

    LANCEDB_PATH.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(LANCEDB_PATH))

    schema = pa.schema([
        pa.field("entityId", pa.string()),
        pa.field("name",     pa.string()),
        pa.field("type",     pa.string()),
        pa.field("text",     pa.string()),
        pa.field("vector",   pa.list_(pa.float32(), 384)),
    ])

    if "entities" in db.table_names():
        db.drop_table("entities")
        print("Dropped existing 'entities' table.")

    table = db.create_table("entities", data=rows, schema=schema)
    print(f"\nLanceDB table 'entities' created — {table.count_rows()} rows.")


def verify():
    print("\n── Verification ────────────────────────────────────────────────")
    entity_ids = json.loads(ENTITY_IDS_PATH.read_text())
    db    = lancedb.connect(str(LANCEDB_PATH))
    table = db.open_table("entities")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    query = "solution concept discovery workflow"
    vec   = model.encode(query).tolist()

    results = table.search(vec).limit(3).to_list()
    print(f"Query: '{query}'")
    print("Top-3 results:")
    for i, r in enumerate(results, 1):
        eid   = r["entityId"]
        match = "✓" if eid in entity_ids.values() else "✗"
        print(f"  {i}. [{r['type']}] {r['name']}")
        print(f"     entityId: {eid}  {match} resolves to Neo4j node")

    print("\nT3 done — LanceDB seeded and verified.")


if __name__ == "__main__":
    main()
    verify()
