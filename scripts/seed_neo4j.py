"""Seed Neo4j with a two-domain enterprise graph — Commerce and Payments.

Models the full UKP node hierarchy:
  ValueStream → Capability (L1/L2/L3) → Domain → Subdomain →
  BoundedContext → Component → Contract

Demonstrates the ubiquitous language conflict: 'Order' means
different things in Commerce vs Payments.
"""
import json
import uuid
from pathlib import Path
from neo4j import GraphDatabase

URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "ukpneo4j2026")
ENTITY_IDS_PATH = Path(__file__).parent.parent / "data" / "entity_ids.json"

# ── Seed data ──────────────────────────────────────────────────────────────────

VALUE_STREAMS = [
    {
        "name": "Digital Sales",
        "description": "End-to-end digital commerce and payment delivery — owns online ordering, checkout, and payment collection.",
    },
]

CAPABILITIES = [
    # Commerce
    {"name": "Order Management",    "level": "L1", "parent": None,
     "description": "Enterprise capability to manage the full lifecycle of customer orders from creation to fulfilment."},
    {"name": "Order Processing",    "level": "L2", "parent": "Order Management",
     "description": "Validates, prices, and routes incoming orders before committing them to fulfilment."},
    {"name": "Order Validation",    "level": "L3", "parent": "Order Processing",
     "description": "Checks order completeness, stock availability, and customer eligibility before acceptance."},
    # Payments
    {"name": "Payment Management",  "level": "L1", "parent": None,
     "description": "Enterprise capability to authorise, collect, and settle payments across all channels."},
    {"name": "Payment Authorization","level": "L2", "parent": "Payment Management",
     "description": "Performs real-time fraud screening and issuer authorisation for each payment attempt."},
    {"name": "Fraud Detection",     "level": "L3", "parent": "Payment Authorization",
     "description": "Applies ML-based rules and velocity checks to score and accept or decline transactions."},
]

DOMAINS = [
    {"name": "Commerce",  "description": "Covers the customer shopping experience — browsing, cart, checkout, and order tracking."},
    {"name": "Payments",  "description": "Covers the financial transaction layer — authorisation, clearing, and settlement of funds."},
]

SUBDOMAINS = [
    {"name": "Checkout",                "domain": "Commerce",
     "description": "The point-of-sale subprocess — from cart finalisation through order confirmation."},
    {"name": "Transaction Processing",  "domain": "Payments",
     "description": "Real-time processing of payment transactions — authorisation through settlement."},
]

BOUNDED_CONTEXTS = [
    # Checkout has TWO bounded contexts — same subdomain, different 'Order' meaning
    {"name": "Cart Management",    "subdomain": "Checkout",
     "ubiquitous_language": "Order = customer purchase basket, not yet committed.",
     "description": "Manages the shopping cart lifecycle: add/remove items, apply promotions, lock cart at checkout start."},
    {"name": "Order Confirmation", "subdomain": "Checkout",
     "ubiquitous_language": "Order = confirmed, immutable purchase record with a unique order ID.",
     "description": "Converts a locked cart into a confirmed order, assigns order ID, triggers fulfilment and payment flows."},
    # Transaction Processing has TWO bounded contexts
    {"name": "Authorization",  "subdomain": "Transaction Processing",
     "ubiquitous_language": "Order = payment instruction sent to the issuer for approval.",
     "description": "Sends authorisation requests to card networks, applies fraud scores, and returns approve/decline decisions."},
    {"name": "Settlement",     "subdomain": "Transaction Processing",
     "ubiquitous_language": "Transaction = settled funds transfer between acquirer and issuer.",
     "description": "Batches authorised transactions, submits clearing files to networks, and reconciles settled funds."},
]

COMPONENTS = [
    {"name": "checkout-service",   "type": "service", "context": "Cart Management",
     "description": "Orchestrates cart validation, promotion application, and checkout initiation. Calls payment gateway before confirming."},
    {"name": "order-service",      "type": "service", "context": "Order Confirmation",
     "description": "Persists confirmed orders, assigns order IDs, emits order-submitted events, and exposes order status APIs."},
    {"name": "auth-gateway",       "type": "gateway", "context": "Authorization",
     "description": "Routes payment authorisation requests to card networks, applies ML fraud scores, and returns real-time decisions."},
    {"name": "settlement-service", "type": "service", "context": "Settlement",
     "description": "Batches daily authorised transactions into clearing files, submits to networks, and reconciles settled amounts."},
]

CONTRACTS = [
    {"name": "order-submitted",          "type": "event",   "component": "order-service",
     "description": "Event emitted when a customer order is confirmed and persisted. Consumed by payment and fulfilment services."},
    {"name": "POST /checkout/complete",  "type": "rest",    "component": "checkout-service",
     "description": "REST endpoint that finalises the cart, triggers payment authorisation, and returns a confirmed order ID."},
    {"name": "payment-authorized",       "type": "event",   "component": "auth-gateway",
     "description": "Event emitted when a payment authorisation is approved by the card network. Consumed by order-service to confirm purchase."},
    {"name": "payment-settled",          "type": "event",   "component": "settlement-service",
     "description": "Event emitted after funds are cleared and settled between acquirer and issuer."},
    {"name": "POST /payments/authorize", "type": "rest",    "component": "auth-gateway",
     "description": "REST endpoint that accepts a payment instruction and returns an authorisation decision synchronously."},
]

# ── Relationships ──────────────────────────────────────────────────────────────

VSTREAM_CAPABILITIES = [
    ("Digital Sales", "Order Management"),
    ("Digital Sales", "Payment Management"),
]

CAPABILITY_HIERARCHY = [
    ("Order Management",   "Order Processing"),
    ("Order Processing",   "Order Validation"),
    ("Payment Management", "Payment Authorization"),
    ("Payment Authorization", "Fraud Detection"),
]

CONTEXT_DEPENDENCIES = [
    # Cart Management calls Authorization before confirming the order
    ("Cart Management", "Authorization"),
    # order-service calls auth-gateway (cross-domain)
    ("order-service",   "auth-gateway"),
]


# ── Graph operations ───────────────────────────────────────────────────────────

def clear_db(driver):
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")


def create_constraints(driver):
    labels = ("ValueStream", "Capability", "Domain", "Subdomain",
              "BoundedContext", "Component", "Contract")
    with driver.session() as s:
        for label in labels:
            s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.entityId IS UNIQUE")


def seed(driver, ids):
    with driver.session() as s:

        # ValueStreams
        for v in VALUE_STREAMS:
            s.run("MERGE (n:ValueStream {entityId:$eid}) SET n.name=$name, n.description=$desc",
                  eid=ids[v["name"]], name=v["name"], desc=v["description"])

        # Capabilities
        for c in CAPABILITIES:
            s.run("MERGE (n:Capability {entityId:$eid}) SET n.name=$name, n.level=$level, n.description=$desc",
                  eid=ids[c["name"]], name=c["name"], level=c["level"], desc=c["description"])
        for parent, child in CAPABILITY_HIERARCHY:
            s.run("MATCH (p:Capability {name:$p}),(c:Capability {name:$c}) MERGE (p)-[:HAS_CHILD]->(c)",
                  p=parent, c=child)

        # ValueStream → Capability
        for vs, cap in VSTREAM_CAPABILITIES:
            s.run("MATCH (v:ValueStream {name:$v}),(c:Capability {name:$c}) MERGE (v)-[:INVESTS_IN]->(c)",
                  v=vs, c=cap)

        # Domains
        for d in DOMAINS:
            s.run("MERGE (n:Domain {entityId:$eid}) SET n.name=$name, n.description=$desc",
                  eid=ids[d["name"]], name=d["name"], desc=d["description"])

        # Subdomains + CONTAINS edges
        for sd in SUBDOMAINS:
            s.run("MERGE (n:Subdomain {entityId:$eid}) SET n.name=$name, n.description=$desc",
                  eid=ids[sd["name"]], name=sd["name"], desc=sd["description"])
            s.run("MATCH (d:Domain {name:$dn}),(sd:Subdomain {name:$sn}) MERGE (d)-[:CONTAINS]->(sd)",
                  dn=sd["domain"], sn=sd["name"])

        # BoundedContexts + CONTAINS edges
        for bc in BOUNDED_CONTEXTS:
            s.run("""MERGE (n:BoundedContext {entityId:$eid})
                     SET n.name=$name, n.ubiquitous_language=$ul, n.description=$desc""",
                  eid=ids[bc["name"]], name=bc["name"],
                  ul=bc["ubiquitous_language"], desc=bc["description"])
            s.run("MATCH (sd:Subdomain {name:$sn}),(bc:BoundedContext {name:$bn}) MERGE (sd)-[:CONTAINS]->(bc)",
                  sn=bc["subdomain"], bn=bc["name"])

        # BoundedContext DEPENDS_ON BoundedContext
        for src, tgt in CONTEXT_DEPENDENCIES:
            if src in [bc["name"] for bc in BOUNDED_CONTEXTS]:
                s.run("MATCH (a:BoundedContext {name:$a}),(b:BoundedContext {name:$b}) MERGE (a)-[:DEPENDS_ON]->(b)",
                      a=src, b=tgt)

        # Components + IMPLEMENTS edges
        for comp in COMPONENTS:
            s.run("MERGE (n:Component {entityId:$eid}) SET n.name=$name, n.type=$type, n.description=$desc",
                  eid=ids[comp["name"]], name=comp["name"], type=comp["type"], desc=comp["description"])
            s.run("MATCH (c:Component {name:$cn}),(bc:BoundedContext {name:$bn}) MERGE (c)-[:IMPLEMENTS]->(bc)",
                  cn=comp["name"], bn=comp["context"])

        # Component DEPENDS_ON Component
        for src, tgt in CONTEXT_DEPENDENCIES:
            if src in [c["name"] for c in COMPONENTS]:
                s.run("MATCH (a:Component {name:$a}),(b:Component {name:$b}) MERGE (a)-[:DEPENDS_ON]->(b)",
                      a=src, b=tgt)

        # Contracts + EXPOSES edges
        for ct in CONTRACTS:
            s.run("""MERGE (n:Contract {entityId:$eid})
                     SET n.name=$name, n.type=$type, n.description=$desc""",
                  eid=ids[ct["name"]], name=ct["name"], type=ct["type"], desc=ct["description"])
            s.run("MATCH (c:Component {name:$cn}),(ct:Contract {name:$ctn}) MERGE (c)-[:EXPOSES]->(ct)",
                  cn=ct["component"], ctn=ct["name"])


def verify(driver):
    with driver.session() as s:
        for label in ("ValueStream","Capability","Domain","Subdomain","BoundedContext","Component","Contract"):
            r = s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
            print(f"  {label}: {r['c']}")
        rels = s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC")
        print("\nRelationships:")
        for row in rels:
            print(f"  {row['t']}: {row['c']}")


if __name__ == "__main__":
    all_nodes = VALUE_STREAMS + CAPABILITIES + DOMAINS + SUBDOMAINS + BOUNDED_CONTEXTS + COMPONENTS + CONTRACTS
    ENTITY_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Always regenerate IDs for a clean reseed
    ids = {n["name"]: str(uuid.uuid4()) for n in all_nodes}
    ENTITY_IDS_PATH.write_text(json.dumps(ids, indent=2))
    print(f"Entity IDs saved → {ENTITY_IDS_PATH}\n")

    driver = GraphDatabase.driver(URI, auth=AUTH)
    print("Clearing existing graph...")
    clear_db(driver)
    create_constraints(driver)
    print("Seeding...")
    seed(driver, ids)
    print("\nNode counts:")
    verify(driver)
    driver.close()
    print("\nSeed complete.")
