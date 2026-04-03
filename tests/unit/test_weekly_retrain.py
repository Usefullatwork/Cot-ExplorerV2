"""Tests for src.pipeline.weekly_retrain -- Friday retrain pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pipeline.weekly_retrain import RetrainResult, run_weekly_retrain


# ---------------------------------------------------------------------------
# Missing data graceful failure
# ---------------------------------------------------------------------------


class TestRunWeeklyRetrainMissingData:
    """Tests for graceful handling of missing data."""

    def test_missing_data_dir(self, tmp_path: Path) -> None:
        """Non-existent data dir should return errors, not crash."""
        missing = tmp_path / "nonexistent"
        result = run_weekly_retrain(
            data_dir=missing, output_dir=tmp_path / "out",
        )
        assert isinstance(result, RetrainResult)
        assert len(result.errors) > 0
        assert not result.signal_weights_updated
        assert not result.drift_detected

    def test_empty_data_dir(self, tmp_path: Path) -> None:
        """Empty data dir (no signal_log.json) should skip gracefully."""
        result = run_weekly_retrain(
            data_dir=tmp_path, output_dir=tmp_path / "out",
        )
        assert isinstance(result, RetrainResult)
        assert "No signal log data available" in result.errors

    def test_invalid_json_in_signal_log(self, tmp_path: Path) -> None:
        """Corrupt JSON should be handled without crashing."""
        log_path = tmp_path / "signal_log.json"
        log_path.write_text("not valid json {{{", encoding="utf-8")
        result = run_weekly_retrain(
            data_dir=tmp_path, output_dir=tmp_path / "out",
        )
        assert not result.signal_weights_updated


# ---------------------------------------------------------------------------
# Successful run with valid data
# ---------------------------------------------------------------------------


class TestRunWeeklyRetrainSuccess:
    """Tests for successful pipeline runs with valid data."""

    def _write_signal_log(self, data_dir: Path, n_signals: int = 3) -> None:
        """Write a valid signal_log.json for testing."""
        records = []
        for i in range(n_signals):
            sig_id = f"sig_{i}"
            for j in range(50):
                records.append({
                    "signal_id": sig_id,
                    "outcome": j % (i + 2) != 0,  # varied win rates
                })
        log_path = data_dir / "signal_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(records, f)

    def test_writes_output_files(self, tmp_path: Path) -> None:
        """Valid data should produce weights and report files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        out_dir = tmp_path / "retrain"
        self._write_signal_log(data_dir)

        result = run_weekly_retrain(data_dir=data_dir, output_dir=out_dir)

        assert result.signal_weights_updated
        assert result.date  # should be a non-empty date string

        # Check output files exist
        output_files = list(out_dir.glob("*_weights.json"))
        assert len(output_files) >= 1
        report_files = list(out_dir.glob("*_report.json"))
        assert len(report_files) >= 1

    def test_report_json_valid(self, tmp_path: Path) -> None:
        """Report JSON should be valid and contain expected keys."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        out_dir = tmp_path / "retrain"
        self._write_signal_log(data_dir)

        result = run_weekly_retrain(data_dir=data_dir, output_dir=out_dir)
        report_files = list(out_dir.glob("*_report.json"))
        assert len(report_files) >= 1

        with open(report_files[0], encoding="utf-8") as f:
            report = json.load(f)

        assert "date" in report
        assert "signal_weights_updated" in report
        assert "drift_detected" in report
        assert "quality_score" in report
        assert "weights" in report

    def test_quality_score_populated(self, tmp_path: Path) -> None:
        """Quality score should be > 0 when signals have data."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        out_dir = tmp_path / "retrain"
        self._write_signal_log(data_dir)

        result = run_weekly_retrain(data_dir=data_dir, output_dir=out_dir)
        assert result.quality_score > 0.0

    def test_result_fields_populated(self, tmp_path: Path) -> None:
        """RetrainResult should have all fields populated."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        out_dir = tmp_path / "retrain"
        self._write_signal_log(data_dir)

        result = run_weekly_retrain(data_dir=data_dir, output_dir=out_dir)
        assert isinstance(result.date, str)
        assert isinstance(result.signal_weights_updated, bool)
        assert isinstance(result.drift_detected, bool)
        assert isinstance(result.drift_details, list)
        assert isinstance(result.rebalance_actions, int)
        assert isinstance(result.quality_score, float)
        assert isinstance(result.errors, list)
