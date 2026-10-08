# Push delivery

Push delivery consumes only artifacts produced by the local push pipeline. It
never reconstructs routing from filenames, webhook fields, or transport state.

```text
Git history + push envelope
          |
          v
     prepare-push
          |
          v
 manifest.json
 delivery-plan.json
 mail-dev/*.json
 mail-user/*.json
 irc.txt
          |
          v
     deliver-push
          |
          +--> Git evidence
          `--> one transport effect at a time
```

The provider-neutral engine therefore remains usable without GitHub Actions.
The future forge workflow is responsible only for supplying a complete Git
repository, carrying the prepared artifact between isolation boundaries,
exposing destination credentials, and invoking the same local delivery command.

## Delivery plan

`delivery-plan.json` is the binding contract between deterministic rendering
and external effects. Each entry records:

```text
artifact
normalized event ID
item ID
template version
```

Development and user mail use the commit object ID as the item ID. IRC uses the
push-level item ID `push` because a push has at most one IRC summary.

The plan is ordered. Development mail follows the oldest-first commit order
observed from Git. User mail preserves that same relative order after commits
not routed to the user audience are omitted.

Before any claim is written, the delivery controller verifies that:

* the plan and manifest describe the same repository and event;
* every artifact remains inside the prepared directory;
* an artifact's event, item, destination, and template identity match the plan;
* duplicate delivery identities are absent;
* the selected route is an ordered list.

An artifact is therefore data selected by an admitted plan, not an arbitrary
path supplied to a secret-bearing transport job.

## Delivery identity

One push effect is identified by:

```text
source repository
event ID
destination
item ID
renderer template version
```

The corresponding Git namespace is:

```text
refs/automation/delivery/push/
    <owner>/<repository>/
    <sha256(event-id)>/
    <destination>/
    <item-id>/
    template-<version>/
```

The full event digest is used because provider-neutral event IDs contain ref
names and punctuation that must not become Git-ref syntax. The digest is a
deterministic representation, not a new source of event truth; it is always
recomputed from `manifest.json`.

An attempt is recorded before transport I/O:

```text
.../attempts/<run-id>-<run-attempt>
```

A successful transport return is recorded as:

```text
.../delivered
```

The refs record controller knowledge. They do not claim that SMTP storage,
mailing-list expansion, or IRC readership can be observed perfectly from the
client.

## Sequential mail

`deliver-push.py DELIVERY-DIR mail-dev` processes development messages one at
a time in plan order:

```text
claim commit 1
submit commit 1
mark commit 1 delivered
claim commit 2
submit commit 2
mark commit 2 delivered
...
```

The same rule applies to `mail-user` after routing has selected its commits.
There is no matrix fan-out and no parallel mail submission inside a
destination.

If a transport attempt becomes uncertain, processing stops immediately. Later
commits are not claimed and cannot overtake the unresolved predecessor.

A later ordinary invocation skips already delivered predecessors and stops at
the unresolved item. `--force` is an explicit operator decision to replay that
item; after it succeeds, later items continue in their original order.

## IRC

`deliver-push.py DELIVERY-DIR irc` submits the single bounded IRC summary
created by the renderer. It uses the same claim-before-effect and
delivered-after-return protocol as mail.

IRC has no application-level acknowledgement for a `PRIVMSG`. A connection
failure around submission can therefore be ambiguous. Automation does not
pretend otherwise and does not automatically resend an unresolved IRC effect.

## Retries

There is deliberately no generic transport retry loop yet.

A timeout or connection loss may occur after an SMTP server accepted DATA or
after an IRC server accepted a `PRIVMSG`. Blind exponential retry would turn an
unknown effect into a probable duplicate.

Issue #1 still requires a bounded retry policy. That policy must distinguish a
failure proven to occur before an external effect from an uncertain failure.
Until such a distinction is implemented and behaviorally qualified, uncertain
effects require explicit replay.

## Local qualification

The push-delivery integration suite uses:

* disposable real Git histories;
* a real Git-backed delivery ledger;
* a local bare Git remote for cross-workspace evidence;
* a verified loopback TLS SMTP server;
* a verified loopback TLS/SASL IRC server;
* synthetic credentials only.

One behavioral test deliberately closes SMTP after receiving the second
message's DATA but before acknowledging it. The suite verifies that the first
message is durable as delivered, the second remains an unresolved attempt, the
third is never claimed, a normal rerun refuses to continue, and an explicit
replay resumes from the second item without resending the first.

No GitHub server, public SMTP service, IRC network, or production credential is
needed to qualify that state machine.
