"""Read-only observations of a local Git repository.

Provider adapters supply event coordinates. Git remains authority for commit
reachability, history order, commit metadata, and trailers.
"""

import os
import re
import subprocess
from pathlib import Path

OID_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")


class GitRepository:
    def __init__(self, path):
        self.path = Path(path)
        result = self.run("rev-parse", "--git-dir", check=False)
        if result.returncode != 0:
            raise ValueError(f"not a Git repository: {self.path}")

    def run(self, *args, check=True, input_text=None):
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
            env=env,
        )
        if check and result.returncode != 0:
            raise ValueError("Git repository observation failed")
        return result

    @property
    def object_format(self):
        return self.run("rev-parse", "--show-object-format").stdout.strip()

    @property
    def oid_length(self):
        return 64 if self.object_format == "sha256" else 40

    @property
    def zero_oid(self):
        return "0" * self.oid_length

    def validate_oid(self, oid, allow_zero=False):
        if not OID_RE.fullmatch(oid) or len(oid) != self.oid_length:
            raise ValueError(f"invalid Git object id: {oid}")
        if set(oid) == {"0"}:
            if allow_zero:
                return oid.lower()
            raise ValueError("zero Git object id is not an object")
        return oid.lower()


    def validate_ref(self, ref):
        result = self.run("check-ref-format", ref, check=False)
        if result.returncode != 0:
            raise ValueError(f"invalid Git ref: {ref}")
        return ref

    def object_exists(self, oid, commit=False):
        suffix = "^{commit}" if commit else "^{object}"
        return self.run("cat-file", "-e", oid + suffix, check=False).returncode == 0

    def require_object(self, oid, commit=False):
        self.validate_oid(oid)
        if not self.object_exists(oid, commit=commit):
            kind = "commit" if commit else "object"
            raise ValueError(f"Git {kind} is unavailable locally: {oid}")

    def is_ancestor(self, older, newer):
        result = self.run("merge-base", "--is-ancestor", older, newer, check=False)
        if result.returncode == 0:
            return True
        if result.returncode == 1:
            return False
        raise ValueError("cannot determine Git ancestry")

    def rev_list(self, *revisions):
        if not revisions:
            return []
        result = self.run("rev-list", "--topo-order", "--reverse", *revisions)
        return [line for line in result.stdout.splitlines() if line]

    def other_ref_objects(self, excluded_ref):
        result = self.run(
            "for-each-ref",
            "--format=%(refname)%00%(objectname)",
            "refs/heads",
            "refs/remotes",
            "refs/tags",
        )
        branch_name = (
            excluded_ref[len("refs/heads/") :]
            if excluded_ref.startswith("refs/heads/")
            else None
        )
        objects = []
        for line in result.stdout.splitlines():
            ref, separator, oid = line.partition("\0")
            if not separator or not oid or ref == excluded_ref:
                continue
            if branch_name is not None and ref.startswith("refs/remotes/"):
                remote_path = ref[len("refs/remotes/") :]
                _, slash, remote_branch = remote_path.partition("/")
                if slash and remote_branch == branch_name:
                    # A normal clone may expose the pushed branch only through a
                    # remote-tracking ref. It represents the target ref, not an
                    # independently pre-existing reachability boundary.
                    continue
            objects.append(oid)
        return objects

    def new_branch_commits(self, tip, ref):
        others = self.other_ref_objects(ref)
        if not others:
            return self.rev_list(tip)
        return self.rev_list(tip, "--not", *others)

    def trailers(self, message):
        result = self.run(
            "-c", "trailer.separators=:",
            "interpret-trailers", "--parse",
            input_text=message,
        )
        trailers = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            trailers.setdefault(key.strip(), []).append(value.strip())
        return trailers

    def commit(self, oid, repository_url=None):
        self.require_object(oid, commit=True)
        fields = self.run(
            "show", "-s",
            "--format=%H%x00%P%x00%an%x00%ae%x00%aI%x00%s%x00%b",
            oid,
        ).stdout.rstrip("\n").split("\0", 6)
        if len(fields) != 7:
            raise ValueError(f"cannot parse Git commit: {oid}")
        sha, parents, author_name, author_email, authored_at, title, body = fields
        short_sha = sha[:12]
        message = title + ("\n\n" + body.rstrip("\n") if body.strip() else "") + "\n"
        diffstat = self.run(
            "show", "--no-color", "--no-ext-diff", "--stat=80,60",
            "--no-renames", "--format=", sha,
        ).stdout.rstrip("\n")
        return {
            "sha": sha,
            "short_sha": short_sha,
            "parents": parents.split() if parents else [],
            "title": title,
            "body": body.rstrip("\n"),
            "author_name": author_name,
            "author_email": author_email,
            "authored_at": authored_at,
            "trailers": self.trailers(message),
            "diffstat": diffstat,
            "commit_url": f"{repository_url.rstrip('/')}/commit/{sha}" if repository_url else None,
        }
