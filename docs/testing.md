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
