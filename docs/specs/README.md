# Specs

> Feature specifications and implementation plans. See
> [`../CONVENTIONS.md`](../CONVENTIONS.md#4-specs-and-plans--docsspecsfeature)
> for the spec / plan distinction and lifecycle.

Each feature gets a directory:

```
docs/specs/<feature>/
├── spec.md      ← the contract (objective, boundaries, testing strategy, acceptance criteria): what this feature does
├── plan.md      ← the strategy + construction tests: how we'll build it
└── notes/       ← (optional) research, sketches, rejected approaches
```

## Current specs

<!-- Update this list as features are added. -->

| Spec | Status | Constrained by | Notes |
| --- | --- | --- | --- |
| [neo4j-retrieval-poc](neo4j-retrieval-poc/spec.md) | Shipped | ADR-4 | Current shipped POC validating graph-first + semantic-first retrieval locally |

## Adding a new spec

Create a new directory under `docs/specs/` with a `spec.md` and `plan.md`.

For this repo, the easiest approach is to follow the same shape as
`docs/specs/neo4j-retrieval-poc/` and keep the spec/plan pair together.
