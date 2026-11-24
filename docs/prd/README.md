# Product Requirements Documents

Use a PRD to define the user outcome, scope, and acceptance criteria for a milestone or a change to a supported workflow or public contract. Subsystem documentation describes how Auralis works. GitHub issues track implementation and fixes. The [master roadmap](../MASTER_ROADMAP.md) sets milestone order, and the relevant release checklist records validation results.

## PRD index

| PRD | Milestone | State | Product outcome |
|---|---|---|---|
| [Application startup](application-startup.md) | v1.5.1 recovery | PROPOSED | Launch Auralis with truthful readiness and predictable shutdown. |
| [Library and playback recovery](library-playback-recovery.md) | v1.5.1 recovery | PROPOSED | Scan, browse, and play a fresh library reliably. |

## Writing a PRD

1. Copy [TEMPLATE.md](TEMPLATE.md) to `docs/prd/<feature>.md`, using a kebab-case feature name, and add it to the index. Link it from the roadmap if it defines a milestone outcome.
2. Give each goal, non-goal, and requirement a stable ID in the form `PREFIX-AREA-NNN`. Use a distinct two- to six-letter capitalized prefix for each PRD. Define each ID once and preserve retired IDs in place with the revision that withdrew them.
3. Give each requirement one observable outcome. Use **MUST** for a requirement, **SHOULD** for a recommendation, and **MAY** for a permitted option. Link current behavior to a source, test, or commit and date the snapshot. Use **Phase 0: verify** with a concrete check when evidence is missing.
4. List the affected surfaces and environments, such as desktop development, packaged Electron, standalone web, or audio formats. State why each one is in scope and name the fixtures and observable pass conditions for its acceptance scenarios.
5. Put discovery, baselines, and unresolved decisions in Phase 0. Put implementation and validation in subsequent phases, each with a dependency where applicable and a measurable exit. Define metrics in the PRD and link to the checklist or roadmap for measured results.

## Lifecycle

| State | When to use it |
|---|---|
| **PROPOSED** | A draft is ready for review. Existing work and evidence can be linked here. |
| **APPROVED** | The project owner accepted the scope and recorded the decisions in the PRD. |
| **ACTIVE** | Delivery is underway against the approved PRD. The **Tracking** field links the existing parent or phase issues. |
| **SHIPPED** | The phase exits have evidence and the product outcome has shipped. |
| **WITHDRAWN** | The owner ended the work. Record the reason. |
| **SUPERSEDED** | A later PRD owns the outcome. Link the replacement. |

For each revision or state change, update the status date and append a row to the review log. Record owner approval and decisions in that log and in §10. Link implementation issues to their PRD and cite requirement IDs in their acceptance criteria. Reuse issues already tracking the work.

## Review checklist

- The thesis identifies the users and workflow. Scope, non-goals, risks, and design owners are explicit.
- Current-behavior claims have dated evidence. A component test supports only the behavior it exercises.
- Each requirement has a stable ID and an observable result. Acceptance names the fixture or environment, the steps, and the pass condition.
- Phase exits are measurable and account for dependencies. Decisions have an owner and show the consequences of the options.
- Links resolve. The index, roadmap, tracking references, and review log agree with the current scope.

The section order and lifecycle follow the PRD convention in `gamebyro-redux`.
