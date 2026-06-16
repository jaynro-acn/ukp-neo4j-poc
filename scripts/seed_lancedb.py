"""Seed LanceDB with embeddings of all graph entities.

Embeds name + description (and ubiquitous_language where present)
for richer semantic ranking and disambiguation testing.
"""
import json
from pathlib import Path

import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer

ENTITY_IDS_PATH = Path(__file__).parent.parent / "data" / "entity_ids.json"
LANCEDB_PATH    = Path(__file__).parent.parent / "data" / "lancedb"

ENTITIES = [
    # ValueStreams
    {"name": "Digital Sales", "type": "ValueStream",
     "text": "Digital Sales value stream. End-to-end digital commerce and payment delivery — owns online ordering, checkout, and payment collection."},

    # Capabilities
    {"name": "Order Management", "type": "Capability",
     "text": "Order Management L1 capability. Enterprise capability to manage the full lifecycle of customer orders from creation to fulfilment."},
    {"name": "Order Processing", "type": "Capability",
     "text": "Order Processing L2 capability. Validates, prices, and routes incoming orders before committing them to fulfilment."},
    {"name": "Order Validation", "type": "Capability",
     "text": "Order Validation L3 capability. Checks order completeness, stock availability, and customer eligibility before acceptance."},
    {"name": "Payment Management", "type": "Capability",
     "text": "Payment Management L1 capability. Enterprise capability to authorise, collect, and settle payments across all channels."},
    {"name": "Payment Authorization", "type": "Capability",
     "text": "Payment Authorization L2 capability. Performs real-time fraud screening and issuer authorisation for each payment attempt."},
    {"name": "Fraud Detection", "type": "Capability",
     "text": "Fraud Detection L3 capability. Applies ML-based rules and velocity checks to score and accept or decline transactions."},

    # Domains
    {"name": "Commerce", "type": "Domain",
     "text": "Commerce domain. Covers the customer shopping experience — browsing, cart, checkout, and order tracking."},
    {"name": "Payments", "type": "Domain",
     "text": "Payments domain. Covers the financial transaction layer — authorisation, clearing, and settlement of funds."},

    # Subdomains
    {"name": "Checkout", "type": "Subdomain",
     "text": "Checkout subdomain within Commerce. The point-of-sale subprocess — from cart finalisation through order confirmation."},
    {"name": "Transaction Processing", "type": "Subdomain",
     "text": "Transaction Processing subdomain within Payments. Real-time processing of payment transactions — authorisation through settlement."},

    # Bounded Contexts — include ubiquitous language to test disambiguation
    {"name": "Cart Management", "type": "BoundedContext",
     "text": "Cart Management bounded context within Checkout. Order means customer purchase basket, not yet committed. Manages cart lifecycle: add/remove items, apply promotions, lock cart at checkout start."},
    {"name": "Order Confirmation", "type": "BoundedContext",
     "text": "Order Confirmation bounded context within Checkout. Order means confirmed immutable purchase record with a unique order ID. Converts locked cart into confirmed order and triggers fulfilment and payment flows."},
    {"name": "Authorization", "type": "BoundedContext",
     "text": "Authorization bounded context within Transaction Processing. Order means payment instruction sent to the issuer for approval. Sends authorisation requests to card networks and returns approve or decline decisions."},
    {"name": "Settlement", "type": "BoundedContext",
     "text": "Settlement bounded context within Transaction Processing. Batches authorised transactions, submits clearing files to networks, and reconciles settled funds between acquirer and issuer."},

    # Components
    {"name": "checkout-service", "type": "Component",
     "text": "checkout-service component implementing Cart Management. Orchestrates cart validation, promotion application, and checkout initiation. Calls payment gateway before confirming order."},
    {"name": "order-service", "type": "Component",
     "text": "order-service component implementing Order Confirmation. Persists confirmed orders, assigns order IDs, emits order-submitted events, and exposes order status APIs."},
    {"name": "auth-gateway", "type": "Component",
     "text": "auth-gateway component implementing Authorization. Routes payment authorisation requests to card networks, applies ML fraud scores, and returns real-time approve or decline decisions."},
    {"name": "settlement-service", "type": "Component",
     "text": "settlement-service component implementing Settlement. Batches daily authorised transactions into clearing files, submits to networks, and reconciles settled amounts."},

    # Contracts
    {"name": "order-submitted", "type": "Contract",
     "text": "order-submitted event contract from order-service. Emitted when a customer order is confirmed and persisted. Consumed by payment and fulfilment services."},
    {"name": "POST /checkout/complete", "type": "Contract",
     "text": "POST /checkout/complete REST contract from checkout-service. Finalises the cart, triggers payment authorisation, and returns a confirmed order ID."},
    {"name": "payment-authorized", "type": "Contract",
     "text": "payment-authorized event contract from auth-gateway. Emitted when a payment authorisation is approved by the card network. Consumed by order-service to confirm purchase."},
    {"name": "payment-settled", "type": "Contract",
     "text": "payment-settled event contract from settlement-service. Emitted after funds are cleared and settled between acquirer and issuer."},
    {"name": "POST /payments/authorize", "type": "Contract",
     "text": "POST /payments/authorize REST contract from auth-gateway. Accepts a payment instruction and returns an authorisation decision synchronously."},
]


def main():
    entity_ids = json.loads(ENTITY_IDS_PATH.read_text())

    print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"Embedding {len(ENTITIES)} entities...")
    vectors = model.encode([e["text"] for e in ENTITIES], show_progress_bar=True)

    rows = []
    for entity, vector in zip(ENTITIES, vectors):
        name = entity["name"]
        if name not in entity_ids:
            raise ValueError(f"entityId missing for '{name}' — run seed_neo4j.py first")
        rows.append({
            "entityId": entity_ids[name],
            "name":     name,
            "type":     entity["type"],
            "text":     entity["text"],
            "vector":   vector.tolist(),
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

    try:
        db.drop_table("entities")
        print("Dropped existing table.")
    except Exception:
        pass

    table = db.create_table("entities", data=rows, schema=schema)
    print(f"\nLanceDB table 'entities' — {table.count_rows()} rows.")


def verify():
    print("\n── Verification ─────────────────────────────────────────────────")
    entity_ids = json.loads(ENTITY_IDS_PATH.read_text())
    db    = lancedb.connect(str(LANCEDB_PATH))
    table = db.open_table("entities")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    queries = [
        "what handles an order?",               # ubiquitous language disambiguation
        "how does payment authorisation work?",
        "which services depend on each other?",
    ]

    for q in queries:
        vec     = model.encode(q).tolist()
        results = table.search(vec).limit(3).to_list()
        print(f"\nQuery: '{q}'")
        for i, r in enumerate(results, 1):
            match = "✓" if r["entityId"] in entity_ids.values() else "✗"
            print(f"  {i}. [{r['type']}] {r['name']}  {match}")

    print("\nSeed + verify complete.")


if __name__ == "__main__":
    main()
    verify()
