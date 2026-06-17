"""T1 verification — confirms Neo4j, neo4j driver, qdrant, and sentence-transformers are all working."""
import sys

def check_neo4j_driver():
    import neo4j
    driver = neo4j.GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "ukpneo4j2026"))
    with driver.session() as session:
        session.run("CREATE (t:_VerifyTest {name: 'verify'}) DELETE t")
    driver.close()
    return neo4j.__version__

def check_qdrant():
    import tempfile
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams

    path = tempfile.mkdtemp(prefix="qdrant_verify_")
    client = QdrantClient(path=path)
    if client.collection_exists("verify_test"):
        client.delete_collection(collection_name="verify_test")
    client.create_collection(
        collection_name="verify_test",
        vectors_config=VectorParams(size=4, distance=Distance.COSINE),
    )
    client.delete_collection(collection_name="verify_test")
    return "local embedded mode ok"

def check_sentence_transformers():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vec = model.encode("test")
    assert len(vec) == 384
    return "all-MiniLM-L6-v2 ok (dim=384)"

checks = [
    ("neo4j driver", check_neo4j_driver),
    ("qdrant", check_qdrant),
    ("sentence-transformers", check_sentence_transformers),
]

failed = False
for name, fn in checks:
    try:
        result = fn()
        print(f"  ✓ {name}: {result}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        failed = True

if failed:
    print("\nStack NOT OK — fix errors above before proceeding.")
    sys.exit(1)
else:
    print("\nStack OK")
