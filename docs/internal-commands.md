# Internal command contracts

The commands under `libexec/` are executable boundaries of Zeppe-Lin
Automation. They use the Python standard library plus ordinary system tools
where documented. GitHub Actions invokes these commands; the workflow files do
not own their semantics.

Common rules:

* structured or durable data is written to files rather than workflow outputs;
* credentials are supplied only through environment variables;
* credentials are never accepted as command-line arguments;
* stdout contains bounded operational state, never protocol transcripts;
* stderr contains bounded diagnostics, never credentials or transformed
  credentials;
* no command requires GitHub Actions merely to be exercised;
* exit status `2` denotes command-line misuse unless documented otherwise.

## `extract-news.py`

```text
extract-news.py TAG NEWS OUTPUT
```

Extract exactly one level-two NEWS section matching `TAG`. No network access or
credentials are used.

## `publish-github-release.py`

```text
publish-github-release.py TAG NOTES [--name NAME] [--prerelease]
```

Publish one GitHub Release using `gh`. Existing releases are left unchanged.
`GH_TOKEN` is required in the environment. `RELEASE_NAME` and
`RELEASE_PRERELEASE` are accepted as adapter defaults so composite actions do
not need shell option construction.

## `queue-release-delivery.py`

```text
queue-release-delivery.py REPOSITORY TAG
```

Send one `release-published` repository dispatch to the central automation
repository using `gh`. `GH_TOKEN` is required. The JSON payload is created as a
file and passed as data.

## `collect-github-release.py`

```text
collect-github-release.py REPOSITORY TAG OUTPUT [--release-json FILE]
```

Normalize one published GitHub Release into schema-1 JSON. Without
`--release-json`, the command re-fetches publication authority from GitHub and
may use `GITHUB_TOKEN` as an Authorization header. With `--release-json`, the
same normalization runs entirely offline against a fixture payload.

## `render-release.py`

```text
render-release.py MANIFEST OUTPUT-DIR
```

Render one normalized release into:

```text
manifest.json
mail-user.json
mail-dev.json
irc.txt
```

Rendering is deterministic, consumes no credentials, and performs no network
I/O.

## `prepare-release.py`

```text
prepare-release.py REPOSITORY TAG OUTPUT-DIR [--release-json FILE]
```

Compose collection and rendering as one locally executable preparation stage.
This is the command used by the central workflow.

## `delivery-state.py`

```text
delivery-state.py claim REPOSITORY TAG DESTINATION [--force]
delivery-state.py delivered REPOSITORY TAG DESTINATION
```

Maintain release-delivery evidence in ordinary Git refs.

Environment:

```text
AUTOMATION_STATE_REPOSITORY   local Git repository; defaults to .
AUTOMATION_STATE_REMOTE       optional remote to query and mirror refs to
AUTOMATION_STATE_SHA          object ID for new refs; defaults to local HEAD
AUTOMATION_RUN_ID             attempt identity; defaults to local
AUTOMATION_RUN_ATTEMPT        attempt sequence; defaults to 1
```

`claim` statuses:

```text
0     claim created; external effect may proceed
20    destination already delivered; external effect must not run
21    unresolved prior attempt; explicit replay is required
```

With no remote, all behavior is local. Production points the checked-out
automation repository at `origin`; the same transitions are then mirrored as
central durable refs.

## `deliver-release.py`

```text
deliver-release.py DELIVERY-DIR mail-user|mail-dev|irc [--force]
```

Own the complete destination transition:

```text
validate transport configuration
claim delivery state
perform exactly one external transport effect
record delivered state
```

`AUTOMATION_FORCE_REPLAY=true` is equivalent to `--force` and exists for the
thin workflow adapter. A configuration failure occurs before a claim is
written.

## `send-mail.py`

```text
send-mail.py MESSAGE.json
```

Submit one rendered message over verified TLS SMTP.

Environment:

```text
SMTP_HOST
SMTP_PORT             optional; defaults to 465
SMTP_SECURITY         ssl or starttls; defaults to ssl
SMTP_USERNAME         optional authentication identity
SMTP_PASSWORD         paired with SMTP_USERNAME
MAIL_FROM
MAIL_TO
AUTOMATION_CA_FILE    optional explicit CA file; primarily for local fixtures
```

There is no plaintext authenticated mode and no certificate-verification bypass.
Remote SMTP response text is reduced to bounded diagnostics before logging.

## `send-irc.py`

```text
send-irc.py MESSAGE.txt
```

Submit exactly one IRC `PRIVMSG` over verified TLS after SASL PLAIN
authentication.

Environment:

```text
IRC_HOST
IRC_PORT              optional; defaults to 6697
IRC_CHANNEL
IRC_NICK
IRC_USERNAME          optional; defaults to IRC_NICK
IRC_SASL_USERNAME     optional; defaults to IRC_NICK
IRC_SASL_PASSWORD
AUTOMATION_CA_FILE    optional explicit CA file; primarily for local fixtures
```

The client never logs IRC protocol traffic or the base64 SASL payload.
