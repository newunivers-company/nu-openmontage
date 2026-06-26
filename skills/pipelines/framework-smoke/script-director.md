# Framework Smoke Script Director

## Purpose

Exercise the instruction-driven pipeline contract with the smallest useful script stage. This skill is for framework tests only; keep the output deterministic and schema-valid.

## Inputs

- `research_brief` artifact
- `schemas/artifacts/script.schema.json`

## Output

Write one `script` artifact that validates against the schema.

## Process

1. Use the strongest research angle as the script premise.
2. Produce a short script with explicit section timing.
3. Keep the total duration small so tests remain fast.

## Quality Bar

- The artifact must validate before checkpointing.
- Section times must be ordered and non-overlapping.
- Do not call external providers.
