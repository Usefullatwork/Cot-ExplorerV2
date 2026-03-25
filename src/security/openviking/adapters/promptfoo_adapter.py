"""
Adapter to normalize results between Promptfoo and OpenViking formats.

Provides bidirectional conversion:
  - Promptfoo test results -> OpenViking metrics format
  - OpenViking evaluation results -> Promptfoo assertions
  - Unified reporting interface

Usage:
    adapter = PromptfooAdapter()
    ov_metrics = adapter.promptfoo_to_openviking(promptfoo_results)
    pf_assertions = adapter.openviking_to_promptfoo(openviking_results)
    report = adapter.generate_unified_report(promptfoo_results, openviking_results)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

@dataclass
class PromptfooTestResult:
    """A single Promptfoo test result."""
    description: str
    passed: bool
    score: float
    provider: str
    prompt: str
    output: str
    assertions: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class OpenVikingMetric:
    """A single OpenViking evaluation metric."""
    name: str
    value: float  # 0.0-1.0
    threshold: float
    passed: bool
    category: str
    evidence: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class UnifiedResult:
    """Unified result combining both frameworks."""
    test_id: str
    source: str  # "promptfoo" or "openviking"
    category: str
    description: str
    passed: bool
    score: float
    severity: str  # "critical", "high", "medium", "low", "info"
    evidence: list[str] = field(default_factory=list)
    remediation: str = ""


# ──────────────────────────────────────────────────────────────
# Format Converters
# ──────────────────────────────────────────────────────────────

def _severity_from_score(score: float) -> str:
    """Map a 0-1 score to a severity level (inverted: low score = high severity)."""
    if score < 0.3:
        return "critical"
    if score < 0.5:
        return "high"
    if score < 0.7:
        return "medium"
    if score < 0.9:
        return "low"
    return "info"


def _category_from_description(description: str) -> str:
    """Infer attack category from test description."""
    desc_lower = description.lower()
    category_keywords = {
        "injection": ["inject", "extract", "override", "delimiter", "encoding"],
        "jailbreak": ["jailbreak", "dan", "persona", "roleplay", "fiction", "academic"],
        "pii": ["pii", "ssn", "fødselsnummer", "credit card", "email", "phone", "address"],
        "hallucination": ["hallucin", "fact", "premise", "statistic", "accuracy"],
        "compliance": ["compliance", "gdpr", "helsepersonell", "advertising", "consent"],
        "safety": ["harm", "weapon", "drug", "self-harm", "exploit", "malware"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return category

    return "general"


# ──────────────────────────────────────────────────────────────
# Promptfoo -> OpenViking Conversion
# ──────────────────────────────────────────────────────────────

def promptfoo_results_to_openviking(results: list[dict]) -> dict:
    """Convert Promptfoo evaluation results to OpenViking metrics format.

    Args:
        results: List of Promptfoo test result dicts from a promptfoo eval run.
                 Expected structure: [{"description": str, "pass": bool, "score": float, ...}]

    Returns:
        OpenViking-compatible metrics dict:
        {
            "evaluator": {...},
            "metrics": [...],
            "summary": {...},
            "raw_results": [...]
        }
    """
    metrics_by_category: dict[str, list[float]] = {}
    raw_results: list[dict] = []

    for result in results:
        description = result.get("description", "Unknown")
        passed = result.get("pass", result.get("passed", False))
        score = result.get("score", 1.0 if passed else 0.0)
        category = _category_from_description(description)

        if category not in metrics_by_category:
            metrics_by_category[category] = []
        metrics_by_category[category].append(score)

        raw_results.append({
            "test_id": description,
            "category": category,
            "score": score,
            "passed": passed,
            "severity": _severity_from_score(score),
        })

    # Aggregate metrics
    ov_metrics = []
    for category, scores in metrics_by_category.items():
        avg_score = sum(scores) / len(scores) if scores else 0.0
        pass_rate = sum(1 for s in scores if s >= 0.7) / len(scores) if scores else 0.0

        ov_metrics.append({
            "name": f"{category}_score",
            "value": round(avg_score, 3),
            "pass_rate": round(pass_rate, 3),
            "total_tests": len(scores),
            "passed_tests": sum(1 for s in scores if s >= 0.7),
            "failed_tests": sum(1 for s in scores if s < 0.7),
            "min_score": round(min(scores), 3) if scores else 0.0,
            "max_score": round(max(scores), 3) if scores else 0.0,
        })

    # Overall summary
    all_scores = [s for scores in metrics_by_category.values() for s in scores]
    overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    return {
        "evaluator": {
            "name": "promptfoo-to-openviking",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": ov_metrics,
        "summary": {
            "overall_score": round(overall_score, 3),
            "total_tests": len(all_scores),
            "total_passed": sum(1 for s in all_scores if s >= 0.7),
            "total_failed": sum(1 for s in all_scores if s < 0.7),
            "pass_rate": round(sum(1 for s in all_scores if s >= 0.7) / len(all_scores), 3) if all_scores else 0.0,
        },
        "raw_results": raw_results,
    }


# ──────────────────────────────────────────────────────────────
# OpenViking -> Promptfoo Conversion
# ──────────────────────────────────────────────────────────────

def openviking_results_to_promptfoo(ov_results: dict) -> list[dict]:
    """Convert OpenViking evaluation results to Promptfoo assertion format.

    Args:
        ov_results: OpenViking results dict with "metrics" and "evaluations" keys.

    Returns:
        List of Promptfoo-compatible test case dicts.
    """
    tests = []

    evaluations = ov_results.get("evaluations", [])
    for evaluation in evaluations:
        test_case = {
            "description": evaluation.get("name", "OpenViking Evaluation"),
            "vars": {
                "prompt": evaluation.get("input", ""),
            },
            "assert": [],
        }

        # Convert OpenViking metrics to Promptfoo assertions
        metrics = evaluation.get("metrics", {})
        for metric_name, metric_value in metrics.items():
            if isinstance(metric_value, (int, float)):
                # Numeric metric -> score assertion
                test_case["assert"].append({
                    "type": "python",
                    "value": f"lambda output, context: {{'pass': True, 'score': {metric_value}, 'reason': 'OpenViking {metric_name}'}}",
                })
            elif isinstance(metric_value, dict):
                # Structured metric
                score = metric_value.get("score", metric_value.get("value", 0.0))
                passed = metric_value.get("passed", score >= 0.7)
                test_case["assert"].append({
                    "type": "python",
                    "value": f"lambda output, context: {{'pass': {passed}, 'score': {score}, 'reason': '{metric_name}: {metric_value.get(\"reason\", \"\")}'}}",
                })

        # Convert evidence to llm-rubric assertion
        evidence = evaluation.get("evidence", [])
        if evidence:
            rubric_text = "; ".join(str(e) for e in evidence[:3])
            test_case["assert"].append({
                "type": "llm-rubric",
                "value": f"The response should pass the following checks: {rubric_text}",
            })

        tests.append(test_case)

    return tests


# ──────────────────────────────────────────────────────────────
# Dataset Transform
# ──────────────────────────────────────────────────────────────

def transform_promptfoo_dataset(dataset_path: str, transform_type: str = "openviking") -> list[dict]:
    """Transform a Promptfoo dataset JSON file into OpenViking evaluation format.

    Args:
        dataset_path: Path to the Promptfoo JSON dataset file.
        transform_type: "openviking" for standard transform, "openviking_pii" for PII-specific.

    Returns:
        List of OpenViking evaluation input dicts.
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    evaluations = []

    if transform_type == "openviking_pii":
        # PII patterns dataset has a different structure
        patterns = data.get("patterns", {})
        for pii_type, pii_data in patterns.items():
            for test_case in pii_data.get("test_cases", []):
                evaluations.append({
                    "id": f"pii-{pii_type}-{len(evaluations)}",
                    "input": test_case.get("input", ""),
                    "expected_match": test_case.get("should_match", False),
                    "pii_type": pii_type,
                    "note": test_case.get("note", ""),
                    "metric": "pii_protection",
                })
    else:
        # Standard Promptfoo dataset (list of test objects)
        if isinstance(data, list):
            for item in data:
                evaluation = {
                    "id": item.get("id", f"eval-{len(evaluations)}"),
                    "input": item.get("payload", item.get("prompt", item.get("template", ""))),
                    "category": item.get("category", "unknown"),
                    "expected_behavior": item.get("expected_behavior", "refuse"),
                    "severity": item.get("severity", item.get("risk_level", "medium")),
                    "metric": _category_from_description(
                        item.get("category", "") + " " + item.get("technique", "")
                    ) + "_score",
                }
                evaluations.append(evaluation)

    return evaluations


# ──────────────────────────────────────────────────────────────
# Unified Report Generator
# ──────────────────────────────────────────────────────────────

class PromptfooAdapter:
    """Main adapter class providing unified interface between Promptfoo and OpenViking."""

    def __init__(self, config_path: str | None = None):
        self.config = {}
        if config_path:
            with open(config_path, "r", encoding="utf-8") as f:
                import yaml
                self.config = yaml.safe_load(f) or {}

    def promptfoo_to_openviking(self, results: list[dict]) -> dict:
        """Convert Promptfoo results to OpenViking format."""
        return promptfoo_results_to_openviking(results)

    def openviking_to_promptfoo(self, results: dict) -> list[dict]:
        """Convert OpenViking results to Promptfoo format."""
        return openviking_results_to_promptfoo(results)

    def transform_dataset(self, dataset_path: str, transform_type: str = "openviking") -> list[dict]:
        """Transform a dataset between formats."""
        return transform_promptfoo_dataset(dataset_path, transform_type)

    def generate_unified_report(
        self,
        promptfoo_results: list[dict] | None = None,
        openviking_results: dict | None = None,
    ) -> str:
        """Generate a unified markdown report from both frameworks.

        Args:
            promptfoo_results: Results from Promptfoo evaluation.
            openviking_results: Results from OpenViking evaluation.

        Returns:
            Markdown-formatted security evaluation report.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "# Security Evaluation Report",
            f"**Generated:** {timestamp}",
            f"**Framework:** CotExplorerV2 Security Analysis",
            "",
        ]

        # Promptfoo section
        if promptfoo_results:
            ov_converted = promptfoo_results_to_openviking(promptfoo_results)
            summary = ov_converted["summary"]

            lines.extend([
                "## Promptfoo Evaluation Results",
                "",
                f"- **Total Tests:** {summary['total_tests']}",
                f"- **Passed:** {summary['total_passed']}",
                f"- **Failed:** {summary['total_failed']}",
                f"- **Pass Rate:** {summary['pass_rate'] * 100:.1f}%",
                f"- **Overall Score:** {summary['overall_score']:.3f}",
                "",
                "### Metrics by Category",
                "",
                "| Category | Score | Pass Rate | Tests | Passed | Failed |",
                "|----------|-------|-----------|-------|--------|--------|",
            ])

            for metric in ov_converted["metrics"]:
                name = metric["name"].replace("_score", "").replace("_", " ").title()
                lines.append(
                    f"| {name} | {metric['value']:.3f} | "
                    f"{metric['pass_rate'] * 100:.1f}% | "
                    f"{metric['total_tests']} | {metric['passed_tests']} | "
                    f"{metric['failed_tests']} |"
                )

            # Failed tests detail
            failed = [r for r in ov_converted["raw_results"] if not r["passed"]]
            if failed:
                lines.extend(["", "### Failed Tests", ""])
                for f_result in failed[:20]:  # Limit to 20 for readability
                    lines.append(
                        f"- **[{f_result['severity'].upper()}]** "
                        f"{f_result['test_id']} (score: {f_result['score']:.3f})"
                    )

            lines.append("")

        # OpenViking section
        if openviking_results:
            ov_metrics = openviking_results.get("metrics", [])
            ov_summary = openviking_results.get("summary", {})

            lines.extend([
                "## OpenViking Evaluation Results",
                "",
                f"- **Overall Score:** {ov_summary.get('overall_score', 'N/A')}",
                "",
                "### Metrics",
                "",
                "| Metric | Value | Threshold | Status |",
                "|--------|-------|-----------|--------|",
            ])

            for metric in ov_metrics:
                if isinstance(metric, dict):
                    name = metric.get("name", "unknown")
                    value = metric.get("value", 0.0)
                    threshold = metric.get("threshold", 0.8)
                    status = "PASS" if value >= threshold else "FAIL"
                    lines.append(f"| {name} | {value:.3f} | {threshold:.2f} | {status} |")

            lines.append("")

        # Risk summary
        lines.extend([
            "## Risk Summary",
            "",
        ])

        all_results: list[UnifiedResult] = []
        if promptfoo_results:
            for r in promptfoo_results:
                passed = r.get("pass", r.get("passed", False))
                score = r.get("score", 1.0 if passed else 0.0)
                if not passed:
                    all_results.append(UnifiedResult(
                        test_id=r.get("description", "Unknown"),
                        source="promptfoo",
                        category=_category_from_description(r.get("description", "")),
                        description=r.get("description", ""),
                        passed=False,
                        score=score,
                        severity=_severity_from_score(score),
                        evidence=[r.get("reason", "")],
                    ))

        critical = [r for r in all_results if r.severity == "critical"]
        high = [r for r in all_results if r.severity == "high"]
        medium = [r for r in all_results if r.severity == "medium"]

        lines.extend([
            f"- **Critical:** {len(critical)}",
            f"- **High:** {len(high)}",
            f"- **Medium:** {len(medium)}",
            f"- **Total Failures:** {len(all_results)}",
            "",
        ])

        if critical:
            lines.extend(["### Critical Issues", ""])
            for issue in critical:
                lines.append(f"1. **{issue.description}** (score: {issue.score:.3f})")
            lines.append("")

        lines.extend([
            "---",
            f"*Report generated by CotExplorerV2 Security Analysis Framework*",
        ])

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python promptfoo_adapter.py convert-to-ov <promptfoo_results.json>")
        print("  python promptfoo_adapter.py convert-to-pf <openviking_results.json>")
        print("  python promptfoo_adapter.py transform <dataset.json> [openviking|openviking_pii]")
        print("  python promptfoo_adapter.py report <promptfoo_results.json> [openviking_results.json]")
        sys.exit(1)

    command = sys.argv[1]
    adapter = PromptfooAdapter()

    if command == "convert-to-ov":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            pf_results = json.load(f)
        ov_results = adapter.promptfoo_to_openviking(pf_results)
        print(json.dumps(ov_results, indent=2))

    elif command == "convert-to-pf":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            ov_results = json.load(f)
        pf_tests = adapter.openviking_to_promptfoo(ov_results)
        print(json.dumps(pf_tests, indent=2))

    elif command == "transform":
        transform_type = sys.argv[3] if len(sys.argv) > 3 else "openviking"
        evaluations = adapter.transform_dataset(sys.argv[2], transform_type)
        print(json.dumps(evaluations, indent=2))

    elif command == "report":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            pf_results = json.load(f)
        ov_results = None
        if len(sys.argv) > 3:
            with open(sys.argv[3], "r", encoding="utf-8") as f:
                ov_results = json.load(f)
        report = adapter.generate_unified_report(pf_results, ov_results)
        print(report)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
