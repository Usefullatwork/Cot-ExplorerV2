"""
fundamentals.py - Configuration constants for fundamental macro scoring.

Extracted from src/trading/core/fetch_fundamentals.py.
"""

# ---------------------------------------------------------------------------
# FRED series definitions
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "GDP":     {"id": "A191RL1Q225SBEA", "type": "level",   "label": "GDP Growth QoQ (%)"},
    "Retail":  {"id": "RSAFS",           "type": "mom",     "label": "Retail Sales MoM (%)"},
    "ConConf": {"id": "UMCSENT",         "type": "level",   "label": "UoM Consumer Sentiment"},
    "CPI":     {"id": "CPIAUCSL",        "type": "yoy",     "label": "CPI YoY (%)"},
    "PPI":     {"id": "PPIACO",          "type": "yoy",     "label": "PPI YoY (%)"},
    "PCE":     {"id": "PCEPI",           "type": "yoy",     "label": "PCE YoY (%)"},
    "IntRate": {"id": "FEDFUNDS",        "type": "level",   "label": "Fed Funds Rate (%)"},
    "NFP":     {"id": "PAYEMS",          "type": "mom_abs", "label": "NFP Change (k)"},
    "Unemp":   {"id": "UNRATE",          "type": "level",   "label": "Unemployment Rate (%)"},
    "Claims":  {"id": "ICSA",            "type": "level",   "label": "Initial Claims (k)"},
    "ADP":     {"id": "ADPMNUSNERNSA",   "type": "level",   "label": "ADP Change (k)"},
    "JOLTS":   {"id": "JTSJOL",          "type": "level",   "label": "JOLTS Openings (k)"},
}

# ---------------------------------------------------------------------------
# Indicator weights (within-category importance)
# ---------------------------------------------------------------------------
INDICATOR_WEIGHTS = {
    "GDP": 1.0, "mPMI": 2.0, "sPMI": 2.0, "Retail": 1.5, "ConConf": 1.5,
    "CPI": 2.0, "PPI": 1.0, "PCE": 2.0, "IntRate": 1.5,
    "NFP": 2.0, "Unemp": 1.5, "Claims": 1.5, "ADP": 1.0, "JOLTS": 1.0,
}

# ---------------------------------------------------------------------------
# Category groupings
# ---------------------------------------------------------------------------
CATEGORIES = {
    "econ_growth": ["GDP", "mPMI", "sPMI", "Retail", "ConConf"],
    "inflation":   ["CPI", "PPI", "PCE", "IntRate"],
    "jobs":        ["NFP", "Unemp", "Claims", "ADP", "JOLTS"],
}

# ---------------------------------------------------------------------------
# Category weights per asset class
# ---------------------------------------------------------------------------
CAT_WEIGHTS_FX = {"econ_growth": 0.25, "inflation": 0.40, "jobs": 0.35}
CAT_WEIGHTS_EQ = {"econ_growth": 0.50, "inflation": 0.10, "jobs": 0.40}

# ---------------------------------------------------------------------------
# Instrument USD direction mapping
# ---------------------------------------------------------------------------
INSTRUMENT_USD_DIR = {
    "EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1,
    "USDJPY": +1, "DXY":    +1,
    "Gold":   -1, "Silver": -1,
    "SPX":    +1, "NAS100": +1,
    "Brent":  +1, "WTI":    +1,
}

EQ_INSTRUMENTS = {"SPX", "NAS100", "Brent", "WTI"}
