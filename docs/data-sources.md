# Data Sources Document -- Cot-ExplorerV2

Last updated: 2026-03-25

Complete reference for all data sources, API configurations, rate limits, update schedules, legal compliance, and fallback strategies.

---

## Complete Data Source Table

| # | Source | Data Type | Endpoint / URL | Rate Limit | API Key | Cost | Update Frequency |
|---|---|---|---|---|---|---|---|
| 1 | CFTC.gov | COT reports (TFF, Legacy, Disaggregated, Supplemental) | `https://www.cftc.gov/dea/futures/` | Unlimited | No | Free (public domain) | Weekly (Friday 15:30 ET) |
| 2 | FRED | GDP, CPI, NFP, jobless claims, JOLTS, DGS10, DTB3 | `https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}` | 120 req/min | Yes (free registration) | Free | Varies by series (daily to quarterly) |
| 3 | Yahoo Finance | OHLC, quotes, daily + intraday | `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}` | Unofficial (no formal limit) | No | Free (personal use) | Real-time during market hours |
| 4 | Stooq | Daily OHLC CSV | `https://stooq.com/q/d/l/?s={symbol}&i=d` | Unlimited | No | Free | Daily after market close |
| 5 | Twelvedata | OHLC, forex, intraday | `https://api.twelvedata.com/time_series` | 800 req/day (free) | Yes (free registration) | Free tier: 800/day. Paid: from $29/mo | Intraday (15m/1H/4H) |
| 6 | Finnhub | Real-time quotes, market status | `https://finnhub.io/api/v1/quote` | 60 req/min (free) | Yes (free registration) | Free tier: 60/min. Paid: from $50/mo | Real-time |
| 7 | Alpha Vantage | OHLC, forex, technical indicators | `https://www.alphavantage.co/query` | 25 req/day (free) | Yes (free registration) | Free tier: 25/day. Premium: from $49/mo | Daily/intraday |
| 8 | CNN | Fear & Greed Index | `https://production.dataviz.cnn.io/index/fearandgreed/graphdata` | Unofficial | No | Free | Hourly |
| 9 | ForexFactory | Economic calendar | Web scrape | Unofficial | No | Free | Daily |
| 10 | Google News RSS | News headlines (economy, markets, geopolitics) | `https://news.google.com/rss/search?q=economy+markets+geopolitics` | Unofficial | No | Free | Every pipeline run |
| 11 | BBC News RSS | World news headlines | `https://feeds.bbci.co.uk/news/world/rss.xml` | Unofficial | No | Free | Every pipeline run |

---

## API Rate Limits and Keys

### FRED API

- **Registration:** https://fred.stlouisfed.org/docs/api/api_key.html
- **Rate limit:** 120 requests per minute
- **Key format:** 32-character alphanumeric string
- **Environment variable:** `FRED_API_KEY`
- **Fallback:** The `fetch_fundamentals.py` script can fetch CSV data from FRED without an API key using the graph endpoint. The API key is needed only for higher rate limits and the JSON API.

**Series used:**
| Series ID | Description | Frequency |
|---|---|---|
| DGS10 | 10-Year Treasury Constant Maturity Rate | Daily |
| DTB3 | 3-Month Treasury Bill Rate | Daily |
| GDP | Gross Domestic Product | Quarterly |
| CPIAUCSL | Consumer Price Index | Monthly |
| PAYEMS | Non-Farm Payrolls | Monthly |
| ICSA | Initial Claims | Weekly |
| JTSJOL | JOLTS Job Openings | Monthly |

### Twelvedata API

- **Registration:** https://twelvedata.com/account/api-key
- **Rate limit:** 800 requests/day (free tier), 8 credits/minute
- **Key format:** 32-character alphanumeric
- **Environment variable:** `TWELVEDATA_API_KEY`
- **Symbols used:** EUR/USD, USD/JPY, GBP/USD, AUD/USD, XAU/USD

**Note:** Twelvedata is the first-priority source in the price waterfall. Its data quality is the highest but the daily limit is restrictive. The pipeline uses Twelvedata for forex pairs where it provides the best coverage.

### Finnhub API

- **Registration:** https://finnhub.io/register
- **Rate limit:** 60 requests/minute (free tier)
- **Key format:** Alphanumeric string
- **Environment variable:** `FINNHUB_API_KEY`
- **Symbols used:** SI1! (Silver futures), UKOIL (Brent), USOIL (WTI), ^GSPC, ^NDX, ^VIX

**Note:** Finnhub is used as a real-time quote overlay and for instruments not well-served by other sources (Silver futures, oil futures).

### Alpha Vantage API

- **Registration:** https://www.alphavantage.co/support/#api-key
- **Rate limit:** 25 requests/day (free tier), 5 requests/minute
- **Key format:** Alphanumeric string
- **Environment variable:** Not yet configured in `.env.example` (new addition)
- **Usage:** Secondary fallback for forex and commodity data

### Signal Distribution Keys

| Service | Environment Variable | Purpose |
|---|---|---|
| Telegram | `TELEGRAM_TOKEN` | Bot token for signal alerts |
| Telegram | `TELEGRAM_CHAT_ID` | Target chat/channel ID |
| Discord | `DISCORD_WEBHOOK` | Webhook URL for signal alerts |
| API Auth | `SCALP_API_KEY` | API key for REST endpoint authentication |

---

## Data Freshness and Update Schedules

### COT Data

| Report Type | Publication | Coverage | Delay |
|---|---|---|---|
| Traders in Financial Futures (TFF) | Friday 15:30 ET | As of Tuesday close | 3-day delay |
| Legacy (Futures Only) | Friday 15:30 ET | As of Tuesday close | 3-day delay |
| Disaggregated (Futures Only) | Friday 15:30 ET | As of Tuesday close | 3-day delay |
| Supplemental | Friday 15:30 ET | As of Tuesday close | 3-day delay |

The COT data is fetched by `fetch_cot.py` which downloads ZIP files from CFTC.gov, extracts the CSV data, parses all 4 report types, and writes to JSON + database.

### Price Data

| Source | Freshness | Typical Delay | Best For |
|---|---|---|---|
| Finnhub | Real-time | < 1 second | Live quotes during market hours |
| Twelvedata | Near real-time | 1-15 minutes | Intraday OHLC bars |
| Yahoo Finance | 15-min delayed | 15 minutes | Daily OHLC, broad coverage |
| Stooq | End of day | Next business day | Daily OHLC, historical |
| Alpha Vantage | 15-min delayed | 15 minutes | Fallback source |

### Macro Data

| Indicator | Source | Release Frequency | Typical Release Time |
|---|---|---|---|
| GDP | FRED (BEA) | Quarterly (3 estimates) | 08:30 ET |
| CPI | FRED (BLS) | Monthly | 08:30 ET |
| Non-Farm Payrolls | FRED (BLS) | Monthly (first Friday) | 08:30 ET |
| Initial Claims | FRED (DOL) | Weekly (Thursday) | 08:30 ET |
| JOLTS | FRED (BLS) | Monthly (~6-week lag) | 10:00 ET |
| 10Y Treasury | FRED | Daily | 15:00 ET |
| 3M T-Bill | FRED | Daily | 15:00 ET |
| Fear & Greed | CNN | Hourly | Rolling |
| HYG, TIP, EEM, Copper | Yahoo Finance | Daily | Market close |

### Pipeline Schedule

```
Weekdays only (Monday-Friday):
  06:45 UTC = 07:45 CET  (Pre-London open)
  11:30 UTC = 12:30 CET  (London session, mid-morning)
  13:15 UTC = 14:15 CET  (NY overlap begins)
  16:15 UTC = 17:15 CET  (Late NY session)

Weekly:
  Sunday 03:00 UTC       (Full backtest run)

Monthly:
  1st of month 04:00 UTC (Security scan: pip-audit + trufflehog)
```

---

## Legal Compliance Notes

### Public Domain / Government Data

**CFTC COT Reports:** Public domain data published by the U.S. Commodity Futures Trading Commission. No restrictions on use, redistribution, or commercial application. Data is freely available at https://www.cftc.gov/dea/futures/.

**FRED Economic Data:** Public domain data from the Federal Reserve Bank of St. Louis. Free to use for any purpose. Some underlying series may have attribution requirements from the original statistical agency (BLS, BEA, etc.).

### Terms of Service Compliance

**Yahoo Finance:** Uses the unofficial v8 chart API. Yahoo's terms of service permit personal and non-commercial use. The data is fetched using standard HTTP requests with a browser-like User-Agent. No login or authentication bypass is performed.

**Stooq:** Provides free daily OHLC data via direct CSV download links. No API key or authentication required. Used for non-commercial purposes.

**CNN Fear & Greed:** Unofficial API endpoint. Used for personal/research purposes. The data is publicly displayed on CNN's website.

**ForexFactory Calendar:** Web-scraped economic calendar data. Used for personal analysis. No rate limiting is abused.

**Google News / BBC RSS:** Public RSS feeds designed for syndication. Used within the intended purpose of RSS feeds.

### Licensed API Services

**Twelvedata:** Used under the free tier terms (800 requests/day). API key required. Terms permit non-commercial use on the free tier. Commercial use requires a paid plan.

**Finnhub:** Used under the free tier terms (60 requests/minute). API key required. Free tier permits non-commercial and commercial use with attribution.

**Alpha Vantage:** Used under the free tier terms (25 requests/day). API key required. Free tier is for personal use.

### Norwegian Financial Regulations

Cot-ExplorerV2 generates **trading signals, not financial advice**. Important disclaimers:

- Signals are for informational and educational purposes only
- Past performance does not guarantee future results
- Users are responsible for their own trading decisions
- The platform does not manage money or execute trades
- No guarantees of profit or specific returns are made
- Users should consult a licensed financial advisor before trading

Under Norwegian securities law (Verdipapirhandelloven), providing personalized investment recommendations requires an authorized investment firm license from Finanstilsynet. Cot-ExplorerV2's automated signal generation does not constitute personalized advice.

---

## Fallback Strategies

### Price Data Fallback Chain

```
Attempt 1: Twelvedata API
  |
  +--> Success? Use data
  +--> Fail (rate limit / timeout / error)?
         |
         v
Attempt 2: Stooq CSV
  |
  +--> Success? Use data
  +--> Fail?
         |
         v
Attempt 3: Yahoo Finance v8
  |
  +--> Success? Use data
  +--> Fail?
         |
         v
Attempt 4: Finnhub quote (real-time only, no OHLC history)
  |
  +--> Success? Use as quote overlay
  +--> Fail? Mark instrument as "no data"
```

### Macro Data Fallback

For interest rates (TNX, IRX):
1. **FRED API** (official, highest quality)
2. **Yahoo Finance** (fallback if FRED unavailable)

For ETFs and commodities (HYG, TIP, Copper, EEM):
1. **Yahoo Finance** (primary for equity/ETF data)

### COT Data Resilience

COT data is published weekly and cached locally:
1. Attempt fresh download from CFTC.gov
2. If download fails, use the most recent cached data from `data/combined/latest.json`
3. The SQLite database stores all historical COT positions for offline analysis

### News Sentiment Fallback

The sentiment engine processes multiple RSS feeds:
1. Google News RSS (economy + markets + geopolitics)
2. BBC World News RSS

If both feeds fail, the news sentiment criterion (`news_confirms`) is set to neutral, effectively scoring 0 for that criterion.

### Complete System Degradation

If all external APIs are unavailable, the system can still:
- Serve cached COT data from the database
- Serve historical prices from the database
- Serve previously generated signals
- Run the API server with stale data (timestamps indicate freshness)

The health endpoint (`/health`) reports `last_run` timestamp so consumers can detect stale data.

---

## Instrument Symbol Mapping

Each of the 12 tracked instruments has mappings for every data provider:

| Key | Name | Yahoo | Stooq | Twelvedata | Finnhub | COT Market |
|---|---|---|---|---|---|---|
| EURUSD | EUR/USD | EURUSD=X | eurusd | EUR/USD | -- | euro fx |
| USDJPY | USD/JPY | JPY=X | usdjpy | USD/JPY | -- | japanese yen |
| GBPUSD | GBP/USD | GBPUSD=X | gbpusd | GBP/USD | -- | british pound |
| AUDUSD | AUD/USD | AUDUSD=X | audusd | AUD/USD | -- | -- |
| Gold | Gull | GC=F | xauusd | XAU/USD | -- | gold |
| Silver | Solv | SI=F | xagusd | -- | SI1! | silver |
| Brent | Brent | BZ=F | co.f | -- | UKOIL | crude oil, light sweet |
| WTI | WTI | CL=F | cl.f | -- | USOIL | crude oil, light sweet |
| SPX | S&P 500 | ^GSPC | ^spx | -- | ^GSPC | s&p 500 consolidated |
| NAS100 | Nasdaq | ^NDX | ^ndx | -- | ^NDX | nasdaq mini |
| VIX | VIX | ^VIX | ^vix | -- | ^VIX | -- |
| DXY | DXY | DX-Y.NYB | dxy.f | -- | -- | usd index |

### Macro Indicator Symbols

| Key | Yahoo Symbol | FRED Series | Purpose |
|---|---|---|---|
| HYG | HYG | -- | High Yield Corp Bond ETF (credit risk) |
| TIP | TIP | -- | TIPS Bond ETF (inflation expectations) |
| TNX | ^TNX | DGS10 | 10-Year Treasury yield |
| IRX | ^IRX | DTB3 | 3-Month Treasury bill |
| Copper | HG=F | -- | Copper futures (growth indicator) |
| EEM | EEM | -- | Emerging Markets ETF (risk appetite) |
