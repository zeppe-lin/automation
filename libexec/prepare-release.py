#!/usr/bin/env python3
"""Thin command adapter; implementation lives in :mod:`automation`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.commands.prepare_release import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
