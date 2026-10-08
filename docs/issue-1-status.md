# Automation issue #1 implementation status

Issue #1 defines the migration from ad hoc GitHub notification workflows to an
event-aware delivery pipeline. The repository currently implements one complete
vertical slice: **published project releases**.

This document records implementation state. It does not replace the issue or
the Codebook.

## Implemented for release events

The following issue #1 requirements have concrete implementation for published
release events:

| Requirement | Release-event status |
| --- | --- |
| Treat external fields as data | Implemented |
| Deterministic normalized manifest | Implemented |
| Separate user-mail, development-mail, and IRC renderers | Implemented |
| Bounded single-line IRC output | Implemented |
| Central cross-repository queue | Implemented by the automation workflow concurrency group |
| Secret-bearing transport isolated from source repositories | Implemented |
| Direct SMTP and IRC transports without marketplace transport actions | Implemented |
| Attempt-before-effect and delivered-after-effect evidence | Implemented with Git refs |
| Refuse automatic replay of uncertain effects | Implemented |
| Explicit operator replay | Implemented |
| Dry-run rendered artifact | Implemented through manual workflow preparation |
| Immutable third-party action pins | Enforced by local tests |
| Local fixture tests | Implemented for release collection, SMTP, IRC, state, and end-to-end delivery |
| Credential-safe diagnostics | Implemented for current SMTP/IRC clients |

The release pipeline is:

```text
NEWS.md
    |
    v
published GitHub Release
    |
    v
release manifest
    |
    +--> user-mail rendering
    +--> development-mail rendering
    `--> IRC rendering
            |
            v
       delivery claim
            |
            v
       transport effect
            |
            v
       delivered evidence
```

## Not yet implemented

The general repository-event pipeline remains open work:

* push-event collection from `$GITHUB_EVENT_PATH`;
* oldest-first Git commit enumeration from `before..after`;
* explicit handling of branch creation, deletion, force-push, tag push, empty
  ranges, and large pushes;
* Codebook tag classification for `[news]`, `[security]`, `[breaking]`, and
  `[deprecation]`;
* Git trailer parsing and validation;
* durable `News:` and `Migration:` artifact validation;
* per-commit routing according to the Codebook matrix;
* development commit mail in commit order;
* user mail only for events whose classification requires it;
* push/event IRC aggregation with omission accounting;
* generic normalized event manifests and golden fixtures;
* transport retry policy beyond explicit replay of uncertain effects;
* operator replay tooling spanning all event types;
* migration of existing callers from `.github-shared-workflows`;
* retirement of the legacy notification workflows.

## Codebook dependency

The current Codebook already defines the maintained event tags and the broad
routing matrix. Some repository-level enforcement details still need to remain
synchronized with `zeppe-lin/codebook#1`, especially trailer cardinality,
artifact-reference rules, and edge-case event semantics.

Automation must not invent missing doctrine to make implementation convenient.
Where policy is not normative enough to validate mechanically, the correct next
step is to amend the Codebook first.

## Next tranche

The next implementation tranche should begin with a provider-neutral local push
collector and fixture manifest, not another GitHub workflow.

A suitable order is:

```text
1. collect a Git push fixture into a normalized manifest
2. enumerate commits oldest first from a local fixture repository
3. classify subject tags and trailers
4. validate Codebook invariants
5. derive routing decisions
6. render deterministic channel files
7. exercise all of the above with fixtures and golden output
8. only then add a thin GitHub event adapter
```

This preserves the repository rule: locally executable machinery first, forge
adapter second.
