# Retrieval Architecture Findings

> Purpose: inform the retrieval architecture decision (hybrid routing — graph-first vs semantic-first)
> POC date: 2026-06-15
> Stack: Neo4j 2026.05.0 (local) + LanceDB 0.33.0 + sentence-transformers all-MiniLM-L6-v2
> Seed data: 11 entities from the enterprise workflow entity inventory (4 Workflows, 2 Domains, 3 Components, 2 Contracts)

---

## Graph-first pattern

**Script:** `scripts/retrieve_graph_first.py <node_label> <relationship> <target_label>`

**How it works:** Cypher traversal — the caller specifies the node label, relationship
type, and target label. The graph returns all matching paths. Optional name filter
narrows to a single starting node.

**Queries run:**

| Query | Results | Correct? |
|---|---|---|
| `Workflow -[:BELONGS_TO]-> Domain` | 4 pairs | ✓ all workflows mapped to correct domain |
| `Workflow -[:DEPENDS_ON]-> Component` | 5 pairs | ✓ S3 shared across all; PostgreSQL only Domain Synthesis |
| `Component -[:IMPLEMENTS]-> Contract` | 2 pairs | ✓ exact contracts per component |

**Strengths:**
- **Deterministic** — same query always returns the same result set; no ranking, no noise
- **Zero ambiguity** — returns exactly the nodes that satisfy the relationship, nothing more
- **Fast** — simple Cypher traversal with indexed `entityId`; scales well on large graphs
- **Best for structural questions:** "what does X depend on?", "what implements Y?",
  "show me the blast radius of removing component Z"

**Weaknesses:**
- **Schema knowledge required** — the caller must know the node label and relationship
  type upfront; not usable with a natural language query
- **No fuzzy matching** — a misspelled node name or wrong relationship type returns empty
- **Single hop by default** — multi-hop queries (e.g., "everything transitively depending
  on S3") require more complex Cypher; not handled by the current script

---

## Semantic-first pattern

**Script:** `scripts/retrieve_semantic_first.py "<natural language query>" [top_k]`

**How it works:** (1) embed the query with `all-MiniLM-L6-v2`; (2) search LanceDB for
top-k matching entities by cosine similarity; (3) resolve their `entityId`s to Neo4j
nodes; (4) hop to direct neighbors; (5) return combined result.

**Queries run:**

| Query | Top-1 LanceDB hit | Graph hop added value? |
|---|---|---|
| "discovery workflow for domain synthesis" | `domain-synthesis-output` (Contract) | Yes — revealed Domain Synthesis's 4 dependencies |
| "what components store architecture artifacts" | `Architecture` (Domain) | Yes — revealed Blueprint Compilation's dependency chain |
| "integration contracts between workflows" | `solution-concept-output` (Contract) | Partial — contracts are leaf nodes (no outgoing edges) |

**Strengths:**
- **No schema knowledge required** — works with any natural language; ideal for product
  engineers and new-to-the-graph users
- **Surfaces unexpected but relevant nodes** — "integration contracts" correctly returned
  both Contract nodes without the caller knowing they existed
- **Graph hop enriches the result** — a fuzzy entry point lands on the right node, then
  the graph adds the structural picture (dependencies, ownership)

**Weaknesses:**
- **Ranking is not always intent-aligned** — "discovery workflow for domain synthesis"
  ranked the `domain-synthesis-output` Contract above the Workflow itself; the caller
  intended the Workflow but got the output artifact first
- **Leaf nodes add no graph context** — Contract nodes have no outgoing edges, so the
  graph hop step returns nothing for them; the result is a semantic hit with no
  structural enrichment
- **Sensitivity to embedding quality** — short or ambiguous text fields produce weaker
  vectors; longer, descriptive `text` fields (as used here) improve ranking significantly
- **Top-k is a tuning parameter** — too low misses relevant nodes; too high adds noise

---

## retrieval architecture decision answers

### Q1: Which pattern is more natural for the platform's primary consumer queries?

**Neither alone — the right answer is hybrid, routed by query shape.**

| Consumer | Natural pattern | Why |
|---|---|---|
| **Architect** (impact / dependency analysis) | Graph-first | Knows the entity; wants the structural picture — "what depends on S3?" |
| **Product engineer** (landscape / "what exists?") | Semantic-first | Doesn't know the schema; has an open question |
| **Developer via MCP** (specific lookup) | Semantic-first to discover → graph-first to traverse | Finds the entry point semantically, then traverses precisely |

The POC confirms the architecture doc's three consumer patterns (Section 5.2) are real
and distinct. Each consumer naturally reaches for a different entry point.

### Q2: Is an intent routing layer needed, or can the consumer choose the pattern?

**A lightweight routing layer is needed — but it does not need to be an LLM.**

The routing signal is structural, detectable from the query shape:

| Query shape | Route to | Signal |
|---|---|---|
| Names a known entity + relationship ("what does X depend on?") | Graph-first | Entity name + relationship verb present |
| Open-ended / exploratory ("what stores artifacts?") | Semantic-first | No entity or relationship named |
| Ambiguous | Semantic-first → graph hop | Default to semantic; graph adds context |

A simple heuristic classifier (does the query contain a known node name + a
relationship verb?) is sufficient for the majority of cases. A full LLM-based router
adds accuracy for edge cases but is not required for MVP.

**Implication for the context MCP:** the MCP tool should expose a single entry point
that accepts natural language and routes internally — not two separate tools that force
the caller to pick a pattern. The routing logic lives inside the MCP, not in the agent.

### Q3: What are the trade-offs observed?

| Dimension | Graph-first | Semantic-first |
|---|---|---|
| Result determinism | Deterministic — same query, same result | Non-deterministic — ranking varies by embedding |
| Schema dependency | High — caller must know labels + relationships | None — natural language input |
| Result noise | None — returns only what satisfies the relationship | Low-medium — top-k may include tangential nodes |
| Leaf node handling | N/A — explicit relationship traversal | Weak — leaf nodes return no graph context |
| Speed | Fast (indexed Cypher) | Slower (embedding + vector search + graph hop) |
| Best query type | "What is the structure around X?" | "What is relevant to this topic?" |
| Multi-hop support | Native (extend Cypher) | Requires repeated hops (not implemented) |

**Key finding:** the `entityId` bridge between LanceDB and Neo4j is the load-bearing
seam of the hybrid architecture. It held perfectly across all test runs — every
LanceDB hit resolved to a valid Neo4j node. This validates the `entityId` design
decision in the architecture doc (Section 5.2).

---

## Implications for the production architecture (Neptune + OpenSearch)

1. **The hybrid pattern transfers directly to Neptune + OpenSearch.** The structural
   finding — semantic entry point → graph traversal — is engine-agnostic. Neptune
   replaces Neo4j (same Cypher dialect); OpenSearch replaces LanceDB (same vector
   search + `entityId` bridge).

2. **The context MCP should expose one tool, not two.** Route graph-first vs
   semantic-first internally based on query shape. Agents should not need to know which
   engine to call.

3. **Leaf nodes need incoming edges to add value.** Contract nodes in this POC returned
   no graph context because they have no outgoing edges. In production, adding incoming
   edges (e.g., `Workflow -[:PRODUCES]-> Contract`) would make them first-class
   traversal targets.

4. **Embedding text quality matters more than model size.** Using `name + purpose`
   as the embedded text (vs. name alone) produced good ranking with a small model
   (all-MiniLM-L6-v2, 384 dims). OpenSearch's embedding pipeline should use the same
   composite text field strategy.

5. **retrieval architecture decision routing recommendation:** implement semantic-first as the default entry
   point with a lightweight query-shape classifier that promotes to graph-first when
   the query names a known entity + relationship. Build the classifier as a separate
   layer in the MCP, not inside the retrieval scripts.
