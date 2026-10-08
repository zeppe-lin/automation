# Zeppe-Lin Automation

**Repository Events into Maintained Knowledge**

Zeppe-Lin Automation is the shared automation engine for the
[Zeppe-Lin Project](https://github.com/zeppe-lin).

It classifies repository events, validates their metadata, renders
channel-specific messages, routes knowledge to the appropriate
audiences, and records delivery state.

The repository is being established as the successor to:

```text
zeppe-lin/.github-shared-workflows
```

The existing shared-workflow repository contains GitHub Actions
templates for IRC and mailing-list notifications.

Those workflows remain in service during the transition, but they are
not the intended long-term architecture.

This repository separates the durable automation machinery from the
forge that invokes it.

```text
repository event
`-- provider adapter
    `-- normalized event
        `-- classification
            `-- validation
                `-- rendering
                    `-- routing
                        `-- delivery
                            `-- recorded result
```

## Purpose

The repository exists to provide one maintained implementation for:

* repository-event normalization;
* semantic event classification;
* commit-tag and trailer validation;
* knowledge-routing decisions;
* development and user mailing-list messages;
* IRC summaries and notices;
* system-news and release-note checks;
* delivery retries, replay, and audit state;
* GitHub integration;
* future GitLab or other forge integration.

The generic pipeline should not depend on GitHub Actions semantics after
the provider event has been normalized.

GitHub workflows are adapters.

They are not the engine.

## Transition from `.github-shared-workflows`

The migration begins from the existing reusable workflows:

```text
notify-irc.yml
notify-mail-dev.yml
notify-mail-tag.yml
```

Those workflows currently:

* receive GitHub push events;
* send push summaries to IRC;
* send one development-list message per commit;
* route `[notify]` commits to the user mailing list.

The replacement architecture will:

* replace `[notify]` with semantic event classes;
* treat commit text and event fields as untrusted data;
* preserve commit ordering;
* render separate IRC, development-mail, and user-mail messages;
* serialize shared IRC delivery across repositories;
* validate required commit trailers and durable knowledge artifacts;
* distinguish policy failures from transport failures;
* support bounded retries and replay without a new source commit;
* expose provider-neutral scripts that can be tested outside a forge.

During migration:

```text
.github-shared-workflows
    legacy delivery still used by callers

automation
    new canonical implementation under development
```

The old workflows should be retired only after the new pipeline has
been tested in dry-run mode, compared against representative repository
events, and enabled without duplicate external delivery.

## Event Model

Project-wide event semantics are defined by *The Codebook*.

The maintained event tags are:

```text
[news]
[security]
[breaking]
[deprecation]
```

Ordinary commits carry no event tag.

Tags classify why knowledge must propagate.

Git trailers carry structured event metadata, including fields such as:

```text
Affected:
Action:
News:
Migration:
Release-Note:
Reference:
```

This repository implements that contract.

It does not invent project doctrine independently from the Codebook.

## Architecture

The automation is divided into two layers.

### Generic Engine

The generic layer owns:

```text
collect
classify
validate
render
route
deliver
replay
```

It consumes normalized event manifests and produces deterministic
routing decisions and channel-specific output.

It should be usable from:

* local tests;
* recorded event fixtures;
* GitHub Actions;
* future GitLab CI;
* manual replay tools.

### Forge Adapters

Forge-specific integration owns:

* reading provider event payloads;
* acquiring repository metadata;
* exposing forge secrets;
* reporting checks and artifacts;
* invoking the generic engine;
* translating delivery state into provider status.

Initial integration lives under:

```text
.github/workflows/
```

Future GitLab integration may live under:

```text
gitlab/
```

Provider adapters must remain thin enough that the event model and
rendering behavior can be tested without the provider.

## Repository Layout

```text
automation/
    commands/
libexec/
tests/
    integration/
    support/
docs/

.github/
    actions/
    workflows/
```

The maintained responsibilities are:

| Path                    | Responsibility                                             |
| ----------------------- | ---------------------------------------------------------- |
| `automation/`           | Importable provider-neutral engine and explicit adapters   |
| `automation/commands/`  | Command-line composition and argument/error handling       |
| `libexec/`              | Thin executable membrane into `automation.commands`        |
| `tests/`                | Unit and contract qualification                            |
| `tests/integration/`    | Real Git and loopback protocol behavior                    |
| `tests/support/`        | Local fixture repositories and protocol servers            |
| `docs/`                 | Event schema, transport, replay, and operator documentation|
| `.github/actions/`      | Thin caller-facing GitHub adapters                         |
| `.github/workflows/`    | GitHub event, permission, artifact, and secret plumbing    |

Public commands may be added under `bin/` when an operator-facing interface is
justified. Internal implementation must not migrate back into `libexec/` or
workflow YAML merely because those surfaces are executable.

The boundary between the generic engine and forge adapters must remain.

## Current Status

This repository is in bootstrap and migration state.

The initial work is expected to establish:

1. the normalized event manifest;
2. event-tag and trailer validation;
3. deterministic renderers;
4. dry-run artifacts;
5. fixture-based tests;
6. GitHub adapter workflows;
7. queued IRC and mail delivery;
8. replay and delivery records;
9. migration of callers from `.github-shared-workflows`;
10. retirement of the legacy workflows.

Until migration is complete, the repository should state clearly which
components are experimental and which are used for production delivery.

## Source and Publication

The canonical source is this repository:

```text
https://github.com/zeppe-lin/automation
```

Generated workflow artifacts, rendered messages, and delivery logs are
representations of repository events.

They are not independent project authority.

The Codebook defines event and routing doctrine.

The originating repository records the change.

This repository implements classification and delivery.

## Security

Automation processes untrusted repository metadata and has access to
notification credentials.

The implementation must therefore:

* treat event fields and commit messages as data;
* avoid interpolating untrusted values into shell source;
* separate unprivileged parsing from secret-bearing delivery;
* declare minimum forge permissions;
* pin third-party actions to reviewed immutable revisions;
* avoid storing credentials in logs or artifacts;
* preserve rendered messages for audit without preserving secrets;
* make retries bounded and delivery results inspectable.

A notification system is part parser, part transport, and part
credential boundary.

All three must be maintained.

## Contributions

Corrections, implementation work, provider adapters, tests, templates,
and documentation are welcome.

Before submitting changes, read:

```text
CONTRIBUTING.md
MAINTAINING.md
```

Contributions should preserve:

* the Codebook as the authority for event semantics;
* provider-neutral behavior after event normalization;
* deterministic rendering;
* explicit routing decisions;
* reproducible tests;
* minimal secret exposure;
* replayable and inspectable delivery state;
* compatibility with the documented migration plan.

A GitHub-specific convenience must not silently become the generic
event model.

## License

Unless a file states otherwise, this repository is licensed under the
GNU General Public License, version 3 or later.

```text
SPDX-License-Identifier: GPL-3.0-or-later
```

See `COPYING` for the complete license terms and `COPYRIGHT` for
copyright, attribution, and third-party notices.

---

The forge reports that something happened.

The automation must determine what the project is required to remember.

## Local qualification

Automation is developed as locally executable machinery first. Run:

```sh
make check
```

The suite does not require GitHub, Gmail, LiberaChat, production credentials,
or Internet access. See `docs/testing.md` for the fixture model and
`docs/issue-1-status.md` for the current implementation boundary of issue #1.
