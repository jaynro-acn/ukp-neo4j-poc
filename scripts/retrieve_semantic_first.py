"""T5 — Semantic-first retrieval: LanceDB vector search → entityId bridge → Neo4j graph hop."""
import json
import sys
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase

URI          = "bolt://localhost:7687"
AUTH         = ("neo4j", "ukpneo4j2026")
LANCEDB_PATH = Path(__file__).parent.parent / "data" / "lancedb"

HELP = """
Usage:
  python3 retrieve_semantic_first.py "<natural language query>" [top_k]

Examples:
  python3 retrieve_semantic_first.py "discovery workflow for domain synthesis"
  python3 retrieve_semantic_first.py "what components store architecture artifacts" 3
  python3 retrieve_semantic_first.py "integration contracts between workflows" 5
"""


def vector_search(table, model, query_text, top_k):
    vec = model.encode(query_text).tolist()
    results = table.search(vec).limit(top_k).to_list()
    return results


def graph_hop(driver, entity_ids):
    """For each entityId, fetch the node and all its direct neighbours."""
    with driver.session() as s:
        cypher = """
            UNWIND $ids AS eid
            MATCH (n {entityId: eid})
            OPTIONAL MATCH (n)-[r]->(neighbor)
            RETURN n, labels(n) AS n_labels,
                   collect({
                       rel:      type(r),
                       neighbor: neighbor.name,
                       n_label:  labels(neighbor),
                       n_eid:    neighbor.entityId
                   }) AS edges
        """
        result = s.run(cypher, ids=entity_ids)
        hops = []
        for record in result:
            node = record["n"]
            edges = [e for e in record["edges"] if e["neighbor"] is not None]
            hops.append({
                "entityId": node["entityId"],
                "label":    record["n_labels"][0] if record["n_labels"] else "Unknown",
                "name":     node.get("name", ""),
                "purpose":  node.get("purpose") or node.get("description", ""),
                "neighbors": [
                    {
                        "relationship": e["rel"],
                        "name":         e["neighbor"],
                        "label":        e["n_label"][0] if e["n_label"] else "Unknown",
                        "entityId":     e["n_eid"],
                    }
                    for e in edges
                ],
            })
        return hops


def main():
    args = sys.argv[1:]
    if not args:
        print(HELP)
        sys.exit(1)

    query_text = args[0]
    top_k      = int(args[1]) if len(args) > 1 else 3

    # ── Step 1: embed query and search LanceDB ────────────────────────────────
    print(f"\nQuery: '{query_text}'  (top_k={top_k})")
    print("─" * 60)

    print("\n[1] Semantic search (LanceDB)...")
    db    = lancedb.connect(str(LANCEDB_PATH))
    table = db.open_table("entities")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    hits = vector_search(table, model, query_text, top_k)

    print(f"    Top-{top_k} hits:")
    for i, h in enumerate(hits, 1):
        print(f"      {i}. [{h['type']}] {h['name']}  (entityId: {h['entityId']})")

    # ── Step 2: resolve entityIds → Neo4j nodes + graph hop ──────────────────
    entity_ids = [h["entityId"] for h in hits]

    print("\n[2] Graph hop (Neo4j)...")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    hops   = graph_hop(driver, entity_ids)
    driver.close()

    # ── Step 3: assemble and print combined result ────────────────────────────
    print("\n[3] Combined result:")
    print("─" * 60)

    combined = []
    for hop in hops:
        print(f"\n  [{hop['label']}] {hop['name']}")
        if hop["purpose"]:
            print(f"    purpose: {hop['purpose'][:120]}{'...' if len(hop['purpose']) > 120 else ''}")
        if hop["neighbors"]:
            print(f"    neighbors ({len(hop['neighbors'])}):")
            for n in hop["neighbors"]:
                print(f"      --{n['relationship']}--> [{n['label']}] {n['name']}")
        else:
            print("    neighbors: none")
        combined.append(hop)

    print("\n" + "─" * 60)
    print(json.dumps(combined, indent=2))


if __name__ == "__main__":
    main()
