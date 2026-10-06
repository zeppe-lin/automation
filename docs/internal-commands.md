# Internal command contracts

The commands under `.github/actions/` and `libexec/` are implementation
boundaries of Zeppe-Lin Automation. They are intentionally small, use only the
Python standard library, and are usable from local tests without GitHub Actions.

They follow these common rules:

* structured or durable data is written to files, not shell-generated workflow
  outputs;
* credentials are supplied only through environment variables;
* credentials are never accepted as command-line arguments;
* stdout contains bounded operational state, never protocol transcripts;
* stderr contains bounded diagnostics, never credentials or transformed
  credentials;
* exit status `2` means command-line misuse unless a command documents another
  status explicitly.

## `extract-news.py`

```text
extract-news.py TAG NEWS OUTPUT
```

Extract exactly one level-two NEWS section matching the version in `TAG` and
write the section body to `OUTPUT`.

The command has no network access and consumes no credentials. On success it
prints only the selected version.

## `collect-github-release.py`

```text
collect-github-release.py REPOSITORY TAG OUTPUT
```

Fetch the published GitHub Release for a Zeppe-Lin repository and normalize it
into `OUTPUT` as schema-1 JSON.

`REPOSITORY` and `TAG` select authority; they do not provide release prose. The
release body, title, URL, draft state, and prerelease state are fetched again
from GitHub.

Environment:

```text
GITHUB_TOKEN    optional token used only as an Authorization header
```

On success stdout contains only the normalized event ID.

## `render-release.py`

```text
render-release.py MANIFEST OUTPUT-DIR
```

Render a normalized release manifest into:

```text
manifest.json
mail-user.json
mail-dev.json
irc.txt
```

The renderer performs no network I/O and consumes no credentials. These files
are safe to retain as workflow artifacts because they contain published release
information only.

## `delivery-state.py`

```text
delivery-state.py claim REPOSITORY TAG DESTINATION [--force]
delivery-state.py delivered REPOSITORY TAG DESTINATION
```

Maintain the Git-ref delivery ledger in `zeppe-lin/automation`.

Environment:

```text
GITHUB_REPOSITORY
GITHUB_TOKEN
GITHUB_SHA
GITHUB_RUN_ID
GITHUB_RUN_ATTEMPT    optional; defaults to 1
```

Exit statuses for `claim`:

```text
0     claim created; transport may proceed
20    destination already delivered; transport must not run
21    unresolved prior attempt exists; explicit replay is required
```

The GitHub token is used only in the HTTP Authorization header. It is never
written to the ref name, payload, stdout, or stderr.

## `send-mail.py`

```text
send-mail.py MESSAGE.json
```

Submit one rendered message over TLS-protected SMTP.

Environment:

```text
SMTP_HOST
SMTP_PORT          optional; defaults to 465
SMTP_SECURITY      optional; ssl or starttls, defaults to ssl
SMTP_USERNAME      optional authentication identity
SMTP_PASSWORD      required when SMTP_USERNAME is set
MAIL_FROM
MAIL_TO
```

Authenticated plaintext SMTP is not supported. Certificate verification uses
the platform trust store.

Remote SMTP response text is deliberately not printed. Authentication failures,
server rejections, disconnects, and transport/TLS failures are reduced to
bounded diagnostics so a hostile or misconfigured server cannot inject
credential-like or control data into workflow logs.

On success stdout contains only the number of accepted recipients.

## `send-irc.py`

```text
send-irc.py MESSAGE.txt
```

Submit exactly one IRC `PRIVMSG` over TLS after SASL PLAIN authentication.

Environment:

```text
IRC_HOST
IRC_PORT           optional; defaults to 6697
IRC_CHANNEL
IRC_NICK
IRC_USERNAME       optional; defaults to IRC_NICK
IRC_SASL_USERNAME  optional; defaults to IRC_NICK
IRC_SASL_PASSWORD
```

TLS is mandatory. There is intentionally no plaintext mode because SASL PLAIN
encodes rather than encrypts the credential.

The client never logs IRC protocol traffic. In particular, the base64 SASL
payload is a transformed credential and must not be exposed on the assumption
that forge secret masking will recognize it.

On success stdout contains only `submitted IRC announcement`.
