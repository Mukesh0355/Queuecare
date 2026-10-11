"""
One-shot setup for the QueueCare prototype.

    python run_all.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(args):
    print("\n>", " ".join(args))
    subprocess.check_call(args, cwd=ROOT)


def main():
    py = sys.executable
    version = sys.version_info
    if version < (3, 10) or version >= (3, 14):
        print(
            f"Warning: this prototype is tested on Python 3.10–3.12. "
            f"You are on {version.major}.{version.minor}. "
            "If installs fail, create a 3.11 venv: py -3.11 -m venv .venv"
        )
    run([py, "-m", "pip", "install", "-r", "requirements.txt"])
    run([py, str(ROOT / "model" / "generate_data.py")])
    run([py, str(ROOT / "model" / "train.py")])
    run([py, "-m", "streamlit", "run", str(ROOT / "app.py")])


if __name__ == "__main__":
    main()
