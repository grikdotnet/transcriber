# Structured Transcript artifact contract

Successful ASR Tasks atomically publish `transcripts-{model-id}/transcript.json`. The CLI reports its absolute path through the existing success field. `transcript.txt` is not updated or migrated.

The file is compact UTF-8 JSON with exactly one final LF. The top-level object has exactly one member, `text`, whose value is an ordered array. Every non-empty array entry has exactly these members in this order: `text` (NFKC string) and `probability` (finite JSON number between 0 and 1). No language, count, token ID, timestamp, word separator, or other member is published.

Example for source tokens `e` at probability 0.9 and combining acute plus `.` at probability 0.7:

```json
{"text":[{"text":"é","probability":0.7},{"text":".","probability":0.7}]}
```

The actual file adds one LF after the closing brace. With no non-empty normalized spans, the exact file bytes are `{"text":[]}\n`. Concatenating entry text in order reconstructs each independently normalized Speech Segment and then joins the segment results without added separators or trimmed whitespace. Failure or cancellation preserves any previous complete JSON file and removes attempt-created temporary output.

The retained transcript is derived from provider-exposed Unicode token strings after defined control removal. Final assistant content is not compared with those strings. llama.cpp stop handling may make the two representations differ; the JSON artifact follows the token strings.

This contract replaces only the Transcript artifact clauses of `specs/002-segment-asr/contracts/cli.md`; command grammar, status, progress, and other CLI behavior remain in force.
