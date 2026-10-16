"""Launch locally: python -m dpv_dashboard [--port 8056] [--viewer] [--host 0.0.0.0].

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import argparse
import os
import tempfile
import subprocess
import sys
from dpv_dashboard.model import DATA, ROOT


def main():
    parser = argparse.ArgumentParser(description="UCF DPV Knowledge Workflow")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8056)))
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to serve beyond this computer (e.g. in a container)")
    parser.add_argument("--viewer", action="store_true", help="read-only: explore saved results; no projects, runs or saved settings")
    args = parser.parse_args()
    if args.viewer:
        os.environ["DPV_VIEWER"] = "1"
    temporary = DATA / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temporary)
    tempfile.tempdir = str(temporary)
    # Direct module launches receive the same safe documentation bundle as the PS launcher.
    if not (ROOT / 'outputs/development/codebase-docs/webvowl/library.html').is_file():
        subprocess.run([sys.executable, str(ROOT / 'scripts/documentation_library.py')], check=not os.environ.get("DPV_VIEWER"))
    import uvicorn
    uvicorn.run("dpv_dashboard.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
