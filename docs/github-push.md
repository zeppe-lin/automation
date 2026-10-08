# GitHub push adapter

GitHub is an event source and transport boundary. It is not the implementation
of push classification, rendering, or delivery.

The GitHub path is deliberately split in two:

```text
source repository
    |
    | $GITHUB_EVENT_PATH
    v
queue-push composite action
    |
    | repository_dispatch: push-observed
    | client_payload.envelope
    v
zeppe-lin/automation
    |
    v
prepare-github-push.py
    |
    +-- bare Git materialization
    `-- provider-neutral prepare_push()
            |
            v
       rendered artifact
            |
            v
       deliver-push.py
```

No GitHub push `commits` array crosses the dispatch boundary. GitHub documents
that array as bounded; repository history is therefore observed from Git using
the pushed `before` and `after` coordinates.

## Source-side adapter

A migrated repository needs only a small push workflow. It does not checkout or
execute the pushed repository contents and it receives no SMTP or IRC secrets.

After `automation` is published, callers should pin the action to the reviewed
commit SHA:

```yaml
name: Queue repository notifications

on:
  push:

permissions:
  contents: read

jobs:
  queue:
    runs-on: ubuntu-latest
    steps:
      - uses: zeppe-lin/automation/.github/actions/queue-push@<commit-sha>
        with:
          dispatch-token: ${{ secrets.AUTOMATION_DISPATCH_TOKEN }}
```

`AUTOMATION_DISPATCH_TOKEN` is the only central credential exposed to a source
repository. During migration its organization-secret visibility should contain
only repositories that have moved to this adapter.

The action reads `$GITHUB_EVENT_PATH` as a file. It does not interpolate commit
messages, authors, refs, or other event fields into shell source.

## Dispatch envelope

The source adapter emits only:

```json
{
  "schema": 1,
  "event": "push",
  "repository": "zeppe-lin/example",
  "repository_url": "https://github.com/zeppe-lin/example",
  "ref": "refs/heads/master",
  "before": "...",
  "after": "...",
  "compare_url": "..."
}
```

Provider `commits`, `head_commit`, and `forced` fields are excluded. The central
engine derives commit history, metadata, and ancestry from Git.

Repository identity is restricted to the Zeppe-Lin organization. Presentation
URLs are canonicalized rather than accepted as arbitrary dispatch-controlled
network locations.

## Repository materialization

The central preparation command creates a new bare Git repository. No source
working tree is checked out.

It fetches:

* current branch and tag refs, for reachability context;
* the exact `before` object when required;
* the exact `after` object when required.

The endpoint fetches matter for force pushes and deletions because the pre-push
object may no longer be referenced after the event.

Materialization suppresses ambient system/global Git configuration and admits
only HTTPS and local-file transports. `ext::` remote helpers are rejected. The
production GitHub remote is derived from the validated repository identity:

```text
https://github.com/<owner>/<repository>.git
```

An unavailable required object is a hard failure. Automation does not rebuild
history from webhook commit data when Git cannot provide the object.

## Central workflow

`.github/workflows/deliver-push.yml` is a forge adapter. Its responsibilities
are limited to:

* receive `push-observed` repository dispatches;
* checkout the trusted automation implementation;
* invoke `prepare-github-push.py`;
* carry the rendered artifact across job boundaries;
* expose transport credentials only to the corresponding delivery jobs;
* invoke `deliver-push.py` for each destination.

Actual delivery is disabled unless the automation repository variable
`PUSH_DELIVERY_ENABLED` is exactly `true`. Leaving the variable absent or false
therefore gives the migration a central dry-run mode while legacy notifications
remain active.

The central workflow uses a shared concurrency group with queued pending runs.
This prevents the default Actions behavior from replacing an older pending run
when another event arrives. The queue is still a forge scheduling mechanism,
not project authority; its finite capacity and provider scheduling semantics are
not a replacement for the Git delivery ledger.

## Local qualification

The GitHub boundary is tested without GitHub itself:

* recorded GitHub-shaped push fixtures qualify normalization;
* fake `gh` captures the exact repository-dispatch request;
* real disposable bare remotes qualify Git acquisition;
* force pushes and deleted refs require fetching an otherwise unreachable
  pre-push object;
* deliberately truncated provider commit arrays still produce complete history;
* the source queue command and central prepare command are exercised together;
* hostile provider commit text is proved not to execute or cross the normalized
  dispatch membrane.

The same central preparation command used by Actions can therefore be run
locally with `--remote` pointing at a disposable repository.
