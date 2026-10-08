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

## `collect-push.py`

```text
collect-push.py GIT-REPOSITORY EVENT.json OUTPUT.json
```

Observe one provider-neutral push envelope against a local Git repository and
write a schema-1 push manifest. Commit enumeration, ancestry, merge topology,
commit messages, trailers, and diffstats come from Git rather than a webhook's
bounded commit list.

The command performs no network access. A missing `before` or `after` object
that is required to interpret the push is a hard error; callers must provide a
repository with sufficient history.

## `prepare-push.py`

```text
prepare-push.py GIT-REPOSITORY EVENT.json OUTPUT-DIR
```

Run the local push pipeline through collection, Codebook classification,
routing, and deterministic rendering. The output directory contains:

```text
manifest.json
delivery-plan.json
requirements.json
mail-dev/NNNN.json
mail-user/NNNN.json
irc.txt                 when the push contains routed commits
```

No external delivery is performed. `delivery-plan.json` binds the rendered
artifacts to their event, item, destination, and template identities.

## `deliver-push.py`

```text
deliver-push.py DELIVERY-DIR mail-user|mail-dev|irc [--force]
```

Validate and execute one prepared push destination. Mail is submitted one
commit at a time in delivery-plan order. Every item is claimed in the Git
ledger before transport and marked delivered only after the transport returns
success. An unresolved attempt stops the sequence before later items.

`AUTOMATION_FORCE_REPLAY=true` is equivalent to `--force`. The same
`AUTOMATION_STATE_*` environment contract documented for `delivery-state.py`
applies. Mail and IRC use the transport-specific variables documented below.

## `render-push.py`

```text
render-push.py MANIFEST.json OUTPUT-DIR
```

Render an already-classified push manifest without repository or network I/O.
Development mail is one file per commit in commit order. User mail exists only
for commits whose Codebook classification routes to the user audience. IRC is
a bounded UTF-8 push summary. `requirements.json` exposes durable system-news
and release-note review requirements without pretending to validate doctrine
that the Codebook has not specified precisely enough yet.

## `queue-github-push.py`

```text
queue-github-push.py GITHUB-EVENT.json [--automation-repository OWNER/NAME]
```

Normalize one GitHub push event and send a `push-observed`
`repository_dispatch` to the central automation repository. `GH_TOKEN` is
required in the environment.

Only the provider-neutral repository/ref/object coordinates are dispatched.
GitHub `commits`, `head_commit`, and `forced` fields are not forwarded.

## `prepare-github-push.py`

```text
prepare-github-push.py DISPATCH.json GIT-REPOSITORY OUTPUT-DIR [--remote URL]
```

Decode one central `push-observed` dispatch, materialize the required Git state
into a new bare repository, and run the ordinary provider-neutral push pipeline.

Without `--remote`, the source remote is derived from the validated Zeppe-Lin
repository identity on `github.com`. `--remote` exists for local qualification
against disposable remotes; it is not needed by the production workflow.

The command checks out no source files and accepts no transport credentials.
