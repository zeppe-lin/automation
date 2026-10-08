"""Provider-neutral Git push collection."""

from .common import CONTROL_RE, validate_repository
from .gitrepo import GitRepository


def _clean_url(value, name):
    if value is None:
        return None
    if not isinstance(value, str) or CONTROL_RE.search(value) or "\r" in value or "\n" in value:
        raise ValueError(f"invalid {name}")
    if value and not value.startswith(("https://", "http://")):
        raise ValueError(f"invalid {name}")
    return value


def validate_envelope(envelope, repo):
    if envelope.get("schema") != 1 or envelope.get("event") != "push":
        raise ValueError("unsupported push envelope")
    repository = envelope.get("repository")
    validate_repository(repository)

    ref = envelope.get("ref")
    if not isinstance(ref, str) or not (
        ref.startswith("refs/heads/") or ref.startswith("refs/tags/")
    ):
        raise ValueError(f"unsupported push ref: {ref}")
    repo.validate_ref(ref)

    before = repo.validate_oid(str(envelope.get("before", "")), allow_zero=True)
    after = repo.validate_oid(str(envelope.get("after", "")), allow_zero=True)
    if before == repo.zero_oid and after == repo.zero_oid:
        raise ValueError("push cannot create and delete the same ref")

    repository_url = _clean_url(envelope.get("repository_url"), "repository URL")
    compare_url = _clean_url(envelope.get("compare_url"), "compare URL")
    return repository, ref, before, after, repository_url, compare_url


def collect_push(repository_path, envelope):
    repo = GitRepository(repository_path)
    repository, ref, before, after, repository_url, compare_url = validate_envelope(
        envelope, repo
    )
    created = before == repo.zero_oid
    deleted = after == repo.zero_oid
    ref_kind = "branch" if ref.startswith("refs/heads/") else "tag"
    change = "create" if created else "delete" if deleted else "update"

    commits = []
    forced = False
    if ref_kind == "branch":
        if deleted:
            repo.require_object(before, commit=True)
            commit_oids = []
        elif created:
            repo.require_object(after, commit=True)
            commit_oids = repo.new_branch_commits(after, ref)
        else:
            repo.require_object(before, commit=True)
            repo.require_object(after, commit=True)
            forced = before != after and not repo.is_ancestor(before, after)
            commit_oids = [] if before == after else repo.rev_list(f"{before}..{after}")
        commits = [repo.commit(oid, repository_url) for oid in commit_oids]
    else:
        if not created:
            repo.require_object(before)
        if not deleted:
            repo.require_object(after)

    event_id = f"push:{repository}:{ref}:{before}:{after}"
    return {
        "schema": 1,
        "event": "push",
        "event_id": event_id,
        "repository": repository,
        "repository_url": repository_url,
        "ref": ref,
        "ref_kind": ref_kind,
        "change": change,
        "before": before,
        "after": after,
        "forced": forced,
        "compare_url": compare_url,
        "commits": commits,
        "commit_count": len(commits),
    }
