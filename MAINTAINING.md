# Maintaining Zeppe-Lin Automation

Zeppe-Lin Automation is an executable system first and a forge integration
second.

The repository must remain locally inspectable and locally testable. GitHub
Actions adapts provider events, permissions, artifacts, and credentials to the
local commands; workflow YAML must not become the implementation.

## Boundaries

The maintained direction is:

```text
provider event
    |
    v
provider adapter
    |
    v
normalized manifest
    |
    +--> validation / routing
    |
    +--> deterministic rendering
    |
    v
delivery state
    |
    v
transport actuator
```

Keep these boundaries explicit:

* provider adapters may know GitHub event and API shapes;
* normalized manifests must not contain credentials;
* renderers perform no external I/O;
* delivery state is recorded before and after external effects;
* transport commands receive credentials only through their environment;
* workflows select commands and supply forge-owned data, but do not implement
  parser, routing, state-machine, or transport logic.

## Workflow rule

A behavior that can be run locally belongs in a script, not in YAML.

Workflow `run` steps should normally be one command. A short sequence of local
commands is acceptable when it is only stage composition. Inline Python,
heredoc-generated JSON, protocol handling, retry loops, and shell parsing of
provider event fields are not acceptable workflow implementation.

Third-party actions must be pinned to reviewed full commit SHAs.

## Local qualification

Before changing a workflow, first make the corresponding local command and its
tests correct.

Run:

```sh
make check
```

The default suite must not require GitHub, Gmail, LiberaChat, production
credentials, or Internet access. Network integration tests use loopback fixture
servers and synthetic credentials only.

A workflow should be treated as an uninteresting adapter after the local suite
is green.

## Secrets and logs

Follow `docs/security.md`.

In particular, never rely on forge masking as the primary credential boundary.
A secret or a transformed secret must not be emitted by the program in the
first place.

## Doctrine

Project-wide event classification and routing are owned by the Codebook.
Automation implements that doctrine; it does not complete or reinterpret
missing policy on its own.

When Codebook policy is ambiguous or contradictory, stop at the boundary and
fix the Codebook before adding enforcement here.
