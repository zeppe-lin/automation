"""Real Git repository fixture used by behavioral integration tests."""

import subprocess
from pathlib import Path


class GitFixture:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.run("init", "-q", "-b", "master")
        self.run("config", "user.name", "Automation Test")
        self.run("config", "user.email", "automation@example.invalid")
        self.run("config", "commit.gpgsign", "false")
        self.counter = 0

    def run(self, *args, check=True, input_text=None):
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            input=input_text,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"git {' '.join(args)} failed ({result.returncode}): {result.stderr}"
            )
        return result

    def commit(self, message, filename=None, content=None):
        self.counter += 1
        filename = filename or f"file-{self.counter}.txt"
        target = self.path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content if content is not None else f"{self.counter}\n", encoding="utf-8")
        self.run("add", filename)
        self.run("commit", "-q", "--file=-", input_text=message.rstrip("\n") + "\n")
        return self.oid()

    def oid(self, revision="HEAD"):
        return self.run("rev-parse", revision).stdout.strip()

    def checkout(self, *args):
        self.run("checkout", "-q", *args)

    def branch(self, name, start="HEAD"):
        self.run("branch", name, start)

    def delete_branch(self, name):
        self.run("branch", "-D", name)

    def reset_hard(self, revision):
        self.run("reset", "--hard", "-q", revision)

    def tag(self, name, annotated=False):
        if annotated:
            self.run("tag", "-a", name, "-m", name)
        else:
            self.run("tag", name)
        return self.oid(f"refs/tags/{name}")
