#!/usr/bin/env python3
"""
fetch_fundamentals.py — Tynt wrapper som delegerer til src/trading/core/fetch_fundamentals.py.

Henter fundamental makrodata fra FRED og scorer +/-2 per indikator.
Lagrer til data/prices/fundamentals_latest.json.

Kategorier (EdgeFinder-stil):
  - Economic Growth: GDP QoQ, Retail Sales MoM, UoM Consumer Confidence
  - Inflation:       CPI YoY, PPI YoY, PCE YoY, Fed Funds Rate
  - Jobs Market:     NFP, Unemployment Rate, Initial Claims, ADP, JOLTS

PMI hentes utelukkende fra ForexFactory-kalenderen (ISM-serier er ikke
tilgjengelige som FRED-serie; de ma kjopes direkte fra ISM).

Vekting for hoy-sannsynlighets-setups:
  - Innenfor kategori: vektes per indikator (NFP/Claims/CPI/PCE veier tyngst)
  - Mellom kategorier: inflation 0.40 * jobs 0.35 * growth 0.25 (for FX/metaller)
  - Konsensus-multiplikator: x1.4 nar inflasjon+jobs peker SAMME vei,
    x0.7 nar de peker MOT hverandre -> demper mixet signal

Se src/trading/core/fetch_fundamentals.py for full implementasjon.
"""

import logging
import sys
import os

# Legg til prosjektrot i sys.path slik at src-pakken kan importeres
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.core.fetch_fundamentals import main  # noqa: E402

log = logging.getLogger(__name__)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    log.info("=== fetch_fundamentals.py (wrapper) ===")
    main()
