# Release announcement delivery

Release publication and release announcement delivery are separate operations.
The source repository owns the release tag and `NEWS.md`; the automation
repository owns external delivery.

```text
source repository
    tag -> NEWS section -> GitHub Release
                           |
                           `-- repository_dispatch { repository, tag }
                                      |
                                      v
                              zeppe-lin/automation
                                      |
                              collect published release
                                      |
                                   render
                           /-----------+-----------\
                          v            v            v
                     user mail     dev mail        IRC
```

The dispatch contains no release prose and no transport credentials.  The
central collector fetches the published GitHub Release again and verifies the
repository owner, release tag, draft state, URL, and non-empty release notes.
This prevents caller-supplied text from becoming delivery authority.

## Routing

A tagged project release is currently rendered for three destinations:

* the user mailing list receives the complete release notes;
* the development mailing list receives release metadata and the complete
  release notes;
* IRC receives one bounded line containing the project, tag, and durable GitHub
  Release URL.

Each destination has its own renderer.  Mail text is not reused as IRC text.
The routing is a release-specific policy slice; the broader commit-event
routing contract remains owned by the Codebook.

## Central queue

`.github/workflows/deliver-release.yml` runs only in this repository.  Its
workflow-level concurrency group is shared by all source repositories, so
release delivery is serialized across the project rather than separately in
every caller repository.

A normal `repository_dispatch` performs delivery.  Manual `workflow_dispatch`
runs are dry-run by default and always produce the rendered artifact.  Set the
manual `deliver` input only when external delivery is intended.

## Delivery state and replay

External transports are not safely retryable by assumption.  An SMTP server
can accept a message before a connection failure is observed, and IRC can
accept some lines before a socket is lost.

Before a destination performs network I/O, the workflow creates an attempt ref
in this repository:

```text
refs/automation/delivery/release/<owner>/<repo>/<tag>/<destination>/attempts/<run>-<attempt>
```

After successful submission it creates:

```text
refs/automation/delivery/release/<owner>/<repo>/<tag>/<destination>/delivered
```

A later run:

* skips a destination that already has a `delivered` ref;
* refuses to retry a destination with an unresolved attempt;
* proceeds only when an operator explicitly sets `force_replay` on a manual
  workflow dispatch.

The attempt refs are intentionally retained as audit evidence.  A forced replay
may duplicate a message if the preceding unresolved attempt actually reached
the external service; that risk is therefore an explicit operator decision,
not an automatic retry policy.

Mail additionally uses a stable `Message-ID` derived from the event ID and
destination.  This gives mailing-list software a stable identity across an
explicit replay, but the delivery ledger remains the primary duplicate guard.

## SMTP transport

Mail is delivered directly with Python's standard `smtplib`; no marketplace
mail action is involved.

Transport jobs run on `ubuntu-latest` by default.  To avoid shared-runner IP
reputation or network-policy problems, set `DELIVERY_RUNNER` to a JSON-encoded
GitHub `runs-on` value, for example `["self-hosted","linux","x64"]`.  Rendering
and routing do not change when transport moves to a dedicated runner.

Configure these repository variables on `zeppe-lin/automation`:

```text
DELIVERY_RUNNER     # optional JSON runs-on value
SMTP_HOST
SMTP_PORT          # default in the client: 465
SMTP_SECURITY      # ssl, starttls, or plain
MAIL_FROM
MAIL_USER_TO
MAIL_DEV_TO
```

Configure these repository secrets when authentication is required:

```text
SMTP_USERNAME
SMTP_PASSWORD
```

The transport supports an authenticated public SMTP service or a dedicated
project relay.  Moving delivery to a self-hosted runner or relay therefore does
not change rendering or event semantics.

## IRC transport

IRC is delivered by a small TLS/SASL PLAIN client implemented with Python's
standard library.  It sends one `PRIVMSG` per release announcement and enforces
the IRC protocol line limit after accounting for the destination channel.

Configure these repository variables:

```text
IRC_HOST
IRC_PORT           # default in the client: 6697
IRC_TLS            # default in the client: true
IRC_CHANNEL
IRC_NICK
IRC_USERNAME       # optional; defaults to IRC_NICK
IRC_SASL_USERNAME  # optional; defaults to IRC_NICK
```

Configure the SASL password as a repository secret:

```text
IRC_SASL_PASSWORD
```

The transport responds to `PING`, negotiates `sasl`, authenticates before
joining, and sends one bounded announcement.  It does not automatically retry
a partially uncertain session.

## Caller authentication

The NEWS release workflow dispatches the announcement only after the GitHub
Release has been published.  The caller supplies an
`automation_dispatch_token` secret.  For a fine-grained GitHub token, grant
`Contents: write` only on `zeppe-lin/automation`; GitHub requires that
permission for the repository-dispatch endpoint.

A project caller can normally use an organization secret:

```yaml
jobs:
  release:
    uses: zeppe-lin/automation/.github/workflows/release-from-news.yml@<sha>
    secrets:
      automation_dispatch_token: ${{ secrets.AUTOMATION_DISPATCH_TOKEN }}
```

SMTP and IRC credentials stay in `zeppe-lin/automation` and are never exposed
to source repositories.

## Local tests

Run the release pipeline tests with:

```sh
python3 -m unittest \
    tests/test_extract_news.py \
    tests/test_release_announcement.py \
    tests/test_delivery_transports.py \
    tests/test_delivery_state.py
```

The suite covers release normalization, separate renderers, UTF-8 bounded IRC
output, stable mail identity, an in-process IRC SASL exchange, and delivery
ledger behavior.
