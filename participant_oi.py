"""
Section 1 Extractor: participant_oi.py
=======================================
Official NSE File 1: Participant-Wise Open Interest (fao_participant_oi_DDMMYYYY.csv)

Extracts 14-column breakdown of open interest across 4 market participant classes:
- CLIENT (Retail Individuals & HNIs)
- DII (Domestic Mutual Funds, Insurance AMCs)
- FII (Foreign Institutional Investors)
- PRO (Proprietary Trading Desks & Market Makers)

Provides:
- Exact contract holdings in Index Futures, Stock Futures, Index Calls, Index Puts, Stock Calls, Stock Puts
- Net positions (Long - Short)
- Long/Short ratios
- Multi-day sequential delta change (Delta OI)
- Smart Money vs Retail Skew
- Strict Data Quality & Zero-Sum Derivatives Verification (Total Long == Total Short)
"""

import os
import io
import csv
import re
import json
import argparse
import requests
from datetime import datetime, timedelta

from data_validator import validate_participant_oi_csv, ValidationResult

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nseindia.com/',
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

PARTICIPANT_MAP = {
    'CLIENT': ['CLIENT', 'CLIENTS', 'RETAIL', 'INDIVIDUAL'],
    'DII': ['DII', 'DOMESTIC INSTITUTIONAL INVESTORS'],
    'FII': ['FII', 'FOREIGN INSTITUTIONAL INVESTORS', 'FPI'],
    'PRO': ['PRO', 'PROPRIETARY', 'PROP'],
    'TOTAL': ['TOTAL']
}


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


class ParticipantOIExtractor:
    """Extractor for NSE File 1: Participant-Wise Open Interest with Strict Validation."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_path(self, date_str: str) -> str:
        """Returns path to cached participant OI CSV."""
        clean_date = date_str.replace('-', '')
        if len(clean_date) == 8 and clean_date[:4].isdigit() and int(clean_date[:4]) > 1900:
            clean_date = f"{clean_date[6:8]}{clean_date[4:6]}{clean_date[:4]}"
        return os.path.join(self.cache_dir, f"fao_participant_oi_{clean_date}.csv")

    def fetch_raw(self, date_str: str) -> tuple:
        """
        Retrieves raw CSV text for target date with source provenance.
        Returns: (raw_content: str, source_type: str)
        Sources: 'AUTHENTIC_NSE_CACHE', 'AUTHENTIC_NSE_LIVE', 'HISTORICAL_FALLBACK', 'UNAVAILABLE'
        NO SILENT SYNTHETIC DATA IS GENERATED.
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
            os.path.join(self.cache_dir, f"fao_participant_oi_{ddmmyyyy}.csv"),
            os.path.join(self.cache_dir, f"fao_participant_oi_{yyyymmdd}.csv")
        ]

        # 1. Local Cache check with validation
        for cp in cache_paths:
            if os.path.exists(cp) and os.path.getsize(cp) > 100:
                with open(cp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "Client" in content or "CLIENT" in content:
                        return content, "AUTHENTIC_NSE_CACHE"

        # 2. Live NSE Download with immediate validation before saving
        urls = [
            f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{ddmmyyyy}.csv",
            f"https://archives.nseindia.com/content/fo/fao_participant_oi_{ddmmyyyy}.csv"
        ]
        for url in urls:
            try:
                resp = requests.get(url, headers=NSE_HEADERS, timeout=4.0)
                if resp.status_code == 200 and len(resp.text) > 200 and ("Client" in resp.text or "CLIENT" in resp.text):
                    # Validate before caching
                    val, _ = validate_participant_oi_csv(resp.text, date_str, source="LIVE")
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

        # 3. Check sample_files directory (for offline demo mode ONLY)
        sample_path = os.path.join(SAMPLE_DIR, f"fao_participant_oi_{ddmmyyyy}.csv")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), "SAMPLE_DEMO"

        # 4. If requested date has no data, search nearest verified historical cache
        from nse_fetcher import find_nearest_cached_date
        nearest = find_nearest_cached_date(date_str)
        if nearest and nearest != date_str:
            near_clean = nearest.replace('-', '')
            near_dt = datetime.strptime(nearest, "%Y-%m-%d")
            near_ddmmyyyy = near_dt.strftime("%d%m%Y")
            near_path = os.path.join(self.cache_dir, f"fao_participant_oi_{near_ddmmyyyy}.csv")
            if os.path.exists(near_path) and os.path.getsize(near_path) > 100:
                with open(near_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(), "HISTORICAL_FALLBACK"

        return "", "UNAVAILABLE"

    def parse(self, csv_content: str, target_date_str: str = "", source_hint: str = "CACHE") -> dict:
        """
        Parses CSV string and applies strict validation, schema checks, and zero-sum verification.
        Returns full participant intelligence dictionary with embedded validation report.
        """
        if not csv_content:
            res_val = ValidationResult("PARTICIPANT_OI", target_date_str)
            res_val.errors.append("Empty or missing CSV content.")
            return {
                'date': target_date_str,
                'participants': {},
                'smart_money': {},
                'retail_trap': {},
                'validation': res_val.to_dict(),
                'is_authentic': False,
                'is_valid': False,
                'raw_lines_count': 0
            }

        # Run strict validation
        val_res, validated_rows = validate_participant_oi_csv(csv_content, target_date_str, source=source_hint)

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

        participants = {}
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

            p_data['index_futures_net'] = p_data['future_index_long'] - p_data['future_index_short']
            p_data['stock_futures_net'] = p_data['future_stock_long'] - p_data['future_stock_short']
            p_data['index_calls_net'] = p_data['option_index_call_long'] - p_data['option_index_call_short']
            p_data['index_puts_net'] = p_data['option_index_put_long'] - p_data['option_index_put_short']
            p_data['stock_calls_net'] = p_data['option_stock_call_long'] - p_data['option_stock_call_short']
            p_data['stock_puts_net'] = p_data['option_stock_put_long'] - p_data['option_stock_put_short']
            p_data['total_net'] = p_data['total_long'] - p_data['total_short']

            p_data['index_call_long_short_ratio'] = round(p_data['option_index_call_long'] / max(1, p_data['option_index_call_short']), 2)
            p_data['index_put_long_short_ratio'] = round(p_data['option_index_put_long'] / max(1, p_data['option_index_put_short']), 2)
            p_data['future_index_long_short_ratio'] = round(p_data['future_index_long'] / max(1, p_data['future_index_short']), 2)

            participants[matched_p] = p_data

        fii = participants.get('FII', {})
        pro = participants.get('PRO', {})
        client = participants.get('CLIENT', {})

        smart_money = {
            'index_futures_net': fii.get('index_futures_net', 0) + pro.get('index_futures_net', 0),
            'stock_futures_net': fii.get('stock_futures_net', 0) + pro.get('stock_futures_net', 0),
            'index_calls_net': fii.get('index_calls_net', 0) + pro.get('index_calls_net', 0),
            'index_puts_net': fii.get('index_puts_net', 0) + pro.get('index_puts_net', 0),
            'call_writing_dominance': (fii.get('index_calls_net', 0) + pro.get('index_calls_net', 0)) < -25000,
            'put_writing_dominance': (fii.get('index_puts_net', 0) + pro.get('index_puts_net', 0)) < -25000,
            'net_call_delta': fii.get('index_calls_net', 0) + pro.get('index_calls_net', 0),
            'net_put_delta': fii.get('index_puts_net', 0) + pro.get('index_puts_net', 0),
        }

        retail_trap = {
            'is_trapped_long_calls': client.get('index_calls_net', 0) > 40000 and smart_money['index_calls_net'] < 0,
            'is_trapped_long_puts': client.get('index_puts_net', 0) > 40000 and smart_money['index_puts_net'] < 0,
            'is_trapped_short_puts': client.get('index_puts_net', 0) < -40000 and smart_money['index_puts_net'] > 0,
            'client_call_net': client.get('index_calls_net', 0),
            'client_put_net': client.get('index_puts_net', 0),
        }

        return {
            'date': target_date_str or val_res.detected_date,
            'participants': participants,
            'smart_money': smart_money,
            'retail_trap': retail_trap,
            'raw_lines_count': len(lines),
            'validation': val_res.to_dict(),
            'is_authentic': val_res.is_authentic,
            'is_valid': val_res.is_valid,
            'source_type': val_res.source_type,
            'zero_sum_balanced': val_res.zero_sum_balanced
        }

    def extract(self, date_str: str) -> dict:
        """Main entry point: fetches raw CSV and parses it for a single date."""
        raw_csv, source_type = self.fetch_raw(date_str)
        return self.parse(raw_csv, target_date_str=date_str, source_hint=source_type)

    def extract_multi_day(self, target_date_str: str, days: int = 5) -> dict:
        """
        Extracts multi-day sequential participant data to compute Delta OI (daily changes).
        Maintains historical authentic sessions.
        """
        try:
            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        except ValueError:
            target_dt = datetime.now()

        daily_records = []
        cur_dt = target_dt
        while len(daily_records) < days and (target_dt - cur_dt).days < 25:
            if cur_dt.weekday() < 5:
                d_str = cur_dt.strftime("%Y-%m-%d")
                rec = self.extract(d_str)
                if rec and rec.get('participants') and rec.get('is_valid', True):
                    daily_records.append(rec)
            cur_dt -= timedelta(days=1)

        daily_records.reverse()

        enriched_history = []
        for i, curr in enumerate(daily_records):
            if i == 0:
                curr_copy = dict(curr)
                curr_copy['deltas'] = {}
                enriched_history.append(curr_copy)
                continue

            prev = daily_records[i - 1]
            deltas = {}
            for p_key in ['CLIENT', 'DII', 'FII', 'PRO', 'TOTAL']:
                p_curr = curr['participants'].get(p_key, {})
                p_prev = prev['participants'].get(p_key, {})
                deltas[p_key] = {
                    'delta_index_futures': p_curr.get('index_futures_net', 0) - p_prev.get('index_futures_net', 0),
                    'delta_stock_futures': p_curr.get('stock_futures_net', 0) - p_prev.get('stock_futures_net', 0),
                    'delta_index_calls': p_curr.get('index_calls_net', 0) - p_prev.get('index_calls_net', 0),
                    'delta_index_puts': p_curr.get('index_puts_net', 0) - p_prev.get('index_puts_net', 0),
                    'delta_stock_calls': p_curr.get('stock_calls_net', 0) - p_prev.get('stock_calls_net', 0),
                    'delta_stock_puts': p_curr.get('stock_puts_net', 0) - p_prev.get('stock_puts_net', 0),
                    'call_long_chg': p_curr.get('option_index_call_long', 0) - p_prev.get('option_index_call_long', 0),
                    'call_short_chg': p_curr.get('option_index_call_short', 0) - p_prev.get('option_index_call_short', 0),
                    'put_long_chg': p_curr.get('option_index_put_long', 0) - p_prev.get('option_index_put_long', 0),
                    'put_short_chg': p_curr.get('option_index_put_short', 0) - p_prev.get('option_index_put_short', 0),
                }

            curr_copy = dict(curr)
            curr_copy['deltas'] = deltas
            enriched_history.append(curr_copy)

        latest_record = enriched_history[-1] if enriched_history else {}
        return {
            'status': 'success' if enriched_history else 'failed',
            'target_date': target_date_str,
            'sessions_count': len(enriched_history),
            'history': enriched_history,
            'latest': latest_record,
            'validation': latest_record.get('validation', {}),
            'is_authentic': latest_record.get('is_authentic', False)
        }


# Module convenience instance
extractor = ParticipantOIExtractor()
extract_participant_oi = extractor.extract
extract_multi_day_oi = extractor.extract_multi_day


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Section 1 Extractor: Participant-Wise Open Interest")
    parser.add_argument("--date", type=str, default="2026-11-02", help="Target trading date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=5, help="Number of lookback trading days")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    res = extractor.extract_multi_day(args.date, args.days)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        latest = res.get('latest', {})
        p = latest.get('participants', {})
        sm = latest.get('smart_money', {})
        val = res.get('validation', {})
        print(f"\n=======================================================")
        print(f" NSE PARTICIPANT-WISE OPEN INTEREST: {args.date}")
        print(f" Status: {val.get('summary_badge', 'UNKNOWN')} | Zero-Sum: {val.get('zero_sum_balanced')}")
        print(f"=======================================================")
        print(f"PARTICIPANT | IDX FUTURES | IDX CALLS NET | IDX PUTS NET")
        print(f"-------------------------------------------------------")
        for code in ['FII', 'PRO', 'CLIENT', 'DII']:
            d = p.get(code, {})
            print(f"{code:<11} | {d.get('index_futures_net', 0):>11,} | {d.get('index_calls_net', 0):>13,} | {d.get('index_puts_net', 0):>12,}")
        print(f"=======================================================\n")
