# Security and logging contract

Zeppe-Lin Automation sits between maintained project knowledge and external
transports. Its security model is therefore an authority and information-flow
contract, not only a collection of hidden strings.

## Authority boundaries

For release delivery:

```text
source repository
    owns tag and NEWS.md
        |
        v
GitHub Release
    published release authority
        |
        v
automation renderer
    owns channel projections
        |
        v
delivery ledger
    owns delivery state
        |
        v
SMTP / IRC
    external transports
```

A dispatch may identify a repository and tag. It does not become authority for
release prose. Automation re-fetches the published GitHub Release before it
renders or sends anything.

Rendered files are projections of public release authority. Delivery refs are
evidence about attempted and completed external effects. Neither may be used to
reconstruct source authority that no longer exists.

## Credential boundary

Transport credentials belong to `zeppe-lin/automation`, not to package or tool
repositories.

Secrets must:

* enter a process only through its environment;
* never appear in command-line arguments;
* never be written to rendered artifacts;
* never be copied into normalized manifests;
* never be included in Git ref names or delivery-state payloads;
* never be printed directly or through protocol debugging;
* remain available only to jobs that perform the corresponding transport.

Source repositories receive only the credential needed to request a central
automation dispatch. They do not receive SMTP or IRC credentials.

## Log contract

Logs are operational evidence, not packet captures.

Allowed log content includes:

```text
event IDs
repository and tag names
destination names
Git ref names
bounded status messages
numeric remote status codes
```

Logs must not contain:

```text
passwords or tokens
Authorization headers
SMTP authentication exchanges
IRC AUTHENTICATE payloads
complete environment dumps
unbounded remote response text
shell execution traces containing secret-bearing variables
```

GitHub secret masking is defense in depth only. It is not the primary control.
A transformed credential, such as the base64 payload used by SASL PLAIN, may no
longer match the original masked string.

The transport implementations therefore do not enable protocol debugging and
do not emit raw SMTP server response bodies or IRC protocol transcripts.

## Transport encryption

SMTP supports only:

```text
ssl
starttls
```

IRC always uses TLS. SASL PLAIN without TLS is deliberately unsupported.
Certificates are verified with Python's default platform trust store.

If a service cannot provide authenticated TLS, change the transport or place a
trusted local relay in front of it. Do not add an insecure mode to make a
workflow pass.


## Source repository acquisition

Push preparation treats the source repository as untrusted data. The central
GitHub adapter materializes it into a new bare repository and never checks out a
source working tree.

Git acquisition must not execute repository-owned hooks, filters, submodules, or
remote helpers. Ambient user/system Git configuration is suppressed for the
materialization subprocesses and allowed protocols are restricted to the
production HTTPS path plus local `file` remotes used by tests.

The production remote URL is derived from the already validated `owner/name`
repository identity. A dispatch payload cannot select an arbitrary network
endpoint. If an exact `before` or `after` object cannot be fetched, preparation
fails closed instead of consulting the webhook commit list as replacement
history.

## Failure semantics

A destination is claimed before network I/O and marked delivered only after the
transport reports success.

This yields three durable states:

```text
no claim
    no external attempt is known

attempt without delivered marker
    external effect is uncertain

delivered marker
    automation considers the destination complete
```

An uncertain attempt is not automatically retried. The operator must explicitly
request replay and accept the possibility that the preceding attempt actually
reached the external service.

Configuration is validated before a claim is created. A missing variable or
secret is therefore a configuration failure, not an uncertain delivery effect.

## Artifacts

Dry-run and preparation artifacts contain normalized public release data and
rendered channel messages only. They must remain useful for review and replay
without requiring access to transport credentials.

Adding a new artifact requires the same test: if the artifact were downloaded
by every collaborator with Actions access, would it reveal a credential or a
secret-derived value? If yes, the data does not belong in the artifact.
