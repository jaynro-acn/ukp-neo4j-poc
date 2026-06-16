"""T4 — Graph-first retrieval: traverse Neo4j by node label + relationship + target label."""
import json
import sys
from pathlib import Path
from neo4j import GraphDatabase

URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "ukpneo4j2026")

HELP = """
Usage:
  python3 retrieve_graph_first.py <node_label> <relationship> <target_label> [node_name]

Examples:
  python3 retrieve_graph_first.py Workflow BELONGS_TO Domain
  python3 retrieve_graph_first.py Workflow DEPENDS_ON Component
  python3 retrieve_graph_first.py Component IMPLEMENTS Contract
  python3 retrieve_graph_first.py Workflow DEPENDS_ON Workflow
  python3 retrieve_graph_first.py Workflow BELONGS_TO Domain "Domain Architecture"
"""


def query(driver, node_label, rel, target_label, node_name=None):
    with driver.session() as s:
        if node_name:
            cypher = f"""
                MATCH (a:{node_label} {{name: $name}})-[r:{rel}]->(b:{target_label})
                RETURN a, b, type(r) AS rel
                ORDER BY a.name, b.name
            """
            result = s.run(cypher, name=node_name)
        else:
            cypher = f"""
                MATCH (a:{node_label})-[r:{rel}]->(b:{target_label})
                RETURN a, b, type(r) AS rel
                ORDER BY a.name, b.name
            """
            result = s.run(cypher)

        rows = []
        for record in result:
            rows.append({
                "from": {
                    "label": node_label,
                    "entityId": record["a"]["entityId"],
                    "name":     record["a"]["name"],
                },
                "relationship": record["rel"],
                "to": {
                    "label": target_label,
                    "entityId": record["b"]["entityId"],
                    "name":     record["b"]["name"],
                },
            })
        return rows


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print(HELP)
        sys.exit(1)

    node_label   = args[0]
    relationship = args[1]
    target_label = args[2]
    node_name    = args[3] if len(args) > 3 else None

    driver = GraphDatabase.driver(URI, auth=AUTH)
    rows   = query(driver, node_label, relationship, target_label, node_name)
    driver.close()

    if not rows:
        print(f"No results for: ({node_label})-[:{relationship}]->({target_label})"
              + (f" where name='{node_name}'" if node_name else ""))
        sys.exit(0)

    print(f"\nPattern: ({node_label})-[:{relationship}]->({target_label})"
          + (f"  [filtered: '{node_name}']" if node_name else ""))
    print(f"Results: {len(rows)}\n")

    for r in rows:
        print(f"  [{r['from']['label']}] {r['from']['name']}")
        print(f"    --{r['relationship']}--> [{r['to']['label']}] {r['to']['name']}")
        print(f"    entityIds: {r['from']['entityId']} → {r['to']['entityId']}")
        print()

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
