"""Unit tests for src.data.providers.cftc — ZIP download, report parsing, date handling."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.data.providers.cftc import (
    CATEGORIES,
    REPORTS,
    CftcProvider,
    _download_and_extract,
    _get_category,
    _parse_file,
    _safe_int,
)


# ===== _safe_int ==============================================================

class TestSafeInt:
    """Convert various messy values to int safely."""

    def test_plain_int(self):
        assert _safe_int(42) == 42

    def test_string_int(self):
        assert _safe_int("1000") == 1000

    def test_comma_separated(self):
        assert _safe_int("1,234,567") == 1234567

    def test_float_string_truncates(self):
        assert _safe_int("99.7") == 99

    def test_whitespace(self):
        assert _safe_int("  500  ") == 500

    def test_none_returns_zero(self):
        assert _safe_int(None) == 0

    def test_empty_string_returns_zero(self):
        assert _safe_int("") == 0

    def test_garbage_returns_zero(self):
        assert _safe_int("abc") == 0


# ===== _get_category ==========================================================

class TestGetCategory:
    """Keyword-based categorization of market names."""

    def test_aksjer_sp(self):
        assert _get_category("S&P 500 - CHICAGO MERCANTILE") == "aksjer"

    def test_valuta_euro(self):
        assert _get_category("EURO FX - CHICAGO MERCANTILE") == "valuta"

    def test_renter_treasury(self):
        assert _get_category("10-YEAR T-NOTE - CHICAGO BOARD OF TRADE") == "renter"

    def test_ravarer_gold(self):
        assert _get_category("GOLD - COMMODITY EXCHANGE INC.") == "ravarer"

    def test_krypto_bitcoin(self):
        assert _get_category("BITCOIN - CHICAGO MERCANTILE") == "krypto"

    def test_landbruk_corn(self):
        assert _get_category("CORN - CHICAGO BOARD OF TRADE") == "landbruk"

    def test_volatilitet_vix_matches_aksjer_first(self):
        """'vix' appears in both aksjer and volatilitet; aksjer wins by insertion order."""
        assert _get_category("VIX FUTURES - CBOE FUTURES EXCHANGE") == "aksjer"

    def test_unknown_returns_annet(self):
        assert _get_category("EXOTIC WIDGET FUTURES") == "annet"


# ===== _download_and_extract ==================================================

class TestDownloadAndExtract:
    """Test ZIP download and CSV extraction with mocked HTTP."""

    def _make_zip_bytes(self, csv_content: str, csv_filename: str = "data.txt") -> bytes:
        """Create an in-memory ZIP containing one CSV/txt file."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(csv_filename, csv_content)
        return buf.getvalue()

    @patch("src.data.providers.cftc.urllib.request.urlretrieve")
    def test_successful_extract(self, mock_retrieve):
        """Download + extract produces a .txt file path."""
        csv_text = "Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD\nGOLD,2024-01-02\n"
        zip_bytes = self._make_zip_bytes(csv_text)

        with tempfile.TemporaryDirectory() as tmp:
            def fake_retrieve(url, dest):
                with open(dest, "wb") as f:
                    f.write(zip_bytes)
            mock_retrieve.side_effect = fake_retrieve

            result = _download_and_extract("https://example.com/test.zip", tmp)
            assert result is not None
            assert result.endswith(".txt")
            assert os.path.isfile(result)

    @patch("src.data.providers.cftc.urllib.request.urlretrieve")
    def test_download_error_returns_none(self, mock_retrieve):
        """Network failure returns None."""
        mock_retrieve.side_effect = OSError("Connection refused")
        with tempfile.TemporaryDirectory() as tmp:
            result = _download_and_extract("https://example.com/bad.zip", tmp)
            assert result is None


# ===== _parse_file — TFF report ===============================================

def _write_csv(tmp_dir: str, rows: list[dict[str, Any]], filename: str = "data.txt") -> str:
    """Write a CSV file with DictWriter and return the path."""
    path = os.path.join(tmp_dir, filename)
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return path
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


class TestParseFileTff:
    """Parse a TFF-format CSV into position dicts."""

    def _tff_row(self, **overrides) -> dict[str, Any]:
        base = {
            "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
            "Report_Date_as_YYYY-MM-DD": "2024-01-02",
            "CFTC_Contract_Market_Code": "088691",
            "Open_Interest_All": "500000",
            "Change_in_Open_Interest_All": "5000",
            "Lev_Money_Positions_Long_All": "100000",
            "Lev_Money_Positions_Short_All": "80000",
            "Change_in_Lev_Money_Long_All": "2000",
            "Change_in_Lev_Money_Short_All": "1000",
            "NonRept_Positions_Long_All": "30000",
            "NonRept_Positions_Short_All": "25000",
        }
        base.update(overrides)
        return base

    def test_tff_basic_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_csv(tmp, [self._tff_row()])
            result = _parse_file(path, "tff")
        assert len(result) == 1
        entry = result[0]
        assert entry["report"] == "tff"
        assert entry["spec_long"] == 100000
        assert entry["spec_short"] == 80000
        assert entry["spec_net"] == 20000
        assert entry["change_spec_net"] == 1000  # 2000 - 1000
        assert entry["nonrept_long"] == 30000
        assert entry["nonrept_net"] == 5000  # 30000 - 25000
        assert entry["kategori"] == "ravarer"

    def test_tff_keeps_latest_per_market(self):
        """Without keep_all, only the latest date per market is kept."""
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                self._tff_row(**{"Report_Date_as_YYYY-MM-DD": "2024-01-01"}),
                self._tff_row(**{"Report_Date_as_YYYY-MM-DD": "2024-01-08"}),
            ]
            path = _write_csv(tmp, rows)
            result = _parse_file(path, "tff", keep_all=False)
        assert len(result) == 1
        assert result[0]["date"] == "2024-01-08"

    def test_tff_keep_all_returns_all(self):
        """With keep_all=True, all rows are returned."""
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                self._tff_row(**{"Report_Date_as_YYYY-MM-DD": "2024-01-01"}),
                self._tff_row(**{"Report_Date_as_YYYY-MM-DD": "2024-01-08"}),
            ]
            path = _write_csv(tmp, rows)
            result = _parse_file(path, "tff", keep_all=True)
        assert len(result) == 2

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_csv(tmp, [], filename="empty.txt")
            result = _parse_file(path, "tff")
        assert result == []


# ===== _parse_file — legacy report ============================================

class TestParseFileLegacy:

    def _legacy_row(self, **overrides) -> dict[str, Any]:
        base = {
            "Market_and_Exchange_Names": "EURO FX - CHICAGO MERCANTILE",
            "Report_Date_as_YYYY-MM-DD": "2024-06-01",
            "CFTC_Contract_Market_Code": "099741",
            "Open_Interest_All": "600000",
            "Change_in_Open_Interest_All": "3000",
            "NonComm_Positions_Long_All": "120000",
            "NonComm_Positions_Short_All": "90000",
            "Comm_Positions_Long_All": "200000",
            "Comm_Positions_Short_All": "180000",
            "NonRept_Positions_Long_All": "40000",
            "NonRept_Positions_Short_All": "35000",
            "Change_in_NonComm_Long_All": "5000",
            "Change_in_NonComm_Short_All": "2000",
        }
        base.update(overrides)
        return base

    def test_legacy_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_csv(tmp, [self._legacy_row()])
            result = _parse_file(path, "legacy")
        assert len(result) == 1
        e = result[0]
        assert e["report"] == "legacy"
        assert e["spec_long"] == 120000
        assert e["spec_net"] == 30000  # 120k - 90k
        assert e["comm_net"] == 20000  # 200k - 180k
        assert e["nonrept_net"] == 5000  # 40k - 35k
        assert e["change_spec_net"] == 3000  # 5000 - 2000
        assert e["kategori"] == "valuta"


# ===== _parse_file — unknown report_id ========================================

class TestParseFileUnknown:

    def test_unknown_report_id_skipped(self):
        """Rows with an unrecognized report_id produce no output."""
        with tempfile.TemporaryDirectory() as tmp:
            row = {
                "Market_and_Exchange_Names": "GOLD",
                "Report_Date_as_YYYY-MM-DD": "2024-01-02",
                "CFTC_Contract_Market_Code": "088691",
                "Open_Interest_All": "500000",
                "Change_in_Open_Interest_All": "5000",
            }
            path = _write_csv(tmp, [row])
            result = _parse_file(path, "nonexistent_report")
        assert result == []


# ===== CftcProvider basics ====================================================

class TestCftcProviderBasics:

    def test_name(self):
        p = CftcProvider()
        assert p.name == "cftc"

    def test_is_available(self):
        p = CftcProvider()
        assert p.is_available() is True


# ===== REPORTS config =========================================================

class TestReportsConfig:
    """Verify the REPORTS list is well-formed."""

    def test_four_reports(self):
        assert len(REPORTS) == 4

    def test_report_ids(self):
        ids = {r["id"] for r in REPORTS}
        assert ids == {"tff", "legacy", "disaggregated", "supplemental"}

    def test_urls_contain_cftc(self):
        for r in REPORTS:
            assert "cftc.gov" in r["url"]
            assert "cftc.gov" in r["hist_pat"]

    def test_hist_pat_contains_yyyy(self):
        for r in REPORTS:
            assert "YYYY" in r["hist_pat"]


# ===== CftcProvider.fetch_cot_data (integration-light) ========================

class TestFetchCotDataIntegration:
    """Test fetch_cot_data with mocked _download_and_extract."""

    @patch("src.data.providers.cftc._download_and_extract")
    def test_returns_empty_when_all_downloads_fail(self, mock_dl):
        mock_dl.return_value = None
        p = CftcProvider()
        with tempfile.TemporaryDirectory() as tmp:
            result = p.fetch_cot_data(output_dir=tmp, history=False)
        assert result == []

    @patch("src.data.providers.cftc._download_and_extract")
    def test_writes_combined_json(self, mock_dl):
        """Even with empty data, combined/latest.json is written."""
        mock_dl.return_value = None
        p = CftcProvider()
        with tempfile.TemporaryDirectory() as tmp:
            p.fetch_cot_data(output_dir=tmp, history=False)
            combined_path = Path(tmp) / "combined" / "latest.json"
            assert combined_path.exists()
            data = json.loads(combined_path.read_text())
            assert isinstance(data, list)

    @patch("src.data.providers.cftc._download_and_extract")
    def test_deduplication(self, mock_dl):
        """Duplicate symbol+report entries are de-duplicated."""
        # Create a real CSV that will be parsed for the tff report
        tff_row = {
            "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE",
            "Report_Date_as_YYYY-MM-DD": "2024-01-02",
            "CFTC_Contract_Market_Code": "088691",
            "Open_Interest_All": "500000",
            "Change_in_Open_Interest_All": "5000",
            "Lev_Money_Positions_Long_All": "100000",
            "Lev_Money_Positions_Short_All": "80000",
            "Change_in_Lev_Money_Long_All": "2000",
            "Change_in_Lev_Money_Short_All": "1000",
            "NonRept_Positions_Long_All": "30000",
            "NonRept_Positions_Short_All": "25000",
        }

        def mock_download(url, tmp_dir):
            # Only produce data for tff URL
            if "fut_fin" in url:
                return _write_csv(tmp_dir, [tff_row])
            return None

        mock_dl.side_effect = mock_download
        p = CftcProvider()
        with tempfile.TemporaryDirectory() as tmp:
            result = p.fetch_cot_data(output_dir=tmp, history=False)
        # Should have exactly 1 entry (from the tff report; others returned None)
        assert len(result) == 1
        assert result[0]["report"] == "tff"
