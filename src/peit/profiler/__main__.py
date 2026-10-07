"""CLI entry point for peit.profiler when executed as a module: python -m peit.profiler."""

from __future__ import annotations

import sys
from peit.profiler.cli import main

if __name__ == "__main__":
    sys.exit(main())
