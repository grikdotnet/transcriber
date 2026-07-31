# Code Entity Layers

Classification of code entities (classes, separate functions, packages) by layers according to architectural roles.

## Scope

This classification is applicable to the code for logic, data processing, communication and command execution.

Not applicable for:

* Reactive, UI-specific, output template code for interactions with users.
* Code for build automation, infrastructure management, development and testing environment setup.
* Test mocks and fixtures.
* Coding assistant skills, plugins, plans, todo.
* Temporary, one-time execution code and POC.
* Third-party packages, libraries, and modules.

## Layers

1. Infrastructure — concrete I/O, OS, network, runtime, persistence, and logging adapters.
2. Protocol/Wire — serialized boundary messages, commands, events, frames, codecs, and validation.
3. Domain/Model — pure logic, domain types, invariants, aggregate roots, and interfaces; no I/O implementations.
4. Service — use cases, workflows, lifecycle.
5. Composition — assembles Infrastructure, Protocol, Domain, and Service entities into the application roots used by Controllers.
6. Controller — entry points and input handling.

## Planning Architecture Gate

During planning, every new or changed in-scope code entity must be classified into layers.

A dependency means a source-level import, type reference, or construction reference.

Rules:

* Every code entity MUST belong to exactly one layer.
* Code entities from different layers MUST NOT be grouped together. Any mixed-layer package or other grouping MUST be split by layer.
* An interface and its implementations MUST have the same layer classification.
* A code entity MAY depend on entities of lower layers; it MUST NOT depend on entities of higher layers.
* Protocol MUST contain only boundary contracts, wire types, validation, and codecs.
* Protocol data types MAY be used directly by any higher layer.
* Domain MUST NOT depend on Infrastructure, Service, Controller, or UI.
* Controllers MUST NOT depend on Infrastructure.
* UI code MUST access application behavior through Controllers or Protocol contracts.

If in-scope code violates these rules, propose a fix instead of adding another exception.
