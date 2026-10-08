# Automation issue #1 implementation status

Issue #1 defines the migration from ad hoc GitHub notification workflows to an
event-aware delivery pipeline. The implementation now contains two deliberately
different maturity levels:

* published-release events have a central delivery path;
* generic Git push events have a locally qualified collect/classify/route/render
  path, but no production forge adapter or external delivery yet.

This document records implementation state. It does not replace the issue or
the Codebook.

## Implemented for release events

The release vertical slice implements:

| Requirement | Release-event status |
| --- | --- |
| Treat external fields as data | Implemented |
| Deterministic normalized manifest | Implemented |
| Separate user-mail, development-mail, and IRC renderers | Implemented |
| Bounded single-line IRC output | Implemented |
| Central cross-repository queue | Implemented by automation workflow concurrency |
| Secret-bearing transport isolated from source repositories | Implemented |
| Direct SMTP and IRC transports without marketplace transport actions | Implemented |
| Attempt-before-effect and delivered-after-effect evidence | Implemented with Git refs |
| Refuse automatic replay of uncertain effects | Implemented |
| Explicit operator replay | Implemented |
| Dry-run rendered artifact | Implemented |
| Immutable third-party action pins | Enforced by local tests |
| Local behavioral transport tests | Implemented with loopback TLS SMTP and IRC/SASL |
| Credential-safe diagnostics | Implemented for current SMTP/IRC clients |

## Implemented locally for push events

The generic push path now implements and locally qualifies:

```text
push envelope
    |
    v
local Git observation
    |
    v
normalized push manifest
    |
    v
Codebook tag classification
    |
    v
routing + durable-requirement projection
    |
    +--> ordered development-mail files
    +--> semantic user-mail files
    `--> bounded IRC summary
```

Concrete behavior includes:

* full `before..after` commit enumeration from Git, not `github.event.commits`;
* topological oldest-first ordering;
* branch creation without replaying history shared by existing refs;
* branch deletion and empty-range representation;
* force-push detection from the Git graph;
* explicit tag create/delete representation without replaying pointed history;
* arbitrarily large local commit ranges;
* merge and revert commit preservation;
* UTF-8 and shell-looking commit text treated only as data;
* Git-native trailer parsing through `git interpret-trailers`;
* exact lowercase maintained tags and canonical tag ordering;
* rejection of new `[notify]` commits;
* enforcement that `[breaking]` is combined with `[news]`;
* current Codebook routing to development mail, user mail, IRC, system-news
  review, and release-note review;
* separate deterministic renderers for development mail, user mail, and IRC;
* explicit `requirements.json` for durable-artifact review;
* fail-closed behavior when required pre-push Git objects are unavailable.

All of this runs under `make check` without GitHub, Internet access, or
production credentials.

## Still open for issue #1

The following remain real implementation work:

* GitHub push-event adapter from `$GITHUB_EVENT_PATH` into the provider-neutral
  envelope;
* generic delivery identity and state for push/commit destinations;
* sequential external development-mail delivery in commit order;
* generic user-mail and IRC delivery through the central queue;
* bounded retry policy for transport failures distinct from uncertain effects;
* operator replay spanning generic events;
* exact trailer cardinality and required-trailer rules once Codebook doctrine is
  normative enough to enforce;
* durable `News:` and `Migration:` path validation;
* exact release-note decision validation;
* policy for arbitrary unknown leading bracket prefixes;
* provider semantics for ref classes outside branches and tags;
* migration of callers from `.github-shared-workflows`;
* retirement of `notify-irc.yml`, `notify-mail-dev.yml`, and
  `notify-mail-tag.yml`.

## Codebook dependency

The Codebook already gives automation enough authority to enforce maintained
tag names, ordering, `[breaking]`/`[news]`, `[notify]` retirement, and the broad
routing matrix.

It does not yet define every trailer cardinality, durable-reference rule, or
unknown-prefix diagnostic precisely enough for code to choose on its behalf.
Automation therefore exposes those requirements but does not manufacture a
stricter constitution inside this repository.

There is also historical `[notify]` language elsewhere in the current Codebook.
That is doctrine drift to resolve in the Codebook; automation follows the newer
normative Event Classification and Routing section for new commits.

## Next tranche

The next tranche should stay local-first:

```text
1. define generic delivery identity for push and commit destinations
2. feed rendered dev-mail files sequentially through loopback SMTP
3. feed the bounded push IRC artifact through loopback IRC/SASL
4. prove replay and uncertain-effect semantics for generic events
5. add durable-artifact validators only where Codebook rules are exact
6. only then add the GitHub push adapter
```

The GitHub workflow should be the last and least interesting part.
