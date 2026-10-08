# Push event pipeline

The generic push pipeline is local code. It does not consume a GitHub webhook
object directly and it does not trust a provider's bounded commit list as
repository history.

A forge adapter has one job: translate provider event coordinates into the
small envelope described here and make the referenced Git objects available
locally.

## Input envelope

Schema 1 is:

```json
{
  "schema": 1,
  "event": "push",
  "repository": "zeppe-lin/example",
  "repository_url": "https://github.com/zeppe-lin/example",
  "ref": "refs/heads/master",
  "before": "<object-id>",
  "after": "<object-id>",
  "compare_url": "https://example.invalid/compare/..."
}
```

`repository_url` and `compare_url` are presentation metadata. Git owns the
repository-history facts.

For creation and deletion, the absent side uses Git's all-zero object ID with
the object length used by the local repository.

## Git authority

For a normal branch update the collector enumerates:

```text
before..after
```

with topological oldest-first ordering. It derives force-push state with
`merge-base --is-ancestor`; a provider's `forced` boolean is therefore not an
authority input.

For a new branch, the collector emits commits reachable from the new tip but
not reachable from the repository's other branch or tag refs. Creating an
alias branch at an already-known commit therefore emits zero commits rather
than replaying history.

A branch deletion records the ref transition and emits no historical commits.

Tag creation, update, and deletion are represented explicitly but do not replay
pointed-to commit history. Published releases have their own release-event
pipeline.

The collector requires every object needed to interpret the transition. A
shallow or incomplete checkout that lacks the required pre-push commit fails
closed instead of reconstructing history from webhook fields.

## Commit records

Each collected commit contains:

```text
sha
short_sha
parents
title
body
author_name
author_email
authored_at
trailers
diffstat
commit_url
```

Trailers are parsed by `git interpret-trailers`, not by a second approximation
of Git's trailer grammar.

Commit text is always data. It is never interpolated into shell source or forge
workflow expressions.

## Classification

Automation currently enforces only Codebook rules that are normative and
mechanically unambiguous:

* maintained event tags are `news`, `security`, `breaking`, and `deprecation`;
* maintained tags use lowercase spelling;
* cumulative tags use Codebook order;
* duplicate maintained tags are invalid;
* `[breaking]` requires `[news]`;
* new `[notify]` commits are invalid;
* ordinary commits route to development mail and IRC;
* maintained tagged commits additionally route to user mail;
* `[news]` creates a system-news requirement;
* `[breaking]` creates a release-note review requirement.

The classifier deliberately does **not** declare arbitrary human bracket
prefixes such as `[RFC]` invalid. The Codebook has not established unknown
bracket-prefix policy precisely enough for automation to invent one.

Likewise, automation records the recognized trailers:

```text
Affected:
Action:
News:
Migration:
Release-Note:
Reference:
```

but does not yet enforce their exact per-tag cardinality or durable path rules.
Those rules remain coupled to `zeppe-lin/codebook#1`. A renderer or workflow
must not turn incomplete doctrine into accidental policy.

## Rendered dry-run state

`prepare-push.py` creates one directory containing all projections required for
review before external effects:

```text
manifest.json
delivery-plan.json
requirements.json
mail-dev/
mail-user/
irc.txt
```

Development mail preserves commit order and includes the complete commit
message, author, diffstat, and durable commit URL.

User mail is a distinct renderer. Structured `Affected`, `Action`, news,
migration, release-note, and reference trailers are presented before narrative
detail when available. It is not a development diffstat with a different
recipient.

IRC emits one bounded UTF-8 summary per push. It identifies maintained event
classes, force-push state, a bounded subset of commit summaries, omitted-count
information, and one durable URL.

No renderer performs transport I/O.

`delivery-plan.json` is the admitted bridge to the delivery controller. It
preserves per-destination order and binds each external effect to its event,
commit or push item, and renderer template version. See `push-delivery.md`.

## Current boundary

The local provider-neutral path now continues through Git-backed delivery state
and the real SMTP/IRC transports. Development and user mail are submitted
sequentially per destination; unresolved effects stop later messages until an
operator explicitly replays them. IRC remains one bounded push-level effect.

The remaining boundary is the forge: there is still no GitHub push-event
adapter or push-delivery workflow. Exact durable-artifact validation also
remains coupled to unfinished Codebook doctrine.

That is a boundary, not missing YAML.
