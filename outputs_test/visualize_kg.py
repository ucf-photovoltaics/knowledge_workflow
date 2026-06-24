#!/usr/bin/env python3
"""
Thin shim — the visualizer now lives in the package as kw.visualize so the pipeline
and ad-hoc runs share one implementation. This file just forwards to it.

    python outputs_test/visualize_kg.py --glob "*/all.jsonld" --out kg_combined.html
    # equivalent to:  python -m kw.visualize --glob "..." --out ...
"""
import os
import sys

# make the repo root importable when run directly from outputs_test/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kw.visualize import main  # noqa: E402

if __name__ == "__main__":
    main()
