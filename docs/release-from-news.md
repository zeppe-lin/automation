# NEWS-driven GitHub releases

A project release is published from repository-maintained `NEWS.md`. The source
repository owns the tag and release notes; Zeppe-Lin Automation supplies a
small forge adapter that projects that authority into a GitHub Release and then
queues central announcement delivery.

This is separate from generic commit-event classification. Release publication
does not reconstruct prose from commit history.

## NEWS contract

Each release has exactly one level-two Markdown section whose final heading
token is the tag version without the leading `v`:

```markdown
# NEWS

## pkgman 6.3 — 2026-10-08

Release notes for 6.3.
```

A bare version heading is also valid. Missing, duplicate, or empty matching
sections are rejected. Level-three and deeper headings remain part of the body.

Supported tags are dotted `v`-prefixed versions such as `v6.3`, `v1.0.0`, or
`v1.0.0-rc.1`.

## Caller workflow

The source repository keeps a deliberately small tag-triggered workflow. It
checks out the tag and invokes the automation composite action pinned to one
reviewed commit:

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
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<reviewed-checkout-sha>
        with:
          fetch-depth: 0

      - uses: zeppe-lin/automation/.github/actions/release-from-news@<reviewed-automation-sha>
        with:
          tag: ${{ github.ref_name }}
          repository: ${{ github.repository }}
          github-token: ${{ github.token }}
          dispatch-token: ${{ secrets.AUTOMATION_DISPATCH_TOKEN }}
```

Optional inputs are `news`, `release-name`, and `prerelease`.

The source repository receives no SMTP or IRC credentials.

## Adapter boundary

The composite action contains no release parser, GitHub-release state machine,
or dispatch JSON implementation. It delegates to locally executable commands
under `libexec/`:

```text
extract-news.py
publish-github-release.py
queue-release-delivery.py
```

Those commands are independently testable with local files and a synthetic
`gh` executable. GitHub Actions supplies checkout state, permissions, and
tokens only.

## Local validation

Run all automation tests with:

```sh
make check
```

Validate only a prospective NEWS section with:

```sh
python3 libexec/extract-news.py v6.3 NEWS.md /tmp/release-notes.md
```

The forge publication commands can be qualified with a fake `gh` executable;
see `testing.md`.
