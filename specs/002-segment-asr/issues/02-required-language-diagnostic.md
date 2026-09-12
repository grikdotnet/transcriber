# Render the required-language rejection diagnostic

## Status

Open

## Feature

`002-segment-asr`

## Problem

An ASR Model whose language behavior is `required` correctly rejects `--language auto` before
the ASR Service or Execution Provider starts. The controller catches
`RequiredAsrLanguageError`, but returns status 2 without rendering an explanation:

```python
except RequiredAsrLanguageError:
    return 2
```

The command therefore fails with empty stdout and empty stderr. A GUI or person invoking
`transcriber-asr` cannot determine that the selected ASR Model requires an explicit language.

## Authoritative requirements

- `specs/002-segment-asr/spec.md` FR-011 requires an ASR Model with `language=required` to reject
  `auto`.
- User Story 2, acceptance scenario 4 requires rejection before the Execution Provider starts.
- `specs/002-segment-asr/contracts/cli.md` requires failures to use one bounded stderr line and
  defines `asr-model` as a closed runtime stage.
- `specs/002-segment-asr/plan.md` defines status 2 for an invalid required/automatic language
  combination.
- `specs/002-segment-asr/tasks.md` T016 and T017 require the rejection before file or provider
  work.

## Intended behavior

1. The controller receives a command using `auto` for an ASR Model whose language behavior is
   `required`.
2. Application resolution rejects the combination before the ASR Service, task files, or
   Execution Provider are accessed.
3. The controller converts `RequiredAsrLanguageError` into an `AsrFailure` with:
   - stage `asr-model`;
   - the selected ASR Model ID;
   - message `ASR Model requires an explicit language`.
4. The existing failure renderer writes exactly one bounded, JSON-escaped line to stderr:

   ```text
   ERROR [asr-model] model="qwen3-asr-1.7b": ASR Model requires an explicit language
   ```

5. Stdout remains empty and the command returns status 2.

## Entities, architectural layers, and relationships

- **ASR Model capabilities** — Protocol value describing whether language behavior is `optional`
  or `required`.
- **Required ASR language error** — Composition-owned rejection raised while resolving the
  selected ASR Model against the command.
- **ASR failure** — Protocol value carrying the public stage, ASR Model ID, and message.
- **Controller** — converts the expected Composition error into an ASR failure, invokes the
  existing bounded renderer, and selects status 2.

Relationship: the Controller passes the parsed command to the Application; the Application checks
the selected ASR Model capabilities and raises the expected rejection; the Controller maps the
rejection to the existing public failure value and renderer. The ASR Service and Execution
Provider remain outside this failure path.

## Affected files

- `tests/unit/controller/test_asr_cli.py`: change the existing required-model/automatic-language
  test to require the exact diagnostic in addition to status and no downstream work.
- `src/transcriber/controller/asr_cli.py`: render the caught error through `_render_failure()`
  before returning status 2.
- `specs/002-segment-asr/evidence/`: record the red result and final verification.

No Domain, Service, Infrastructure, ASR Model Manifest, language grammar, or provider-specific
code changes are required.

## Assumptions

- Status 2 remains the established result for the invalid required/automatic language
  combination, as specified by the feature plan.
- `RequiredAsrLanguageError` retains its current deterministic message.
- The existing `_render_failure()` implementation already owns bounding and JSON escaping.
- The selected ASR Model ID is available from the parsed `AsrCommand` when the exception is
  caught.

## Explicit non-goals

- Changing required-language validation ownership or timing.
- Changing the status from 2.
- Changing the CLI failure format or its 1,023-code-point bound.
- Adding a new failure stage or a new renderer.
- Changing optional-language, Qwen language-mapping, or unsupported-language behavior.
- Starting an Execution Provider or reading task files to produce this diagnostic.

## Implementation tasks

### Task 1 — Require the public diagnostic

Update `test_required_model_automatic_language_returns_two_before_task_or_provider_work` through
the existing public CLI seam.

Acceptance criteria:

- The test uses an actual `Application` configured with `language=required`.
- The ASR Service raises if called, proving that no task or provider work starts.
- The command returns status 2.
- Stdout is empty.
- Stderr equals one exact `ERROR [asr-model]` line containing the selected ASR Model ID and the
  explicit-language requirement.
- The updated test fails before the controller change because stderr is empty.

### Task 2 — Render the expected rejection

Catch `RequiredAsrLanguageError` as a named exception, construct the existing `AsrFailure`, invoke
the existing failure renderer, and retain status 2.

Acceptance criteria:

- No new renderer, status type, exception hierarchy, or failure stage is introduced.
- The diagnostic uses stage `asr-model` and the selected ASR Model ID.
- The Task 1 test passes.
- Existing argument-syntax, unregistered-model, provider-failure, and successful CLI tests remain
  green.

### Task 3 — Verify and record evidence

Run the focused test, relevant Controller/Composition/acceptance regressions, Ruff, and strict
mypy. Record exact commands and results.

Acceptance criteria:

- The focused required-language test passes.
- Controller, Composition, CLI contract, acceptance, and architecture tests pass with real-ASR
  tests excluded.
- Changed production and test code passes Ruff.
- Changed production code passes strict mypy; any pre-existing test-suite findings are reported
  accurately rather than attributed to this fix.

## Execution order and parallelization

Tasks 1 and 2 are sequential because both participate in one red-to-green behavior slice. Task 3
starts after Task 2 is green. Within Task 3, independent regression suites, Ruff, and mypy may run
in parallel because verification does not modify files.

## Test plan

1. Update the existing required-language controller test with the exact stderr expectation and run
   it alone; verify that the test fails because stderr is empty.
2. Add the minimum controller rendering call and rerun the focused test; verify that the test
   passes.
3. Run the complete Controller and Composition unit suites.
4. Run the CLI contract, controlled ASR acceptance, and architecture suites with real-ASR tests
   excluded.
5. Run Ruff on the changed production and test files.
6. Run strict mypy on the changed production file and report existing test-suite typing findings
   separately.

## Completion criteria

- Required automatic language is rejected before ASR Service or Execution Provider work.
- The command emits exactly one bounded `asr-model` diagnostic and no stdout.
- The command returns status 2.
- Existing CLI behavior remains unchanged for every other outcome.
- Verification evidence is reproducible and accurately scoped.

