<!--
Sync Impact Report
- Version change: 1.1.0 -> 1.2.0
- Modified principles:
  - V. Complete and Verifiable Plans -> V. Complete and Verifiable Plans
    (three-cycle limit and mandatory manual-review escalation added)
- Modified sections:
  - Planning rules (agent lifecycle bounded by manual-review gate)
- Added sections: None
- Removed sections: None
- Follow-up TODOs: None
-->
# Transcriber Constitution

## Core Principles

### I. Test-First Development
Every behavioral code change MUST follow red-green-refactor: write a test for the intended
behavior, confirm it fails for the expected reason, add the minimum code needed to pass, then
refactor only while all tests remain green. Bug fixes MUST start with a reproducing test.
Refactors MUST start and end with the same relevant tests passing. Changed contracts, boundaries,
integrations, and failure paths MUST have tests at the appropriate level. Tests MUST prove the
requested behavior, not merely execute changed lines.

### II. Enforced Architectural Boundaries
Domain, application, infrastructure, and UI responsibilities MUST remain separate. Every new or changed class, standalone function, or package covered by `architecture/layers.md` MUST be categorized, and pass the Planning Architecture Gate.

### III. Simplicity First
Implementations MUST use simplest maintainable design that meets approved success criteria.
They MUST NOT add abstractions, extension points, unnecessary configuration, generalization, or speculative flexibility unless required by task or approved plan. During planning and review, ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### IV. Scope Traceability
Every implemented capability MUST trace to an explicit task and approved plan. Each task MUST state its authorized functionality and verifiable acceptance criteria. Functionality outside that scope MUST NOT be implemented, even if useful, or future-proof. Newly discovered
work MUST be added to the task and approved before implementation. This keeps delivery and review aligned with intent.

### V. Complete and Verifiable Plans
Every implementation plan MUST define intended behavior, assumptions, success criteria, affected files/components, tests to write before production code, architecture classifications for all new or changed code entities, explicit non-goals, and a test plan. Each task MUST identify its owner, dependencies, implementation order, and acceptance criteria. Each step MUST pair an action with a deterministic verification check. Independent verification instructions MUST compare the result with both the success criteria and approved plan. This makes execution reviewable and safe to distribute among sub-agents.

## Planning rules

Plan MUST define:

- success criteria
- intended behavior
- files/components affected
- architecture classification for new/changed code entities if applicable
- explicit non-goals

Phrase work as verifiable goals:

- "Add validation" -> "write tests for invalid inputs, then make them pass."
- "Fix the bug" -> "write a reproducing test, then make it pass."
- "Refactor X" -> "record the relevant passing tests, refactor X, then confirm they pass."

Every step of a multi-step plan MUST use `<action> -> verify: <deterministic check>`. Plans MUST define affected entities, their architecture layers, and their relationships.

Prefer to divide implementation into sub-agent tasks with explicit ownership, dependencies, order,
acceptance criteria, and safe parallelization boundaries. Where sub-agents are used, the plan MUST
define three distinct roles: Worker, Validator, and Supervisor. A plan MAY assign multiple agents
to each role, but the three roles for a given work item MUST be held by different agents. The plan
MUST identify which Validator and Supervisor receive each Worker's result.

The Worker implements the task, records verification evidence, and submits both to the Validator.
The Validator independently checks the result against the task's acceptance criteria, approved
plan, tests, architecture rules, and scope, then reports findings and evidence to the Supervisor.
The Supervisor reviews the Validator's report and either accepts the work or returns actionable
feedback to the Worker.

When work is returned, the Worker MUST revise it and resubmit it to the Validator. The Validator
MUST repeat validation and send an updated report to the Supervisor. A cycle starts when the
Worker submits a result and ends when the Supervisor accepts or returns it; the initial submission
is cycle 1. A work item MUST NOT exceed three Worker → Validator → Supervisor cycles.

If the Supervisor does not accept the work by the end of cycle 3, all agent work on that item MUST
halt. The Supervisor MUST prepare a manual-review summary containing the work item's scope, each
attempt and its changes, validation findings and evidence, unresolved acceptance criteria or
issues, and the decision required. Work MUST NOT resume until a manual reviewer records a decision
and explicitly authorizes the next action.

## Engineering Standards

- Single Responsibility and Interface Segregation are mandatory. Each entity MUST have one
  coherent reason to change.
- New or changed functions MUST declare parameter and return types where supported.
- Implementations MUST prefer existing project data types and contracts over ad-hoc dictionaries,
  tuples, or parallel representations.
- Code MUST NOT add unrequested flexibility, optional behavior, abstraction, or configuration.
- Reviews MUST verify test-first evidence, coverage, scope traceability, simplicity, type correctness, responsibility boundaries, and architecture classifications.

## Governance

This constitution is Transcriber's highest-priority engineering policy. Specifications, plans,
tasks, implementations, and reviews MUST comply. It supersedes conflicting project documents
unless formally amended.

Amendments MUST document their motivation, affected principles, impact, migration
work, and MUST receive explicit project-owner approval.
Versions follow semantic versioning: MAJOR for incompatible principle removals or redefinitions, MINOR for
new principles or materially expanded requirements, and PATCH for non-semantic clarifications.

Every implementation plan and code review MUST check constitution compliance. Reviewers MUST
reject work lacking test-first evidence, automated verification, task traceability, required
architecture classification, or deterministic verification. Complexity and claimed deviations
MUST be resolved through a constitution amendment or design change; informal exceptions are forbidden.

**Version**: 1.2.0 | **Ratified**: 2026-07-30 | **Last Amended**: 2026-08-02
