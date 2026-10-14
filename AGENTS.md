## Agent skills

A spawned sub-agent must perform its assigned work directly in the existing sub-agent session.

When the assigned workflow names a skill, the sub-agent must read the skill instructions and execute the required commands directly rather than launching another Codex process.

Do not invoke `codex` or `codex exec` from inside a sub-agent. If nested delegation is explicitly requested, use the provided sub-agent orchestration tools rather than launching a Codex CLI process.

### Domain docs

This repository uses the single-context domain documentation layout. See `docs/agents/domain.md`.

## Language

- Prefer entity names over pronouns.

- Use unambiguous phrases. Examples:
Instead of "terminal command" write either "CLI command" or "terminating command," because "terminal command" is ambiguous.
Bad: "Retain second-valued timestamps" because "second-valued" is ambiguous; good: "Keep timestamps in seconds".

Instead of unconventional lexic like "project-owned internal collaborators" use common terms: "components that another component calls".

Avoid overloaded lexical constructions, e.g.: "specification-required system-level verification";
better: "tests that the specification requires, involve system service or hardware".
