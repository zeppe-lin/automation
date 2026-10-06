# NEWS-driven GitHub releases

The release workflow publishes repository-maintained release notes from
`NEWS.md` when a version tag is pushed.

This mechanism is separate from the repository-event notification pipeline.
Release publication projects already-maintained release authority into the
forge; it does not classify commits, route notifications, or reconstruct
release prose from commit history.

## NEWS contract

Each release has one level-two Markdown section whose final heading token is
the version without the leading `v` from the Git tag:

```markdown
# NEWS

## pkgman 6.3 — Unreleased

Release notes for 6.3.

## pkgman 6.2 — 2025-12-12

Release notes for 6.2.
```

A bare version heading is also valid:

```markdown
## 1.0.0 — 2026-08-26
```

Before creating a release tag, replace `Unreleased` with the release date.  The
extractor requires exactly one matching version section and rejects missing,
duplicate, or empty sections.  Level-three and deeper headings remain part of
the release body.

Supported release tags begin with `v` and contain a dotted version, for example
`v6.3`, `v1.0.0`, or `v1.0.0-rc.1`.

## Caller workflow

A repository keeps a small tag-triggered caller workflow:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  release:
    uses: zeppe-lin/automation/.github/workflows/release-from-news.yml@<reviewed-commit-sha>
    secrets:
      automation_dispatch_token: ${{ secrets.AUTOMATION_DISPATCH_TOKEN }}
```

Pin the reusable workflow to a reviewed immutable commit SHA in production.
The dispatch token should be a fine-grained token scoped to
`zeppe-lin/automation` with `Contents: write`; source repositories do not need
SMTP or IRC credentials.
The called workflow cannot elevate permissions beyond the caller, so the caller
must grant `contents: write` for GitHub release creation.

Optional inputs are available for repositories that use another NEWS pathname,
a custom release title, or prerelease publication:

```yaml
jobs:
  release:
    uses: zeppe-lin/automation/.github/workflows/release-from-news.yml@<reviewed-commit-sha>
    with:
      news_path: NEWS.md
      release_name: v1.0.0
      prerelease: false
```

## Execution boundary

The reusable workflow runs in the caller repository context.  Its checkout step
therefore checks out the caller's tagged source tree.  The NEWS extractor is
packaged as an action inside this repository and referenced with the GitHub
self-repository `$/` syntax, which binds the helper implementation to the same
revision as the reusable workflow.

The workflow treats tag names, paths, and release titles as data.  Values are
passed through environment variables or action inputs rather than interpolated
into executable shell source.

After the GitHub Release has been published, the workflow sends a
`release-published` repository-dispatch event to `zeppe-lin/automation`.  The
central delivery workflow re-fetches the release and owns mailing-list and IRC
delivery.  See `release-delivery.md` for the transport, queue, and replay
contract.

## Local validation

Run the extractor regression suite with:

```sh
python3 -m unittest tests/test_extract_news.py
```

A repository can also validate a prospective release section directly:

```sh
.github/actions/extract-news/extract-news.py \
    v6.3 NEWS.md /tmp/release-notes.md
```

The generated file contains only the body of the matching release section; the
section heading is represented by the GitHub release title.
