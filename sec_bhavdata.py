"""
Section 5 Extractor: sec_bhavdata.py
====================================
Official NSE File 5: Cash Market Security-Wise Deliverable Positions (sec_bhavdata_full_DDMMYYYY.csv)

Extracts cash market equity delivery quantities and turnover for top index heavyweight stocks:
- NIFTY Top Weights: HDFCBANK (13.5%), RELIANCE (9.2%), ICICIBANK (7.8%), INFY (6.1%), TCS (4.2%), ITC (4.1%), LT (4.0%), BHARTIARTL (3.8%), SBIN (3.1%), AXISBANK (3.0%)
- BANKNIFTY Top Weights: HDFCBANK (29.1%), ICICIBANK (24.2%), SBIN (11.5%), KOTAKBANK (9.8%), AXISBANK (9.4%), INDUSINDBK (5.5%)

Microstructure Insight:
- Derivative options without cash delivery backing are vulnerable to false breakouts.
- When Heavy Delivery Buying (> 50% Dlv) coincides with Put writing, the institutional floor is unbreakable.
- When Heavy Delivery Selling (< 35% Dlv or high volume distribution) coincides with Call writing, rallies are sold with high conviction.

Data Quality & Authenticity Guarantee:
- Verifies trading date (DATE1) matches requested session.
- Validates delivery volume and turnover columns.
- Flags and separates authentic delivery data from synthetic fallbacks.
"""

import os
import io
import csv
import json
import argparse
import requests
from datetime import datetime

from data_validator import validate_sec_bhavdata_csv, ValidationResult

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nseindia.com/',
}

NIFTY_HEAVYWEIGHTS = [
    {"symbol": "HDFCBANK",   "weight": 13.52, "name": "HDFC Bank Ltd."},
    {"symbol": "RELIANCE",   "weight": 9.18,  "name": "Reliance Industries Ltd."},
    {"symbol": "ICICIBANK",  "weight": 7.84,  "name": "ICICI Bank Ltd."},
    {"symbol": "INFY",       "weight": 6.12,  "name": "Infosys Ltd."},
    {"symbol": "TCS",        "weight": 4.21,  "name": "Tata Consultancy Services Ltd."},
    {"symbol": "ITC",        "weight": 4.10,  "name": "ITC Ltd."},
    {"symbol": "LT",         "weight": 4.02,  "name": "Larsen & Toubro Ltd."},
    {"symbol": "BHARTIARTL", "weight": 3.85,  "name": "Bharti Airtel Ltd."},
    {"symbol": "SBIN",       "weight": 3.14,  "name": "State Bank of India"},
    {"symbol": "AXISBANK",   "weight": 3.05,  "name": "Axis Bank Ltd."},
]

BANKNIFTY_HEAVYWEIGHTS = [
    {"symbol": "HDFCBANK",   "weight": 29.10, "name": "HDFC Bank Ltd."},
    {"symbol": "ICICIBANK",  "weight": 24.20, "name": "ICICI Bank Ltd."},
    {"symbol": "SBIN",       "weight": 11.50, "name": "State Bank of India"},
    {"symbol": "KOTAKBANK",  "weight": 9.80,  "name": "Kotak Mahindra Bank Ltd."},
    {"symbol": "AXISBANK",   "weight": 9.40,  "name": "Axis Bank Ltd."},
    {"symbol": "INDUSINDBK", "weight": 5.50,  "name": "IndusInd Bank Ltd."},
]


class SecBhavdataExtractor:
    """Extractor for NSE File 5: Cash Market Security-Wise Deliverables with Strict Validation."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_raw_rows(self, date_str: str) -> tuple:
        """
        Retrieves list of raw rows and source type.
        Returns: (rows: list, source_type: str)
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%d%m%Y")
            except ValueError:
                dt = datetime.now()

        date_code = dt.strftime("%d%m%Y")
        iso_code = dt.strftime("%Y%m%d")
        cache_paths = [
            os.path.join(self.cache_dir, f"sec_bhavdata_{date_code}.csv"),
            os.path.join(self.cache_dir, f"sec_bhavdata_{iso_code}.csv")
        ]

        # 1. Local Cache check
        for cp in cache_paths:
            if os.path.exists(cp) and os.path.getsize(cp) > 5000:
                with open(cp, "r", encoding="utf-8", errors="ignore") as f:
                    rows = list(csv.DictReader(f))
                    if rows:
                        return rows, "AUTHENTIC_NSE_CACHE"

        # 2. Live NSE Download
        urls = [
            f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_code}.csv",
            f"https://archives.nseindia.com/content/cm/sec_bhavdata_full_{date_code}.csv",
        ]
        for url in urls:
            try:
                resp = requests.get(url, headers=NSE_HEADERS, timeout=4.0)
                if resp.status_code == 200 and len(resp.content) > 10000:
                    for cp in cache_paths:
                        try:
                            with open(cp, "wb") as f:
                                f.write(resp.content)
                        except Exception:
                            pass
                    text = resp.content.decode("utf-8", errors="ignore")
                    rows = list(csv.DictReader(io.StringIO(text)))
                    return rows, "AUTHENTIC_NSE_LIVE"
            except Exception:
                continue

        # 3. Check sample_files directory
        sample_path = os.path.join(SAMPLE_DIR, f"sec_bhavdata_{date_code}.csv")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8", errors="ignore") as f:
                return list(csv.DictReader(f)), "SAMPLE_DEMO"

        # 4. Fallback to nearest historical cache
        from nse_fetcher import find_nearest_cached_date
        nearest = find_nearest_cached_date(date_str)
        if nearest and nearest != date_str:
            near_dt = datetime.strptime(nearest, "%Y-%m-%d")
            near_code = near_dt.strftime("%d%m%Y")
            near_path = os.path.join(self.cache_dir, f"sec_bhavdata_{near_code}.csv")
            if os.path.exists(near_path) and os.path.getsize(near_path) > 5000:
                with open(near_path, "r", encoding="utf-8", errors="ignore") as f:
                    rows = list(csv.DictReader(f))
                    if rows:
                        return rows, "HISTORICAL_FALLBACK"

        return [], "UNAVAILABLE"

    def parse_constituents(self, rows: list, symbol: str = "NIFTY", date_str: str = "", source_type: str = "CACHE") -> dict:
        """
        Parses rows and isolates heavyweight equity delivery behavior with validation.
        """
        val_res = validate_sec_bhavdata_csv(rows, date_str)
        target_list = BANKNIFTY_HEAVYWEIGHTS if "BANK" in symbol.upper() else NIFTY_HEAVYWEIGHTS
        target_map = {item['symbol']: item for item in target_list}

        stocks_data = {}
        total_delivery_turnover = 0.0
        weighted_score_sum = 0.0
        total_weight_found = 0.0

        for raw_row in rows:
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k}
            sym = row.get("SYMBOL", "").strip().upper()
            series = row.get("SERIES", "").strip().upper()

            if sym in target_map and series in ["EQ", ""]:
                try:
                    close_p = float(str(row.get("CLOSE_PRICE", row.get("CLOSE", 0))).replace(",", "") or 0)
                    prev_p  = float(str(row.get("PREV_CLOSE", row.get("PREVCLOSE", 0))).replace(",", "") or close_p)
                    traded_qty = int(float(str(row.get("TTL_TRD_QNTY", row.get("TOTTRDQTY", 0))).replace(",", "") or 0))
                    deliv_qty  = int(float(str(row.get("DELIV_QTY", row.get("DELIVQTY", 0))).replace(",", "") or 0))
                    deliv_pct  = float(str(row.get("DELIV_PER", row.get("DELIVPER", 0))).replace(",", "") or 0)
                except (ValueError, TypeError):
                    continue

                pct_chg = round(((close_p - prev_p) / max(0.01, prev_p)) * 100, 2)
                dlv_turnover_cr = round((deliv_qty * close_p) / 10000000, 2)
                total_delivery_turnover += dlv_turnover_cr

                if deliv_pct >= 50.0 and pct_chg > 0:
                    behavior = "INSTITUTIONAL ACCUMULATION"
                    score = min(100.0, 50.0 + pct_chg * 15.0)
                    badge_color = "green"
                elif deliv_pct >= 50.0 and pct_chg < 0:
                    behavior = "INSTITUTIONAL DISTRIBUTION"
                    score = max(-100.0, -50.0 + pct_chg * 15.0)
                    badge_color = "red"
                elif deliv_pct < 35.0:
                    behavior = "SPECULATIVE CHURN / LOW DLV"
                    score = pct_chg * 10.0
                    badge_color = "neutral"
                else:
                    behavior = "BALANCED CASH VOLUME"
                    score = pct_chg * 10.0
                    badge_color = "neutral"

                wt = target_map[sym]['weight']
                total_weight_found += wt
                weighted_score_sum += (score * (wt / 100.0))

                stocks_data[sym] = {
                    'symbol': sym,
                    'name': target_map[sym]['name'],
                    'weight_pct': wt,
                    'close_price': close_p,
                    'prev_close': prev_p,
                    'pct_change': pct_chg,
                    'traded_quantity': traded_qty,
                    'delivery_quantity': deliv_qty,
                    'delivery_pct': deliv_pct,
                    'delivery_turnover_cr': dlv_turnover_cr,
                    'behavior': behavior,
                    'score': round(score, 1),
                    'badge_color': badge_color
                }

        normalized_weight = max(1.0, total_weight_found)
        composite_score = round((weighted_score_sum / (normalized_weight / 100.0)), 1)

        if composite_score >= 25.0:
            cash_verdict = "BULLISH CASH ACCUMULATION (EQUITY BUYING SUPPORTS PUT FLOORS)"
            cash_color = "green"
        elif composite_score <= -25.0:
            cash_verdict = "BEARISH CASH DISTRIBUTION (EQUITY OVERHANG REINFORCES CALL RESISTANCE)"
            cash_color = "red"
        else:
            cash_verdict = "BALANCED CASH EQUITIES (DERIVATIVES INVENTORIES DICTATE DIRECTION)"
            cash_color = "neutral"

        return {
            'symbol': symbol,
            'constituents_analyzed': len(stocks_data),
            'coverage_weight_pct': round(total_weight_found, 1),
            'composite_cash_score': composite_score,
            'cash_verdict': cash_verdict,
            'cash_color': cash_color,
            'total_delivery_turnover_cr': round(total_delivery_turnover, 1),
            'stocks': stocks_data,
            'heavyweights': list(stocks_data.values()),
            'validation': val_res.to_dict(),
            'is_authentic': val_res.is_authentic,
            'is_valid': val_res.is_valid,
            'source_type': source_type
        }

    def _generate_synthetic_constituents(self, symbol: str, date_str: str) -> dict:
        """Fallback generator if cash bhavcopy completely unavailable (FLAGGED SYNTHETIC)."""
        target_list = BANKNIFTY_HEAVYWEIGHTS if "BANK" in symbol.upper() else NIFTY_HEAVYWEIGHTS
        stocks = {}
        total_turnover = 0.0
        weighted_sum = 0.0

        for item in target_list:
            sym = item['symbol']
            wt = item['weight']
            close_p = 1680.0 if sym == "HDFCBANK" else (2950.0 if sym == "RELIANCE" else 1250.0)
            pct_chg = -0.42
            deliv_pct = 58.4
            dlv_cr = round(wt * 12.5, 1)
            total_turnover += dlv_cr

            stocks[sym] = {
                'symbol': sym,
                'name': item['name'],
                'weight_pct': wt,
                'close_price': close_p,
                'pct_change': pct_chg,
                'delivery_pct': deliv_pct,
                'delivery_turnover_cr': dlv_cr,
                'behavior': 'INSTITUTIONAL DISTRIBUTION',
                'score': -42.0,
                'badge_color': 'red'
            }
            weighted_sum += (-42.0 * (wt / 100.0))

        val_syn = ValidationResult("SEC_BHAVDATA_CASH", date_str)
        val_syn.is_synthetic = True
        val_syn.is_authentic = False
        val_syn.source_type = "SYNTHETIC_FALLBACK"

        return {
            'symbol': symbol,
            'constituents_analyzed': len(stocks),
            'coverage_weight_pct': 72.5,
            'composite_cash_score': round(weighted_sum, 1),
            'cash_verdict': 'BEARISH CASH DISTRIBUTION (EQUITY OVERHANG)',
            'cash_color': 'red',
            'total_delivery_turnover_cr': round(total_turnover, 1),
            'stocks': stocks,
            'heavyweights': list(stocks.values()),
            'validation': val_syn.to_dict(),
            'is_authentic': False,
            'is_synthetic': True,
            'source_type': 'SYNTHETIC_FALLBACK'
        }

    def extract(self, date_str: str, symbol: str = "NIFTY") -> dict:
        """Main entry point: fetches cash delivery and extracts constituent breakdown."""
        rows, source_type = self.fetch_raw_rows(date_str)
        if rows:
            parsed = self.parse_constituents(rows, symbol=symbol, date_str=date_str, source_type=source_type)
            if parsed.get('constituents_analyzed', 0) >= 3:
                return parsed
        return self._generate_synthetic_constituents(symbol, date_str)


# Module convenience instance
extractor = SecBhavdataExtractor()
extract_sec_bhavdata = extractor.extract


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Section 5 Extractor: Cash Market Security-Wise Deliverables")
    parser.add_argument("--date", type=str, default="2026-11-02", help="Target trading date (YYYY-MM-DD)")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Index symbol (NIFTY / BANKNIFTY)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    res = extractor.extract(args.date, args.symbol)
    val = res.get('validation', {})
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"\n=======================================================")
        print(f" CASH MARKET EQUITY DELIVERABLES: {args.symbol} on {args.date}")
        print(f" Status: {val.get('summary_badge', 'UNKNOWN')} | Authentic: {res.get('is_authentic')}")
        print(f"=======================================================")
        print(f"Composite Cash Score: {res.get('composite_cash_score')} / 100")
        print(f"Cash Market Verdict:  {res.get('cash_verdict')}")
        print(f"Delivery Turnover:    INR {res.get('total_delivery_turnover_cr'):,.1f} Cr")
        print(f"-------------------------------------------------------")
        print(f"SYMBOL      | WEIGHT | CLOSE   | % CHG | DLV % | BEHAVIOR")
        print(f"-------------------------------------------------------")
        for sym, d in res.get('stocks', {}).items():
            print(f"{sym:<11} | {d.get('weight_pct'):>5.1f}% | {d.get('close_price'):>7.1f} | {d.get('pct_change'):>5.2f}% | {d.get('delivery_pct'):>5.1f}% | {d.get('behavior')}")
        print(f"=======================================================\n")
