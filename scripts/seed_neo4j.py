"""T2 — Define schema and seed Neo4j with enterprise architecture workflow entities."""
import json
import uuid
from pathlib import Path
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "ukpneo4j2026")
ENTITY_IDS_PATH = Path(__file__).parent.parent / "data" / "entity_ids.json"


# ── Seed data — enterprise architecture workflow entities ─────────────────────

DOMAINS = [
    {
        "name": "Discovery",
        "level": "L0",
        "description": "Encompasses solution concept and domain synthesis workflows — the problem-space framing stage of the SDLC.",
    },
    {
        "name": "Architecture",
        "level": "L0",
        "description": "Encompasses domain architecture and blueprint compilation — the solution-space design stage of the SDLC.",
    },
]

WORKFLOWS = [
    {
        "name": "Discovery — Solution Concept",
        "file": "discovery-solution-concept.command.md",
        "purpose": "Synthesizes ingested research and business context into a solution concept that frames all downstream domain discovery and architecture work.",
        "domain": "Discovery",
        "steps": 9,
    },
    {
        "name": "Discovery — Domain Synthesis",
        "file": "discovery-domain-synthesis.command.md",
        "purpose": "Transforms raw event storming outputs into a formal domain model package. Applies DDD modeling expertise to cluster events into bounded contexts.",
        "domain": "Discovery",
        "steps": 11,
        "depends_on_workflow": "Discovery — Solution Concept",
    },
    {
        "name": "Domain Architecture",
        "file": "arch-domain-architecture.command.md",
        "purpose": "Generates the Domain Architecture foundation document — translates the domain model into service decomposition, integration architecture, and foundational technical decisions.",
        "domain": "Architecture",
        "steps": 7,
        "depends_on_workflow": "Discovery — Domain Synthesis",
    },
    {
        "name": "Architecture Blueprint Compilation",
        "file": "arch-compile-blueprint.command.md",
        "purpose": "Compiles all six architecture view artifacts into a single validated architecture blueprint. Performs cross-view consistency validation.",
        "domain": "Architecture",
        "steps": 4,
        "depends_on_workflow": "Domain Architecture",
    },
]

COMPONENTS = [
    {
        "name": "Knowledge Ingestion Pipeline",
        "type": "pipeline",
        "description": "Five-stage ingestion pipeline (Fetch → Validate → Reconcile identity → Map to ontology → Emit). One instance per source.",
    },
    {
        "name": "S3 Artifact Store",
        "type": "storage",
        "description": "Stores raw workflow output artifacts (markdown files). Source of record for all produced documents.",
    },
    {
        "name": "PostgreSQL Event Register",
        "type": "database",
        "description": "Live register for integration events, personas, and components. Fed by solution repo YAMLs and workflow outputs.",
    },
]

CONTRACTS = [
    {
        "name": "solution-concept-output",
        "interface_type": "document",
        "description": "Output contract of Discovery — Solution Concept. Required input to Domain Synthesis and Domain Architecture.",
    },
    {
        "name": "domain-synthesis-output",
        "interface_type": "document-package",
        "description": "7-artifact output package of Discovery — Domain Synthesis. Enables domain-model-driven mode in Domain Architecture.",
    },
]

# ── Relationships ─────────────────────────────────────────────────────────────
# Defined after nodes so we can reference by name


def build_entity_ids(nodes):
    """Generate stable UUIDs for all nodes keyed by name."""
    return {node["name"]: str(uuid.uuid4()) for node in nodes}


def seed(driver, entity_ids):
    with driver.session() as s:

        # Constraints (idempotent)
        for label in ("Workflow", "Domain", "Component", "Contract"):
            s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.entityId IS UNIQUE")

        # ── Domains ──────────────────────────────────────────────────────────
        for d in DOMAINS:
            s.run(
                """
                MERGE (n:Domain {entityId: $eid})
                SET n.name = $name, n.level = $level, n.description = $description
                """,
                eid=entity_ids[d["name"]], **d,
            )

        # ── Workflows ─────────────────────────────────────────────────────────
        for w in WORKFLOWS:
            s.run(
                """
                MERGE (n:Workflow {entityId: $eid})
                SET n.name = $name, n.file = $file, n.purpose = $purpose,
                    n.steps = $steps
                """,
                eid=entity_ids[w["name"]],
                name=w["name"], file=w["file"],
                purpose=w["purpose"], steps=w["steps"],
            )
            # BELONGS_TO Domain
            s.run(
                """
                MATCH (w:Workflow {entityId: $weid}), (d:Domain {name: $dname})
                MERGE (w)-[:BELONGS_TO]->(d)
                """,
                weid=entity_ids[w["name"]], dname=w["domain"],
            )
            # DEPENDS_ON upstream Workflow
            if "depends_on_workflow" in w:
                s.run(
                    """
                    MATCH (w:Workflow {entityId: $weid}),
                          (up:Workflow {name: $upname})
                    MERGE (w)-[:DEPENDS_ON]->(up)
                    """,
                    weid=entity_ids[w["name"]], upname=w["depends_on_workflow"],
                )

        # ── Components ────────────────────────────────────────────────────────
        for c in COMPONENTS:
            s.run(
                """
                MERGE (n:Component {entityId: $eid})
                SET n.name = $name, n.type = $type, n.description = $description
                """,
                eid=entity_ids[c["name"]], **c,
            )

        # ── Contracts ─────────────────────────────────────────────────────────
        for ct in CONTRACTS:
            s.run(
                """
                MERGE (n:Contract {entityId: $eid})
                SET n.name = $name, n.interface_type = $interface_type,
                    n.description = $description
                """,
                eid=entity_ids[ct["name"]], **ct,
            )

        # ── Cross-entity relationships ────────────────────────────────────────

        # Workflows DEPENDS_ON S3 (they read/write artifacts there)
        for wf_name in [w["name"] for w in WORKFLOWS]:
            s.run(
                """
                MATCH (w:Workflow {entityId: $weid}),
                      (c:Component {name: 'S3 Artifact Store'})
                MERGE (w)-[:DEPENDS_ON]->(c)
                """,
                weid=entity_ids[wf_name],
            )

        # Domain Synthesis DEPENDS_ON PostgreSQL Event Register (outputs integration events)
        s.run(
            """
            MATCH (w:Workflow {name: 'Discovery — Domain Synthesis'}),
                  (c:Component {name: 'PostgreSQL Event Register'})
            MERGE (w)-[:DEPENDS_ON]->(c)
            """,
        )

        # Knowledge Ingestion Pipeline IMPLEMENTS solution-concept-output contract
        s.run(
            """
            MATCH (c:Component {name: 'Knowledge Ingestion Pipeline'}),
                  (ct:Contract {name: 'solution-concept-output'})
            MERGE (c)-[:IMPLEMENTS]->(ct)
            """,
        )

        # S3 Artifact Store IMPLEMENTS domain-synthesis-output contract
        s.run(
            """
            MATCH (c:Component {name: 'S3 Artifact Store'}),
                  (ct:Contract {name: 'domain-synthesis-output'})
            MERGE (c)-[:IMPLEMENTS]->(ct)
            """,
        )


def verify(driver):
    with driver.session() as s:
        counts = {}
        for label in ("Workflow", "Domain", "Component", "Contract"):
            result = s.run(f"MATCH (n:{label}) RETURN count(n) AS c")
            counts[label] = result.single()["c"]

        rel_result = s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c")
        rels = {row["t"]: row["c"] for row in rel_result}

        print("\nNode counts:")
        for label, count in counts.items():
            print(f"  {label}: {count}")
        print("\nRelationship counts:")
        for rel, count in rels.items():
            print(f"  {rel}: {count}")

        # Spot-check query from spec
        check = s.run(
            "MATCH (w:Workflow)-[:BELONGS_TO]->(d:Domain) RETURN w.name, d.name ORDER BY d.name, w.name"
        )
        print("\nWorkflow → Domain (spec check query):")
        for row in check:
            print(f"  {row['w.name']} → {row['d.name']}")


if __name__ == "__main__":
    # Build and persist entity IDs
    all_nodes = DOMAINS + WORKFLOWS + COMPONENTS + CONTRACTS
    ENTITY_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)

    if ENTITY_IDS_PATH.exists():
        entity_ids = json.loads(ENTITY_IDS_PATH.read_text())
        # Add any new nodes not yet in the file
        for node in all_nodes:
            if node["name"] not in entity_ids:
                entity_ids[node["name"]] = str(uuid.uuid4())
    else:
        entity_ids = build_entity_ids(all_nodes)

    ENTITY_IDS_PATH.write_text(json.dumps(entity_ids, indent=2))
    print(f"Entity IDs saved → {ENTITY_IDS_PATH}")

    driver = GraphDatabase.driver(URI, auth=AUTH)
    seed(driver, entity_ids)
    verify(driver)
    driver.close()
    print("\nT2 done — Neo4j seeded.")
