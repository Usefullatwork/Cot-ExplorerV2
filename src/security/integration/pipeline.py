"""
Security evaluation pipeline orchestrator for CotExplorerV2.

Coordinates the full security evaluation lifecycle:
  1. Run Promptfoo evaluations (red-team, injection, jailbreak, pii, etc.)
  2. Run OpenViking evaluations
  3. Run loophole scanner on prompt templates
  4. Run pattern detector on adversarial datasets
  5. Generate threat model
  6. Aggregate results into unified report

Usage:
    CLI:
        python pipeline.py --full                     # Run everything
        python pipeline.py --promptfoo                # Promptfoo only
        python pipeline.py --scan <directory>         # Scanner only
        python pipeline.py --patterns <dataset.json>  # Pattern detector only
        python pipeline.py --threat-model             # Threat model only
        python pipeline.py --report <results_dir>     # Report from existing results

    Python:
        pipeline = SecurityPipeline(config_dir="./promptfoo/configs")
        results = pipeline.run_full()
        pipeline.save_report(results, "./reports/security_report.md")
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent directories to path for imports
_SECURITY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SECURITY_DIR))

from analysis.loophole_scanner import LoopholeScanner
from analysis.pattern_detector import PatternDetector
from analysis.threat_modeler import ThreatModeler
from analysis.report_generator import ReportGenerator


@dataclass
class PipelineStage:
    """Result of a single pipeline stage."""
    name: str
    status: str  # "success", "failed", "skipped"
    duration_ms: float = 0.0
    result_count: int = 0
    error: str = ""
    data: Any = None


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    stages: list[PipelineStage] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    total_duration_ms: float = 0.0

    @property
    def all_passed(self) -> bool:
        return all(s.status in ("success", "skipped") for s in self.stages)

    @property
    def failed_stages(self) -> list[str]:
        return [s.name for s in self.stages if s.status == "failed"]


class SecurityPipeline:
    """Orchestrates the complete security evaluation pipeline."""

    def __init__(
        self,
        config_dir: str | None = None,
        dataset_dir: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        base = _SECURITY_DIR
        self.config_dir = Path(config_dir) if config_dir else base / "promptfoo" / "configs"
        self.dataset_dir = Path(dataset_dir) if dataset_dir else base / "promptfoo" / "datasets"
        self.output_dir = Path(output_dir) if output_dir else base / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.scanner = LoopholeScanner()
        self.pattern_detector = PatternDetector()
        self.threat_modeler = ThreatModeler()
        self.report_generator = ReportGenerator()

    # ── Stage 1: Promptfoo Evaluations ──

    def run_promptfoo(self, configs: list[str] | None = None) -> PipelineStage:
        """Run Promptfoo evaluations for specified configs.

        Args:
            configs: List of config file names (e.g., ["red-team.yaml", "injection.yaml"]).
                     If None, runs all YAML configs in config_dir.

        Returns:
            PipelineStage with evaluation results.
        """
        stage = PipelineStage(name="promptfoo")
        start = time.monotonic()

        if configs is None:
            configs = [f.name for f in self.config_dir.glob("*.yaml")]

        if not configs:
            stage.status = "skipped"
            stage.error = "No config files found"
            return stage

        all_results: list[dict] = []

        for config_name in configs:
            config_path = self.config_dir / config_name
            if not config_path.exists():
                print(f"  Warning: Config not found: {config_path}", file=sys.stderr)
                continue

            print(f"  Running Promptfoo: {config_name}...")

            try:
                result = subprocess.run(
                    ["npx", "promptfoo", "eval", "-c", str(config_path), "--output", "json"],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout per config
                    cwd=str(self.config_dir),
                )

                if result.returncode == 0:
                    try:
                        eval_data = json.loads(result.stdout)
                        results = eval_data.get("results", eval_data) if isinstance(eval_data, dict) else eval_data
                        if isinstance(results, list):
                            all_results.extend(results)
                        else:
                            all_results.append(results)
                    except json.JSONDecodeError:
                        print(f"  Warning: Could not parse Promptfoo output for {config_name}", file=sys.stderr)
                else:
                    print(f"  Warning: Promptfoo returned exit code {result.returncode} for {config_name}", file=sys.stderr)
                    if result.stderr:
                        print(f"    stderr: {result.stderr[:200]}", file=sys.stderr)

            except FileNotFoundError:
                stage.status = "failed"
                stage.error = "npx/promptfoo not found. Install with: npm install -g promptfoo"
                stage.duration_ms = (time.monotonic() - start) * 1000
                return stage
            except subprocess.TimeoutExpired:
                print(f"  Warning: Promptfoo timed out for {config_name}", file=sys.stderr)

        stage.data = all_results
        stage.result_count = len(all_results)
        stage.status = "success" if all_results else "failed"
        if not all_results:
            stage.error = "No results produced"
        stage.duration_ms = (time.monotonic() - start) * 1000

        # Save raw results
        results_path = self.output_dir / "promptfoo_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)

        return stage

    # ── Stage 2: Loophole Scanner ──

    def run_scanner(self, scan_dirs: list[str] | None = None) -> PipelineStage:
        """Run the loophole scanner on prompt templates.

        Args:
            scan_dirs: Directories to scan. Defaults to config_dir.
        """
        stage = PipelineStage(name="loophole_scanner")
        start = time.monotonic()

        if scan_dirs is None:
            scan_dirs = [str(self.config_dir)]

        all_results: list[dict] = []

        for scan_dir in scan_dirs:
            if not Path(scan_dir).is_dir():
                print(f"  Warning: Scan directory not found: {scan_dir}", file=sys.stderr)
                continue

            print(f"  Scanning: {scan_dir}...")
            results = self.scanner.scan_directory(scan_dir)

            for scan_result in results:
                all_results.append({
                    "target": scan_result.target,
                    "score": scan_result.score,
                    "vulnerabilities": [
                        {
                            "id": v.id,
                            "severity": v.severity.value,
                            "title": v.title,
                            "description": v.description,
                            "location": v.location,
                            "evidence": v.evidence,
                            "remediation": v.remediation,
                            "cwe": v.cwe,
                        }
                        for v in scan_result.vulnerabilities
                    ],
                })

        stage.data = all_results
        stage.result_count = sum(len(r.get("vulnerabilities", [])) for r in all_results)
        stage.status = "success"
        stage.duration_ms = (time.monotonic() - start) * 1000

        # Save results
        results_path = self.output_dir / "scanner_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)

        return stage

    # ── Stage 3: Pattern Detector ──

    def run_pattern_detector(self, dataset_files: list[str] | None = None) -> PipelineStage:
        """Run the pattern detector on adversarial datasets.

        Args:
            dataset_files: JSON files containing prompts to analyze.
                           Defaults to all JSON datasets in dataset_dir.
        """
        stage = PipelineStage(name="pattern_detector")
        start = time.monotonic()

        if dataset_files is None:
            dataset_files = [str(f) for f in self.dataset_dir.glob("*.json")]

        all_results: list[dict] = []

        for dataset_file in dataset_files:
            if not Path(dataset_file).exists():
                continue

            print(f"  Analyzing: {Path(dataset_file).name}...")

            with open(dataset_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            prompts = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        prompts.append(item)
                    elif isinstance(item, dict):
                        prompt = item.get("payload", item.get("prompt", item.get("template", "")))
                        if prompt:
                            prompts.append(prompt)

            for prompt in prompts:
                result = self.pattern_detector.analyze(prompt)
                if result.is_suspicious:
                    all_results.append({
                        "prompt": prompt[:200],
                        "risk_score": result.risk_score,
                        "risk_level": result.risk_level,
                        "is_suspicious": result.is_suspicious,
                        "is_dangerous": result.is_dangerous,
                        "matched_patterns": [
                            {
                                "pattern_id": p.pattern_id,
                                "pattern_name": p.pattern_name,
                                "category": p.category,
                                "confidence": p.confidence,
                                "risk_level": p.risk_level,
                            }
                            for p in result.matched_patterns
                        ],
                        "heuristic_flags": result.heuristic_flags,
                        "categories": result.categories,
                    })

        stage.data = all_results
        stage.result_count = len(all_results)
        stage.status = "success"
        stage.duration_ms = (time.monotonic() - start) * 1000

        # Save results
        results_path = self.output_dir / "pattern_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)

        return stage

    # ── Stage 4: Threat Model ──

    def run_threat_model(self, system_name: str = "CotExplorerV2") -> PipelineStage:
        """Generate a STRIDE threat model.

        Args:
            system_name: Name of the system to model.
        """
        stage = PipelineStage(name="threat_model")
        start = time.monotonic()

        print(f"  Generating threat model for: {system_name}...")

        model = self.threat_modeler.create_model(system_name=system_name)
        model_json = self.threat_modeler.generate_json(model)
        model_md = self.threat_modeler.generate_report(model)

        stage.data = model_json
        stage.result_count = len(model.threats)
        stage.status = "success"
        stage.duration_ms = (time.monotonic() - start) * 1000

        # Save both formats
        json_path = self.output_dir / "threat_model.json"
        md_path = self.output_dir / "threat_model.md"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(model_json, f, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(model_md)

        return stage

    # ── Stage 5: Report Generation ──

    def generate_report(self, pipeline_result: PipelineResult) -> PipelineStage:
        """Generate the final unified report.

        Args:
            pipeline_result: Results from all previous stages.
        """
        stage = PipelineStage(name="report_generation")
        start = time.monotonic()

        print("  Generating unified report...")

        # Extract data from stages
        pf_data = None
        scanner_data = None
        pattern_data = None
        tm_data = None

        for s in pipeline_result.stages:
            if s.name == "promptfoo" and s.data:
                pf_data = s.data
            elif s.name == "loophole_scanner" and s.data:
                scanner_data = s.data
            elif s.name == "pattern_detector" and s.data:
                pattern_data = s.data
            elif s.name == "threat_model" and s.data:
                tm_data = s.data

        report = self.report_generator.generate(
            promptfoo_results=pf_data,
            scanner_results=scanner_data,
            pattern_results=pattern_data,
            threat_model=tm_data,
        )

        # Save report in both formats
        md_path = self.output_dir / "security_report.md"
        json_path = self.output_dir / "security_report.json"

        self.report_generator.save(report, str(md_path), format="markdown")
        self.report_generator.save(report, str(json_path), format="json")

        stage.data = {"overall_score": report.overall_score, "risk_level": report.risk_level}
        stage.result_count = len(report.findings)
        stage.status = "success"
        stage.duration_ms = (time.monotonic() - start) * 1000

        return stage

    # ── Full Pipeline ──

    def run_full(
        self,
        skip_promptfoo: bool = False,
        skip_scanner: bool = False,
        skip_patterns: bool = False,
        skip_threat_model: bool = False,
    ) -> PipelineResult:
        """Run the complete security evaluation pipeline.

        Args:
            skip_*: Skip individual stages if not needed.

        Returns:
            PipelineResult with all stage outcomes.
        """
        result = PipelineResult(
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        total_start = time.monotonic()

        print("=" * 60)
        print("CotExplorerV2 Security Evaluation Pipeline")
        print("=" * 60)

        # Stage 1: Promptfoo
        if not skip_promptfoo:
            print("\n[1/5] Running Promptfoo evaluations...")
            pf_stage = self.run_promptfoo()
            result.stages.append(pf_stage)
            print(f"  -> {pf_stage.status}: {pf_stage.result_count} results ({pf_stage.duration_ms:.0f}ms)")
        else:
            result.stages.append(PipelineStage(name="promptfoo", status="skipped"))

        # Stage 2: Scanner
        if not skip_scanner:
            print("\n[2/5] Running loophole scanner...")
            scan_stage = self.run_scanner()
            result.stages.append(scan_stage)
            print(f"  -> {scan_stage.status}: {scan_stage.result_count} vulnerabilities ({scan_stage.duration_ms:.0f}ms)")
        else:
            result.stages.append(PipelineStage(name="loophole_scanner", status="skipped"))

        # Stage 3: Pattern Detector
        if not skip_patterns:
            print("\n[3/5] Running pattern detector...")
            pattern_stage = self.run_pattern_detector()
            result.stages.append(pattern_stage)
            print(f"  -> {pattern_stage.status}: {pattern_stage.result_count} suspicious prompts ({pattern_stage.duration_ms:.0f}ms)")
        else:
            result.stages.append(PipelineStage(name="pattern_detector", status="skipped"))

        # Stage 4: Threat Model
        if not skip_threat_model:
            print("\n[4/5] Generating threat model...")
            tm_stage = self.run_threat_model()
            result.stages.append(tm_stage)
            print(f"  -> {tm_stage.status}: {tm_stage.result_count} threats identified ({tm_stage.duration_ms:.0f}ms)")
        else:
            result.stages.append(PipelineStage(name="threat_model", status="skipped"))

        # Stage 5: Report
        print("\n[5/5] Generating unified report...")
        report_stage = self.generate_report(result)
        result.stages.append(report_stage)
        report_data = report_stage.data or {}
        print(f"  -> {report_stage.status}: {report_stage.result_count} findings")
        print(f"  -> Overall Score: {report_data.get('overall_score', 'N/A')}/100 ({report_data.get('risk_level', 'N/A')})")

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.total_duration_ms = (time.monotonic() - total_start) * 1000

        # Summary
        print("\n" + "=" * 60)
        print("Pipeline Summary")
        print("=" * 60)
        for s in result.stages:
            status_icon = {
                "success": "[OK]",
                "failed": "[FAIL]",
                "skipped": "[SKIP]",
            }.get(s.status, "[??]")
            print(f"  {status_icon} {s.name}: {s.result_count} results ({s.duration_ms:.0f}ms)")
            if s.error:
                print(f"       Error: {s.error}")
        print(f"\nTotal Duration: {result.total_duration_ms:.0f}ms")
        print(f"Reports saved to: {self.output_dir}")

        if result.failed_stages:
            print(f"\nFailed stages: {', '.join(result.failed_stages)}")

        return result


# ──────────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point for the security pipeline."""
    if len(sys.argv) < 2:
        print("CotExplorerV2 Security Evaluation Pipeline")
        print()
        print("Usage:")
        print("  python pipeline.py --full                      Run full pipeline")
        print("  python pipeline.py --promptfoo                 Promptfoo evaluations only")
        print("  python pipeline.py --scan [directory]          Loophole scanner only")
        print("  python pipeline.py --patterns [dataset.json]   Pattern detector only")
        print("  python pipeline.py --threat-model [name]       Threat model only")
        print("  python pipeline.py --report                    Generate report from existing results")
        print()
        print("Options:")
        print("  --output-dir <path>   Output directory for reports (default: ./reports)")
        print("  --skip-promptfoo      Skip Promptfoo stage in full pipeline")
        print("  --skip-scanner        Skip scanner stage in full pipeline")
        print("  --skip-patterns       Skip pattern detector stage in full pipeline")
        sys.exit(0)

    # Parse output dir
    output_dir = None
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    pipeline = SecurityPipeline(output_dir=output_dir)

    if "--full" in sys.argv:
        pipeline.run_full(
            skip_promptfoo="--skip-promptfoo" in sys.argv,
            skip_scanner="--skip-scanner" in sys.argv,
            skip_patterns="--skip-patterns" in sys.argv,
        )

    elif "--promptfoo" in sys.argv:
        configs = None
        # Check for specific config
        idx = sys.argv.index("--promptfoo")
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            configs = [sys.argv[idx + 1]]
        stage = pipeline.run_promptfoo(configs)
        print(f"Result: {stage.status} ({stage.result_count} results)")

    elif "--scan" in sys.argv:
        idx = sys.argv.index("--scan")
        scan_dirs = None
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            scan_dirs = [sys.argv[idx + 1]]
        stage = pipeline.run_scanner(scan_dirs)
        print(f"Result: {stage.status} ({stage.result_count} vulnerabilities)")

    elif "--patterns" in sys.argv:
        idx = sys.argv.index("--patterns")
        datasets = None
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            datasets = [sys.argv[idx + 1]]
        stage = pipeline.run_pattern_detector(datasets)
        print(f"Result: {stage.status} ({stage.result_count} suspicious prompts)")

    elif "--threat-model" in sys.argv:
        idx = sys.argv.index("--threat-model")
        name = "CotExplorerV2"
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            name = sys.argv[idx + 1]
        stage = pipeline.run_threat_model(name)
        print(f"Result: {stage.status} ({stage.result_count} threats)")

    elif "--report" in sys.argv:
        # Load existing results and generate report
        result = PipelineResult()

        for fname, stage_name in [
            ("promptfoo_results.json", "promptfoo"),
            ("scanner_results.json", "loophole_scanner"),
            ("pattern_results.json", "pattern_detector"),
            ("threat_model.json", "threat_model"),
        ]:
            fpath = pipeline.output_dir / fname
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result.stages.append(PipelineStage(
                    name=stage_name,
                    status="success",
                    data=data,
                    result_count=len(data) if isinstance(data, list) else 1,
                ))

        report_stage = pipeline.generate_report(result)
        report_data = report_stage.data or {}
        print(f"Report generated: {report_stage.result_count} findings")
        print(f"Overall Score: {report_data.get('overall_score', 'N/A')}/100")
        print(f"Saved to: {pipeline.output_dir}")

    else:
        print(f"Unknown command: {sys.argv[1]}")
        print("Run with no arguments to see usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
