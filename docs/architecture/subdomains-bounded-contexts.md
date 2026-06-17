# Subdomains and Bounded Contexts

This diagram explains the domain model seeded by `scripts/seed_neo4j.py`, with focus on:

- Domain to subdomain boundaries
- Subdomain to bounded context boundaries
- Ubiquitous language differences across contexts

## Domain and Context Map

```mermaid
flowchart TB
  %% Domains
  D1[Domain: Commerce]
  D2[Domain: Payments]

  %% Subdomains
  SD1[Subdomain: Checkout]
  SD2[Subdomain: Transaction Processing]

  %% Bounded contexts
  BC1[Bounded Context: Cart Management]
  BC2[Bounded Context: Order Confirmation]
  BC3[Bounded Context: Authorization]
  BC4[Bounded Context: Settlement]

  %% Containment
  D1 -->|CONTAINS| SD1
  D2 -->|CONTAINS| SD2

  SD1 -->|CONTAINS| BC1
  SD1 -->|CONTAINS| BC2
  SD2 -->|CONTAINS| BC3
  SD2 -->|CONTAINS| BC4

  %% Cross-context dependency
  BC1 -->|DEPENDS_ON| BC3
```

## Ubiquitous Language Map

```mermaid
flowchart LR
  O[Term: Order]
  T[Term: Transaction]

  C1[Cart Management\nOrder = customer basket\nnot yet committed]
  C2[Order Confirmation\nOrder = immutable confirmed\norder record with order ID]
  C3[Authorization\nOrder = payment instruction\nsent to issuer]
  C4[Settlement\nTransaction = settled\nfunds transfer]

  O --> C1
  O --> C2
  O --> C3
  T --> C4
```

## Why this matters for retrieval

- Graph-first retrieval can traverse exact boundaries using `CONTAINS` and `DEPENDS_ON`.
- Semantic-first retrieval can surface ambiguous terms like "Order" and then resolve meaning by bounded context.
- The same word can be valid in multiple contexts with different meanings, which is the key disambiguation test in this POC.
