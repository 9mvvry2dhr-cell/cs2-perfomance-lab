from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

VALIDATORS = (
    ("scoreboard", "validate_scoreboard_trust.py"),
    ("KAST", "validate_kast_trust.py"),
    ("trades", "validate_trade_trust.py"),
    ("entry", "validate_entry_trust.py"),
    ("survival", "validate_survival_trust.py"),
    ("clutches", "validate_clutch_trust.py"),
    ("multikill", "validate_multikill_trust.py"),
    ("utility", "validate_utility_trust.py"),
    ("CT/T splits", "validate_splits_trust.py"),
    ("cross-check batch", "validate_demo_batch.py"),
)


def last_result_line(output: str) -> str:
    for line in reversed(output.splitlines()):
        if line.startswith("RESULT:"):
            return line
    return "RESULT line missing"


def run_validator(label: str, script_name: str, demo_dir: Path) -> bool:
    script_path = SCRIPTS_DIR / script_name

    if not script_path.is_file():
        print(f"[FAIL] {label}: missing {script_name}")
        return False

    completed = subprocess.run(
        [sys.executable, str(script_path), str(demo_dir)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    result_line = last_result_line(stdout)

    if completed.returncode == 0:
        print(f"[PASS] {label:<18} {result_line}")
        return True

    print(
        f"[FAIL] {label:<18} "
        f"exit={completed.returncode} "
        f"{result_line}"
    )

    print()
    print(f"--- {script_name} stdout ---")
    print(stdout.rstrip() or "<empty>")

    if stderr.strip():
        print()
        print(f"--- {script_name} stderr ---")
        print(stderr.rstrip())

    print()
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete CS2 Performance Lab "
            "Data Trust validation suite."
        )
    )
    parser.add_argument(
        "demo_dir",
        type=Path,
        help="Directory containing .dem files",
    )
    args = parser.parse_args()

    demo_dir = args.demo_dir

    if not demo_dir.exists():
        print(f"Directory not found: {demo_dir}")
        return 2

    demo_count = len(list(demo_dir.glob("*.dem")))
    if demo_count == 0:
        print(f"No .dem files found in {demo_dir}")
        return 2

    print("CS2 PERFORMANCE LAB - DATA TRUST SUITE")
    print("=" * 72)
    print(f"Demos:      {demo_count}")
    print(f"Validators: {len(VALIDATORS)}")
    print()

    passed = 0

    for label, script_name in VALIDATORS:
        if run_validator(label, script_name, demo_dir):
            passed += 1

    failed = len(VALIDATORS) - passed

    print()
    print("=" * 72)
    print(
        "TRUST SUITE: "
        f"{passed} passed / "
        f"{failed} failed / "
        f"{len(VALIDATORS)} total"
    )

    if failed == 0:
        print("DATA TRUST: PASS")
        return 0

    print("DATA TRUST: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
