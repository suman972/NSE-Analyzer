"""
Section 4 Extractor: udiff_bhavcopy.py
======================================
Official NSE File 4: UDiFF Common Bhavcopy Final
(BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip / fo{DDMMMYYYY}bhav.csv.zip)

Replaces legacy fo.zip with modern official NSE UDiFF standard.
Extracts:
- Strike-by-strike settlement prices, open interest (OI), Delta OI, traded volume, implied volatility (IV).
- Spot price, ATM strike, Max Pain strike.
- Primary Call Writing Wall (R1 Resistance), Secondary Call Wall (R2).
- Primary Put Writing Wall (S1 Support), Secondary Put Wall (S2).
- Put-Call Ratio (PCR by OI and Volume).
- Volatility Corridor: Expected daily move, +/- 1 SD and +/- 2 SD boundaries.

Data Quality & Authenticity Guarantee:
- Verifies zip archive integrity (uncorrupted, > 10KB).
- Verifies trading date (TradDt / BizDt) matches requested session.
- Verifies UDiFF FO schema and mandatory strike columns.
- Prevents synthetic option chain fallbacks from contaminating real quantitative predictions.
"""

import os
import io
import csv
import zipfile
import math
import json
import argparse
import requests
from datetime import datetime

from data_validator import validate_bhavcopy_archive, ValidationResult

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nseindia.com/',
}


class UDiFFBhavcopyExtractor:
    """Extractor for NSE File 4: Official UDiFF Common Bhavcopy with Strict Validation."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_raw_zip(self, date_str: str) -> tuple:
        """
        Retrieves raw Bhavcopy zip bytes and validation result.
        Returns (success_bool, zip_bytes, ValidationResult).
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%d%m%Y")
            except ValueError:
                dt = datetime.now()

        date_code = dt.strftime("%Y%m%d")
        ddmmyyyy = dt.strftime("%d%m%Y")
        cache_paths = [
            os.path.join(self.cache_dir, f"bhavcopy_{date_code}.zip"),
            os.path.join(self.cache_dir, f"bhavcopy_{ddmmyyyy}.zip")
        ]

        # 1. Local Cache check
        for cp in cache_paths:
            if os.path.exists(cp) and os.path.getsize(cp) > 10000:
                with open(cp, "rb") as f:
                    b = f.read()
                    val, _ = validate_bhavcopy_archive(b, date_str, source="CACHE")
                    if val.is_valid:
                        return True, b, val

        # 2. Live NSE Download
        urls = [
            f"https://archives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_code}_F_0000.csv.zip",
            f"https://archives.nseindia.com/content/historical/DERIVATIVES/{dt.year}/{dt.strftime('%b').upper()}/fo{dt.strftime('%d%b%Y').upper()}bhav.csv.zip",
            f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_code}_F_0000.csv.zip"
        ]

        for url in urls:
            try:
                resp = requests.get(url, headers=NSE_HEADERS, timeout=4.0)
                if resp.status_code == 200 and len(resp.content) > 10000:
                    val, _ = validate_bhavcopy_archive(resp.content, date_str, source="LIVE")
                    if val.is_valid:
                        for cp in cache_paths:
                            try:
                                with open(cp, "wb") as f:
                                    f.write(resp.content)
                            except Exception:
                                pass
                        return True, resp.content, val
            except Exception:
                continue

        # 3. Fallback to nearest historical cache
        from nse_fetcher import find_nearest_cached_date
        nearest = find_nearest_cached_date(date_str)
        if nearest and nearest != date_str:
            near_dt = datetime.strptime(nearest, "%Y-%m-%d")
            near_code = near_dt.strftime("%Y%m%d")
            near_path = os.path.join(self.cache_dir, f"bhavcopy_{near_code}.zip")
            if os.path.exists(near_path) and os.path.getsize(near_path) > 10000:
                with open(near_path, "rb") as f:
                    b = f.read()
                    val, _ = validate_bhavcopy_archive(b, nearest, source="HISTORICAL_FALLBACK")
                    val.source_type = "HISTORICAL_FALLBACK"
                    return True, b, val

        val_err = ValidationResult("BHAVCOPY_FO", date_str)
        val_err.errors.append("Bhavcopy archive not found in cache or live NSE archives.")
        return False, None, val_err

    def extract(self, date_str: str, symbol: str = "NIFTY", expiry: str = None, participant_data: dict = None) -> dict:
        """
        Main extraction routine:
        Parses option chain and computes all quantitative metrics.
        """
        symbol = (symbol or "NIFTY").strip().upper()
        ok, zip_bytes, val_res = self.fetch_raw_zip(date_str)

        try:
            from option_chain_engine import get_option_chain_data
            oc_data = get_option_chain_data(
                date_str=date_str,
                symbol=symbol,
                expiry_date=expiry,
                window=25,
                participant_data=participant_data
            )
            if oc_data and oc_data.get('strikes'):
                oc_data['validation'] = val_res.to_dict()
                oc_data['is_authentic'] = val_res.is_authentic
                oc_data['is_valid'] = val_res.is_valid
                oc_data['source_type'] = val_res.source_type
                return oc_data
        except Exception:
            pass

        # Native fallback synthesis if engine module not invoked (FLAGGED AS SYNTHETIC)
        fallback = self._build_synthetic_option_chain(date_str, symbol)
        val_syn = ValidationResult("BHAVCOPY_FO", date_str)
        val_syn.is_synthetic = True
        val_syn.is_authentic = False
        val_syn.is_valid = False
        val_syn.source_type = "SYNTHETIC_FALLBACK"
        fallback['validation'] = val_syn.to_dict()
        fallback['is_authentic'] = False
        fallback['is_synthetic'] = True
        return fallback

    def _build_synthetic_option_chain(self, date_str: str, symbol: str) -> dict:
        """Constructs a baseline option chain structure (clearly tagged synthetic)."""
        spot = 25057.35 if symbol == "NIFTY" else (51800.0 if symbol == "BANKNIFTY" else 23900.0)
        strike_step = 50.0 if symbol == "NIFTY" else 100.0
        atm = round(spot / strike_step) * strike_step

        s1_strike = atm - (50.0 if symbol == "NIFTY" else 300.0)
        s2_strike = s1_strike - (100.0 if symbol == "NIFTY" else 500.0)
        r1_strike = atm + (150.0 if symbol == "NIFTY" else 400.0)
        r2_strike = r1_strike + (300.0 if symbol == "NIFTY" else 600.0)

        iv_pct = 12.6
        daily_move = round(spot * (iv_pct / 100.0) / math.sqrt(252), 1)

        return {
            'status': 'synthetic_estimate',
            'symbol': symbol,
            'date': date_str,
            'spot_price': spot,
            'atm_strike': atm,
            'max_pain': atm,
            'pcr': 0.68,
            'pcr_stance': 'Mildly Bearish / Call Writing Dominance',
            'pcr_color': 'red',
            'major_support': {'strike': s1_strike, 'oi': 1254000, 'holding_prob': 86},
            'secondary_support': {'strike': s2_strike, 'oi': 980000, 'holding_prob': 98},
            'major_resistance': {'strike': r1_strike, 'oi': 1850000, 'holding_prob': 89},
            'secondary_resistance': {'strike': r2_strike, 'oi': 1420000, 'holding_prob': 98},
            'expected_daily_move': daily_move,
            'sd1_corridor': {'low': round(spot - daily_move, 1), 'high': round(spot + daily_move, 1)},
            'sd2_corridor': {'low': round(spot - 2 * daily_move, 1), 'high': round(spot + 2 * daily_move, 1)},
            'is_authentic': False,
            'is_synthetic': True
        }


# Module convenience instance
extractor = UDiFFBhavcopyExtractor()
extract_udiff_bhavcopy = extractor.extract


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Section 4 Extractor: Official UDiFF FO Bhavcopy")
    parser.add_argument("--date", type=str, default="2026-11-02", help="Target trading date (YYYY-MM-DD)")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Index symbol (NIFTY / BANKNIFTY / FINNIFTY)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    res = extractor.extract(args.date, args.symbol)
    val = res.get('validation', {})
    if args.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        print(f"\n=======================================================")
        print(f" NSE UDIFF OPTION CHAIN EXTRACTOR: {args.symbol} on {args.date}")
        print(f" Status: {val.get('summary_badge', 'UNKNOWN')} | Authentic: {res.get('is_authentic')}")
        print(f"=======================================================")
        print(f"Spot Price:       {res.get('spot_price', 0):,.2f}")
        print(f"ATM Strike:       {res.get('atm_strike', 0):,.0f}")
        print(f"Max Pain Strike:  {res.get('max_pain', 0):,.0f}")
        print(f"PCR:              {res.get('pcr', 0):.2f} ({res.get('pcr_stance', '')})")
        sup = res.get('major_support', {})
        res_k = res.get('major_resistance', {})
        print(f"Primary Support:  {sup.get('strike', 0):,.0f} (Holding Prob: {sup.get('holding_prob', 0)}%)")
        print(f"Primary Resist:   {res_k.get('strike', 0):,.0f} (Holding Prob: {res_k.get('holding_prob', 0)}%)")
        print(f"Expected Move:    ± {res.get('expected_daily_move', 0):.1f} Pts")
        print(f"=======================================================\n")
