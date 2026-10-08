#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation.commands.deliver_push import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
