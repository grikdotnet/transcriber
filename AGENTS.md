## Agent skills

A spawned sub-agent must perform its assigned work directly in the existing sub-agent session.

When the assigned workflow names a skill, the sub-agent must read the skill instructions and execute the required commands directly rather than launching another Codex process.

Do not invoke `codex` or `codex exec` from inside a sub-agent. If nested delegation is explicitly requested, use the provided sub-agent orchestration tools rather than launching a Codex CLI process.

### Domain docs

This repository uses the single-context domain documentation layout. See `docs/agents/domain.md`.

## Language

- Prefer entity names over pronouns. Use a pronoun only when the pronoun's referent is clear.
- Use unambiguous phrases. Examples:
Bad: "terminal command".
Good: either "CLI command" or "terminating command," according to the intended meaning.
Bad: "Should the provider operation receive context?".
Good: "Should the ASR provider's recognize() method receive context?"
