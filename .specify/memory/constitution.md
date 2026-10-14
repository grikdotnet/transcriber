<!--
Sync Impact Report
- Version change: 2.2.0 -> 2.3.0
- Modified principles: None
- Modified sections:
  - Sub-agents (updated Worker and Validator model/reasoning assignments)
  - Governance metadata (amendment approved by the project owner on 2026-10-14)
- Added sections: None
- Removed sections: None
- Follow-up TODOs: None
-->
# Transcriber Constitution

## Core Principles

### I. Test-First Development
Every behavioral code change MUST be test-first: write a test for the intended behavior before implementing the behavior, then add the minimum code needed to pass, then refactor when reasonable. Running test before implementation MAY be skipped.
Bug fixes MUST start with a reproducing test; confirming the test's pre-fix failure is required.
Refactors MUST start and end with the same relevant tests passing.
Changed contracts, boundaries, integrations, and failure paths MUST have tests.

Tests MUST prove the requested behavior. Tests MUST verify only behavior owned by this project. Tests MUST NOT attempt to verify third-party libraries, executables, services, or models, or results produced by the third-party dependencies. Tests covering third-party integrations MUST verify project-owned integration behavior, including input construction, output parsing, contract mapping, handling of errors, and malformed responses. Such tests MUST use controlled fixtures, fakes, or mocks where practical. Omit duplicate verification and no-op work.

### II. Enforced Architectural Boundaries
Domain, application, infrastructure, and UI responsibilities MUST remain separate. Every new or changed class, standalone function, or package covered by `architecture/layers.md` MUST be categorized, and pass the Planning Architecture Gate.

### III. Simplicity First
Implementations MUST use simplest maintainable design that meets approved success criteria.
They MUST NOT add abstractions, extension points, unnecessary configuration, generalization, or speculative flexibility unless required by task or approved plan.

### IV. Scope Traceability
Every implemented capability MUST trace to an explicit task and approved plan. Functionality outside that scope MUST NOT be implemented, even if useful, or future-proof.

### V. Complete and Verifiable Plans

Every implementation plan MUST define:

- intended behavior
- assumptions
- success criteria
- affected files/components
- architecture classifications for all new or changed code entities
- explicit non-goals
- tests to write before production code, and a test plan.

Phrase work as verifiable goals. Every step of a multi-step plan MUST use `<action> -> verify: <deterministic check>`.

## Task Granularity

Each task MUST represent one independently reviewable outcome with explicit acceptance criteria.
Each task MUST identify its owner, dependencies, implementation order, and acceptance criteria.

Keep all work for one independently reviewable outcome in a single task. Split work into separate tasks when the tasks produce independently acceptable outcomes, a dependency requires sequential delivery, or disjoint file ownership enables safe parallel execution.

Test-first work, implementation, and verification of an outcome MUST be ordered steps within
the same task. Verification instructions MUST compare the result with both the success criteria and approved plan. Integration tests that check several parts together or require a real external program, model, service, or hardware MAY remain separate.

This makes execution reviewable and safe to distribute among sub-agents.

## Sub-agents

Prefer to divide implementation into sub-agent tasks with safe parallelization boundaries. Where sub-agents are used, the plan MUST define three distinct roles: Worker, Validator, and Orchestrator. Three roles for a given work item MUST be held by different agents. The plan MUST identify which Validator receive each Worker's result.

The root process acts as an Orchestrator.
Sub-agents MUST use the following model and reasoning-effort assignments:

- Worker: `gpt-6.1-sol` with `low` reasoning effort.
- Validator: `gpt-6.1-sol` with `medium` reasoning effort.

Each separate task MUST receive a newly created Worker and a newly created Validator. Both agents
MUST start the task with clean context windows containing only the task-specific context and
project instructions needed to perform their roles. A Worker or Validator assigned to one task
MUST NOT be reused for a separate task. The Orchestrator coordinates multiple tasks.

The Worker implements the task, records verification evidence, and submits both to the Validator.
The Validator independently checks the result against the task's acceptance criteria, approved
plan, tests, architecture rules, and scope, then reports findings and evidence to the Orchestrator.
The Orchestrator reviews the Validator's report and either accepts the work or returns actionable
feedback to the Worker.

When the Orchestrator returns work, the same Worker that implemented the task MUST revise it and resubmit it to the same Validator that performed the preceding review. That Validator MUST repeat validation and send an updated report to the Orchestrator. A cycle starts when the Worker submits a result and ends when the Orchestrator accepts or returns it; the initial submission is cycle 1. A work item MUST NOT exceed three Worker → Validator → Orchestrator cycles.

If the Orchestrator does not accept the work by the end of cycle 3, all agent work on that task MUST
halt. The Orchestrator MUST prepare a manual-review summary containing the work item's scope, each
attempt and its changes, validation findings and evidence, unresolved acceptance criteria or
issues, and the decision required. Work MUST NOT resume until a manual reviewer explicitly authorizes the next action.

## Engineering Standards

- Single Responsibility and Interface Segregation are mandatory. Each entity MUST have one
  coherent reason to change.
- New or changed functions MUST declare parameter and return types where supported.
- Implementations MUST prefer existing project data types and contracts over ad-hoc dictionaries,
  tuples, or parallel representations.
- Code MUST NOT add unrequested flexibility, optional behavior, abstraction, or configuration.
- Reviews MUST verify evidence, coverage, scope traceability, simplicity, type correctness, responsibility boundaries, and architecture classifications.

## Governance

This constitution is Transcriber's highest-priority engineering policy. Specifications, plans,
tasks, implementations, and reviews MUST comply. It supersedes conflicting project documents
unless formally amended.

Amendments MUST document their motivation, affected principles, impact, migration work, and MUST receive explicit project-owner approval.

Every implementation plan and code review MUST check constitution compliance. Reviewers MUST reject work lacking automated verification, task traceability, required architecture classification, or deterministic verification. Evidence of executing a test before implementation is NOT required. Complexity and claimed deviations MUST be resolved through a constitution amendment or design change; informal exceptions are forbidden.

**Version**: 2.3.0 | **Ratified**: 2026-07-30 | **Last Amended**: 2026-10-14
