#!/usr/bin/env python3
"""Backward-compatible launcher for source checkouts.

The implementation now lives in the ``src/netblackbox`` package. Install the
project with ``python3 -m pip install .`` or set ``PYTHONPATH=src``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from nbb.__main__ import main  # noqa: E402

SOURCE_ROOT = Path(__file__).resolve().parent / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

if __name__ == "__main__":
    main()
