"""Validate Pine Script v5 syntax for all .pine files in src/pine/.

Checks:
1. //@version=5 header present
2. indicator() or strategy() declaration present
3. Balanced brackets/parentheses
4. No Pine v4 deprecated syntax (study())

Generates src/pine/VALIDATION.md with per-file results.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def find_pine_files(root: Path) -> list[Path]:
    """Find all .pine files recursively under root."""
    return sorted(root.rglob("*.pine"))


def validate_file(path: Path) -> dict:
    """Validate a single Pine Script file. Returns {name, path, checks, passed, issues}."""
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    issues: list[str] = []
    checks_passed = 0
    total_checks = 4

    # 1. Version header
    has_version = any("//@version=5" in line for line in lines[:10])
    if has_version:
        checks_passed += 1
    else:
        issues.append("Missing //@version=5 header in first 5 lines")

    # 2. indicator() or strategy() declaration
    has_decl = bool(re.search(r'\b(indicator|strategy)\s*\(', content))
    if has_decl:
        checks_passed += 1
    else:
        issues.append("No indicator() or strategy() declaration found")

    # 3. Balanced brackets
    brackets = {"(": 0, "[": 0, "{": 0}
    closers = {")": "(", "]": "[", "}": "{"}
    for char in content:
        if char in brackets:
            brackets[char] += 1
        elif char in closers:
            brackets[closers[char]] -= 1

    balanced = all(v == 0 for v in brackets.values())
    if balanced:
        checks_passed += 1
    else:
        unbalanced = [f"{k}={v}" for k, v in brackets.items() if v != 0]
        issues.append(f"Unbalanced brackets: {', '.join(unbalanced)}")

    # 4. No deprecated v4 syntax
    has_study = bool(re.search(r'\bstudy\s*\(', content))
    if not has_study:
        checks_passed += 1
    else:
        issues.append("Deprecated Pine v4 study() found — use indicator() instead")

    return {
        "name": path.name,
        "path": str(path.relative_to(path.parent.parent.parent)),
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "passed": checks_passed == total_checks,
        "issues": issues,
    }


def generate_report(results: list[dict], output_path: Path) -> str:
    """Generate VALIDATION.md report."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    lines = [
        "# Pine Script v5 Validation Report",
        "",
        f"**Total**: {total} files | **Passed**: {passed} | **Failed**: {failed}",
        "",
        "| File | Path | Checks | Status |",
        "|------|------|--------|--------|",
    ]

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(
            f"| {r['name']} | {r['path']} | {r['checks_passed']}/{r['total_checks']} | {status} |"
        )

    if failed > 0:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for r in results:
            if r["issues"]:
                lines.append(f"### {r['name']}")
                for issue in r["issues"]:
                    lines.append(f"- {issue}")
                lines.append("")

    report = "\n".join(lines) + "\n"
    output_path.write_text(report, encoding="utf-8")
    return report


def main():
    project_root = Path(__file__).resolve().parent.parent
    pine_root = project_root / "src" / "pine"

    if not pine_root.exists():
        log.error("Pine root not found: %s", pine_root)
        sys.exit(1)

    pine_files = find_pine_files(pine_root)
    if not pine_files:
        log.error("No .pine files found")
        sys.exit(1)

    log.info("Validating %d Pine Script files...", len(pine_files))

    results = [validate_file(f) for f in pine_files]

    # Log summary
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        log.info("[%s] %s (%d/%d)", status, r["name"], r["checks_passed"], r["total_checks"])
        for issue in r["issues"]:
            log.warning("  - %s", issue)

    output_path = pine_root / "VALIDATION.md"
    generate_report(results, output_path)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    log.info("%d/%d files passed. Report: %s", passed, total, output_path)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
