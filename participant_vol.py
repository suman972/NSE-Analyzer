"""
Section 2 Extractor: participant_vol.py
=======================================
Official NSE File 2: Participant-Wise Trading Volumes (fao_participant_vol_DDMMYYYY.csv)

Extracts 14-column breakdown of daily contract trading volumes across 4 market participant classes:
- CLIENT (Retail Individuals & HNIs)
- DII (Domestic Mutual Funds, Insurance AMCs)
- FII (Foreign Institutional Investors)
- PRO (Proprietary Trading Desks & Market Makers)

Calculates the Retention Ratio:
    Retention Ratio_{p, Segment} = |Delta OI_{p, Segment}| / max(1, Volume_{p, Segment})

Microstructure Insight:
- Retention Ratio > 35%: True Institutional Position Creation (Overnight Inventory Commitment)
- Retention Ratio < 12%: Intraday Scalping / High-Frequency Churn (Positions closed before 15:30)
- Identifies exact segments where Big Players (FII + PRO) are creating structural option writing positions.

Data Quality & Authenticity Guarantee:
- Validates all 14 volume columns.
- Rejects simulated/synthetic volume generator data.
- Distinguishes authentic live/cached volume from missing intraday data.
"""

import os
import io
import csv
import re
import json
import argparse
import requests
from datetime import datetime, timedelta

from data_validator import validate_participant_vol_csv, ValidationResult

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nseindia.com/',
}

PARTICIPANT_MAP = {
    'CLIENT': ['CLIENT', 'CLIENTS', 'RETAIL', 'INDIVIDUAL'],
    'DII': ['DII', 'DOMESTIC INSTITUTIONAL INVESTORS'],
    'FII': ['FII', 'FOREIGN INSTITUTIONAL INVESTORS', 'FPI'],
    'PRO': ['PRO', 'PROPRIETARY', 'PROP'],
    'TOTAL': ['TOTAL']
}

INSTRUMENT_KEYS = [
    ('future_index_long', 'Future Index Long'),
    ('future_index_short', 'Future Index Short'),
    ('future_stock_long', 'Future Stock Long'),
    ('future_stock_short', 'Future Stock Short'),
    ('option_index_call_long', 'Option Index Call Long'),
    ('option_index_put_long', 'Option Index Put Long'),
    ('option_index_call_short', 'Option Index Call Short'),
    ('option_index_put_short', 'Option Index Put Short'),
    ('option_stock_call_long', 'Option Stock Call Long'),
    ('option_stock_put_long', 'Option Stock Put Long'),
    ('option_stock_call_short', 'Option Stock Call Short'),
    ('option_stock_put_short', 'Option Stock Put Short'),
    ('total_long_contracts', 'Total Long Contracts'),
    ('total_short_contracts', 'Total Short Contracts')
]


def clean_int(val) -> int:
    """Safely convert strings with commas, dashes, whitespace to int."""
    if val is None:
        return 0
    s = str(val).strip().replace(',', '').replace(' ', '')
    if not s or s == '-' or s.lower() == 'nan':
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


class ParticipantVolExtractor:
    """Extractor for NSE File 2: Participant-Wise Trading Volumes with Strict Validation."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_raw(self, date_str: str) -> tuple:
        """
        Retrieves raw CSV text for target date volume file.
        Returns: (raw_content: str, source_type: str)
        Sources: 'AUTHENTIC_NSE_CACHE', 'AUTHENTIC_NSE_LIVE', 'HISTORICAL_FALLBACK', 'UNAVAILABLE'
        NO SYNTHETIC VOLUME IS FABRICATED.
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%d%m%Y")
            except ValueError:
                dt = datetime.now()

        ddmmyyyy = dt.strftime("%d%m%Y")
        yyyymmdd = dt.strftime("%Y%m%d")
        cache_paths = [
            os.path.join(self.cache_dir, f"fao_participant_vol_{ddmmyyyy}.csv"),
            os.path.join(self.cache_dir, f"fao_participant_vol_{yyyymmdd}.csv")
        ]

        # 1. Local Cache check
        for cp in cache_paths:
            if os.path.exists(cp) and os.path.getsize(cp) > 100:
                with open(cp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if ("Client" in content or "CLIENT" in content) and "Realistic fallback" not in content:
                        return content, "AUTHENTIC_NSE_CACHE"

        # 2. Live NSE Download with validation
        urls = [
            f"https://archives.nseindia.com/content/nsccl/fao_participant_vol_{ddmmyyyy}.csv",
            f"https://archives.nseindia.com/content/fo/fao_participant_vol_{ddmmyyyy}.csv"
        ]
        for url in urls:
            try:
                resp = requests.get(url, headers=NSE_HEADERS, timeout=4.0)
                if resp.status_code == 200 and len(resp.text) > 200 and ("Client" in resp.text or "CLIENT" in resp.text):
                    val, _ = validate_participant_vol_csv(resp.text, date_str, source="LIVE")
                    if val.is_valid and val.is_authentic:
                        for cp in cache_paths:
                            try:
                                with open(cp, "w", encoding="utf-8") as f:
                                    f.write(resp.text)
                            except Exception:
                                pass
                        return resp.text, "AUTHENTIC_NSE_LIVE"
            except Exception:
                continue

        # 3. Check sample_files directory (offline demo mode only)
        sample_path = os.path.join(SAMPLE_DIR, f"fao_participant_vol_{ddmmyyyy}.csv")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "Client" in content:
                    return content, "SAMPLE_DEMO"

        # 4. Fallback to nearest verified historical cache
        from nse_fetcher import find_nearest_cached_date
        nearest = find_nearest_cached_date(date_str)
        if nearest and nearest != date_str:
            near_dt = datetime.strptime(nearest, "%Y-%m-%d")
            near_ddmmyyyy = near_dt.strftime("%d%m%Y")
            near_path = os.path.join(self.cache_dir, f"fao_participant_vol_{near_ddmmyyyy}.csv")
            if os.path.exists(near_path) and os.path.getsize(near_path) > 100:
                with open(near_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "Realistic fallback" not in content:
                        return content, "HISTORICAL_FALLBACK"

        return "", "UNAVAILABLE"

    def parse(self, csv_content: str, target_date_str: str = "", source_hint: str = "CACHE") -> dict:
        """Parses Volume CSV into structured records per participant with strict schema validation."""
        if not csv_content:
            val_res = ValidationResult("PARTICIPANT_VOL", target_date_str)
            val_res.errors.append("Empty or missing Volume CSV.")
            return {
                'validation': val_res.to_dict(),
                'is_authentic': False,
                'is_valid': False,
                'source_type': 'UNAVAILABLE'
            }

        val_res, validated_vol = validate_participant_vol_csv(csv_content, target_date_str, source=source_hint)

        lines = [line.strip() for line in csv_content.splitlines() if line.strip()]
        header_idx = -1
        for idx, line in enumerate(lines[:10]):
            line_upper = line.upper()
            if "FUTURE INDEX LONG" in line_upper or "CLIENT" in line_upper:
                header_idx = idx
                break

        if header_idx == -1:
            header_idx = 0

        rows = list(csv.reader(lines[header_idx:]))
        headers = [h.strip() for h in rows[0]] if rows else []
        col_map = {}
        for c_idx, col_name in enumerate(headers):
            norm = re.sub(r'[^A-Z0-9]', '', col_name.upper())
            for key, raw_label in INSTRUMENT_KEYS:
                raw_norm = re.sub(r'[^A-Z0-9]', '', raw_label.upper())
                if raw_norm in norm or norm in raw_norm:
                    col_map[key] = c_idx

        if len(col_map) < 8 and len(headers) >= 15:
            order = [
                'future_index_long', 'future_index_short',
                'future_stock_long', 'future_stock_short',
                'option_index_call_long', 'option_index_put_long',
                'option_index_call_short', 'option_index_put_short',
                'option_stock_call_long', 'option_stock_put_long',
                'option_stock_call_short', 'option_stock_put_short',
                'total_long_contracts', 'total_short_contracts'
            ]
            for idx_key, k in enumerate(order):
                col_map[k] = idx_key + 1

        participants_vol = {}
        seen_types = set()
        for row in rows[1:]:
            if not row or len(row) < 2:
                continue
            first_cell = row[0].strip().upper()
            matched_p = None
            for p_code, aliases in PARTICIPANT_MAP.items():
                if any(alias in first_cell for alias in aliases):
                    matched_p = p_code
                    break

            if not matched_p or matched_p in seen_types:
                continue
            seen_types.add(matched_p)

            def get_val(key):
                idx = col_map.get(key)
                if idx is not None and idx < len(row):
                    return clean_int(row[idx])
                return 0

            p_data = {
                'participant': matched_p,
                'future_index_long': get_val('future_index_long'),
                'future_index_short': get_val('future_index_short'),
                'future_stock_long': get_val('future_stock_long'),
                'future_stock_short': get_val('future_stock_short'),
                'option_index_call_long': get_val('option_index_call_long'),
                'option_index_put_long': get_val('option_index_put_long'),
                'option_index_call_short': get_val('option_index_call_short'),
                'option_index_put_short': get_val('option_index_put_short'),
                'option_stock_call_long': get_val('option_stock_call_long'),
                'option_stock_put_long': get_val('option_stock_put_long'),
                'option_stock_call_short': get_val('option_stock_call_short'),
                'option_stock_put_short': get_val('option_stock_put_short'),
                'total_long': get_val('total_long_contracts'),
                'total_short': get_val('total_short_contracts'),
            }

            p_data['total_volume'] = p_data['total_long'] + p_data['total_short']
            p_data['index_futures_vol'] = p_data['future_index_long'] + p_data['future_index_short']
            p_data['stock_futures_vol'] = p_data['future_stock_long'] + p_data['future_stock_short']
            p_data['index_calls_vol'] = p_data['option_index_call_long'] + p_data['option_index_call_short']
            p_data['index_puts_vol'] = p_data['option_index_put_long'] + p_data['option_index_put_short']

            participants_vol[matched_p] = p_data

        participants_vol['validation'] = val_res.to_dict()
        participants_vol['is_authentic'] = val_res.is_authentic
        participants_vol['is_valid'] = val_res.is_valid
        participants_vol['source_type'] = val_res.source_type
        return participants_vol

    def extract(self, date_str: str) -> dict:
        """Main entry point: fetches raw CSV and parses it for a single date."""
        raw_csv, source_type = self.fetch_raw(date_str)
        return self.parse(raw_csv, target_date_str=date_str, source_hint=source_type)


def compute_retention(deltas: dict, vol_data: dict) -> dict:
    """
    Computes the Microstructure Retention Ratio:
        Retention Ratio_{p, Segment} = |Delta OI_{p, Segment}| / max(1, Volume_{p, Segment})
    """
    ratios = {}
    is_vol_authentic = vol_data.get('is_authentic', False)
    val_info = vol_data.get('validation', {})

    for p in ['CLIENT', 'DII', 'FII', 'PRO']:
        p_d = deltas.get(p, {})
        p_v = vol_data.get(p, {})

        if not p_v or not is_vol_authentic:
            # Volume unavailable: do not invent fake retention
            ratios[p] = {
                'index_futures': {'ratio': 0.0, 'label': 'No Authentic Volume', 'is_positional': False},
                'index_calls':   {'ratio': 0.0, 'label': 'No Authentic Volume', 'is_positional': False},
                'index_puts':    {'ratio': 0.0, 'label': 'No Authentic Volume', 'is_positional': False},
                'stock_futures': {'ratio': 0.0, 'label': 'No Authentic Volume', 'is_positional': False},
                'composite':     {'avg_retention': 0.0, 'conviction_tag': 'DATA_UNAVAILABLE'}
            }
            continue

        def calc_seg(d_oi, vol):
            v_safe = max(1, vol)
            ratio = round(abs(d_oi) / v_safe, 4)
            pct = round(ratio * 100, 1)
            if ratio >= 0.35:
                label = f"True Institutional Positioning ({pct}%)"
                is_pos = True
            elif ratio <= 0.12:
                label = f"Intraday Scalping Churn ({pct}%)"
                is_pos = False
            else:
                label = f"Mixed Positioning ({pct}%)"
                is_pos = False
            return {'ratio': ratio, 'pct': pct, 'label': label, 'is_positional': is_pos, 'delta_oi': d_oi, 'volume': vol}

        seg_fut = calc_seg(p_d.get('delta_index_futures', 0), p_v.get('index_futures_vol', 0))
        seg_call = calc_seg(p_d.get('delta_index_calls', 0), p_v.get('index_calls_vol', 0))
        seg_put = calc_seg(p_d.get('delta_index_puts', 0), p_v.get('index_puts_vol', 0))
        seg_stk = calc_seg(p_d.get('delta_stock_futures', 0), p_v.get('stock_futures_vol', 0))

        avg_ret = round((seg_fut['ratio'] + seg_call['ratio'] + seg_put['ratio'] + seg_stk['ratio']) / 4.0, 4)
        ratios[p] = {
            'index_futures': seg_fut,
            'index_calls': seg_call,
            'index_puts': seg_put,
            'stock_futures': seg_stk,
            'composite': {
                'avg_retention': avg_ret,
                'conviction_tag': 'HIGH_INSTITUTIONAL' if avg_ret >= 0.25 else ('SCALPING' if avg_ret < 0.10 else 'MODERATE')
            }
        }

    ratios['is_authentic'] = is_vol_authentic
    ratios['validation'] = val_info
    return ratios


# Module convenience instance
extractor = ParticipantVolExtractor()
extract_participant_vol = extractor.extract


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Section 2 Extractor: Participant-Wise Trading Volumes")
    parser.add_argument("--date", type=str, default="2026-11-02", help="Target trading date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    res = extractor.extract(args.date)
    val = res.get('validation', {})
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"\n=======================================================")
        print(f" NSE PARTICIPANT TRADING VOLUMES: {args.date}")
        print(f" Status: {val.get('summary_badge', 'UNKNOWN')} | Authentic: {res.get('is_authentic')}")
        print(f"=======================================================")
        for p in ['FII', 'PRO', 'CLIENT', 'DII']:
            d = res.get(p, {})
            print(f"{p:<8} | Total Vol: {d.get('total_volume', 0):>12,} | Fut Vol: {d.get('index_futures_vol', 0):>10,} | Call Vol: {d.get('index_calls_vol', 0):>10,}")
        print(f"=======================================================\n")
