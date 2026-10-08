# Local qualification

Zeppe-Lin Automation is qualified locally before a forge workflow is trusted.
GitHub Actions is an adapter for events, permissions, artifacts, and secrets;
it is not the primary test environment.

Run the complete suite with:

```sh
make check
```

The default suite requires only Python 3 and Git. It does not contact GitHub,
Gmail, LiberaChat, or any other Internet service and does not require production
credentials.

## Test layers

The suite is divided by failure domain.

```text
unit / contract tests
    NEWS extraction
    release normalization
    channel rendering
    mail construction
    IRC framing
    Git-ref delivery state
    forge adapter command construction
    workflow-policy checks

behavioral Git integration tests
    real commit graphs and ref transitions
    oldest-first collection and force detection
    classification, routing, and rendered artifacts

loopback integration tests
    verified TLS SMTP client <-> fixture SMTP server
    verified TLS IRC/SASL client <-> fixture IRC server
    release fixture -> render -> claim -> SMTP -> delivered ref
```

The TLS fixtures use the repository-owned certificate and private key under
`tests/fixtures/tls/`. They are public test material, not operational
credentials. The clients still perform certificate verification; the tests
point `AUTOMATION_CA_FILE` at the test CA certificate rather than disabling
verification.

## Offline release preparation

A published GitHub Release payload can be captured or written as a fixture and
fed directly to the collector:

```sh
python3 libexec/prepare-release.py \
    zeppe-lin/pkgman \
    v6.3 \
    /tmp/release-delivery \
    --release-json tests/fixtures/example-release.json
```

The command writes exactly the artifacts that the central delivery workflow
would retain:

```text
manifest.json
mail-user.json
mail-dev.json
irc.txt
```

No network access occurs when `--release-json` is used.

## Local delivery state

Delivery state is ordinary Git state. Point the command at any disposable Git
repository:

```sh
export AUTOMATION_STATE_REPOSITORY=/tmp/automation-state
export AUTOMATION_RUN_ID=manual-test
export AUTOMATION_RUN_ATTEMPT=1

python3 libexec/delivery-state.py \
    claim zeppe-lin/pkgman v6.3 mail-user
```

Without `AUTOMATION_STATE_REMOTE`, refs remain local. Production sets the
remote to `origin`, causing exactly the same state transition to be mirrored to
the central automation repository.

This lets replay and duplicate-suppression behavior be tested without GitHub's
REST API.

## Loopback transports

`tests/support/servers.py` contains minimal TLS SMTP and IRC fixtures. They are
protocol fixtures, not general-purpose servers. They bind only to localhost,
accept synthetic credentials, record the submitted message, and terminate.

The production clients remain the clients under test:

```text
libexec/send-mail.py
libexec/send-irc.py
```

The integration suite therefore exercises the same TLS, SMTP authentication,
IRC capability negotiation, SASL authentication, JOIN, and message submission
paths used in production.

## Forge adapters

Forge-facing commands use `gh` only at the outermost boundary. Unit tests put a
synthetic `gh` executable first in `PATH` and inspect the requested operation.
Secrets are supplied through the environment and are not expected to appear in
arguments or logs.

Workflow policy tests additionally reject:

* embedded Python heredocs;
* shell programs hidden in workflow `run` blocks;
* mutable third-party action tags.

A workflow regression should therefore fail locally before a tag or dispatch is
sent to GitHub.

## Manual transport testing

For deeper debugging, instantiate the fixture servers from Python and invoke the
real client with `AUTOMATION_CA_FILE` pointing at
`tests/fixtures/tls/localhost.crt`. Do not weaken TLS verification and do not
substitute production credentials into fixture tests.

## Real Git push qualification

Push-event tests build disposable Git repositories and drive the real command
entry points. They do not mock repository history.

The integration suite currently exercises:

```text
ordinary multi-commit update
oldest-first topological enumeration
UTF-8 and shell-looking commit text
new branch with unique commits
new branch pointing at already-known history
branch deletion
empty update
non-fast-forward / force push
annotated tag creation and deletion
30-commit push beyond webhook payload limits
merge commits
revert commits
missing pre-push objects
Codebook classification failure
obsolete [notify] rejection
channel artifact ordering
```

This is intentionally stronger than constructing a synthetic manifest and
calling a renderer. The collector is qualified against Git's observable graph
and commit objects.

A complete local push dry run is:

```sh
python3 libexec/prepare-push.py \
    /path/to/full/repository \
    event.json \
    /tmp/push-delivery
```

Inspect `manifest.json`, `requirements.json`, `mail-dev/`, `mail-user/`, and
`irc.txt` before any forge adapter or external delivery is introduced.
