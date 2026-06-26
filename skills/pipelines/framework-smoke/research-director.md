# Framework Smoke Research Director

## Purpose

Exercise the instruction-driven pipeline contract with the smallest useful research stage. This skill is for framework tests only; keep the output deterministic and schema-valid.

## Inputs

- User brief or test prompt
- `schemas/artifacts/research_brief.schema.json`

## Output

Write one `research_brief` artifact that validates against the schema.

## Process

1. Summarize the test topic in plain terms.
2. Provide at least three distinct content angles.
3. Include enough source placeholders or local notes for schema validation.
4. Keep claims generic unless the test provides concrete evidence.

## Quality Bar

- The artifact must validate before checkpointing.
- Do not call external providers.
- Do not create media assets.
