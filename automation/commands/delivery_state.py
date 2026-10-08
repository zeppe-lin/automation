import sys

from automation import gitstate
from ._util import error


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 4:
        print(
            f"usage: {sys.argv[0]} claim|delivered REPOSITORY TAG DESTINATION [--force]",
            file=sys.stderr,
        )
        return 2
    command, repository, tag, destination = argv[:4]
    force = argv[4:] == ["--force"]
    if argv[4:] and not force:
        return error("unsupported argument")
    try:
        if command == "claim":
            status, message = gitstate.claim(repository, tag, destination, force)
        elif command == "delivered":
            if force:
                return error("--force is valid only with claim")
            status, message = gitstate.mark_delivered(repository, tag, destination)
        else:
            print(f"error: unsupported command: {command}", file=sys.stderr)
            return 2
    except (OSError, ValueError) as exc:
        return error(exc)
    stream = sys.stderr if status == gitstate.UNRESOLVED_ATTEMPT else sys.stdout
    print(("error: " if status == gitstate.UNRESOLVED_ATTEMPT else "") + message, file=stream)
    return status
