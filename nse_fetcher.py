import os
import io
import csv
import zipfile
import glob
import re
import requests
from datetime import datetime, timedelta
from oi_engine import parse_csv, calculate_multi_day_oi
from generate_samples import generate_sample_data, create_csv_files

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nseindia.com/',
}

# ---------------------------------------------------------------------------
# File 2: Participant-Wise Trading Volumes (fao_participant_vol_DDMMYYYY.csv)
# ---------------------------------------------------------------------------

def fetch_participant_vol(dt: datetime) -> dict:
    """
    Fetches File 2 — Participant-Wise TRADING VOLUMES for a given date.
    Returns a dict keyed by participant with the same 14-column structure
    as File 1 but representing intraday traded volume instead of OI.
    Falls back gracefully to empty dict if not available.
    """
    date_code = dt.strftime("%d%m%Y")
    cache_path = os.path.join(CACHE_DIR, f"fao_participant_vol_{date_code}.csv")

    # Try cache first
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content and len(content) > 100:
            return _parse_vol_csv(content)

    # Attempt live NSE download
    urls = [
        f"https://archives.nseindia.com/content/nsccl/fao_participant_vol_{date_code}.csv",
        f"https://archives.nseindia.com/content/fo/fao_participant_vol_{date_code}.csv",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=NSE_HEADERS, timeout=8)
            if r.status_code == 200 and len(r.text) > 200 and "Client" in r.text:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(r.text)
                return _parse_vol_csv(r.text)
        except Exception:
            continue

    return {}


def _parse_vol_csv(content: str) -> dict:
    """Parse participant-wise volume CSV (same structure as OI CSV)."""
    from oi_engine import parse_csv as _parse_csv
    rec = _parse_csv(content, "vol_file.csv")
    return rec.get("data", {})


# ---------------------------------------------------------------------------
# File 3: FII Derivatives Statistics (fii_stats_DD-MMM-YYYY.xls)
# ---------------------------------------------------------------------------

def fetch_fii_stats(dt: datetime) -> dict:
    """
    Fetches File 3 — FII Derivatives Statistics XLS, which breaks down
    FII OI separately for NIFTY, BANKNIFTY, FINNIFTY, and MIDCPNIFTY.

    Returns a dict keyed by index name with FII Futures and Options data.
    Falls back to empty dict if unavailable (NSE blocks automated download).
    """
    date_str_dash = dt.strftime("%d-%b-%Y").upper()  # e.g. 25-OCT-2024
    date_code     = dt.strftime("%d%m%Y")
    cache_path    = os.path.join(CACHE_DIR, f"fii_stats_{date_code}.json")

    # Use cached JSON if available
    if os.path.exists(cache_path):
        import json
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                pass

    # Try fetching XLS from NSE
    urls = [
        f"https://archives.nseindia.com/content/fo/fii_stats_{date_str_dash}.xls",
        f"https://www.nseindia.com/api/fiiderivativesStats?type=day&dateStr={dt.strftime('%Y-%m-%d')}",
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=NSE_HEADERS, timeout=10)
            if r.status_code == 200 and len(r.content) > 500:
                parsed = _parse_fii_stats_bytes(r.content, url)
                if parsed:
                    import json
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(parsed, f)
                    return parsed
        except Exception:
            continue

    return {}


def _parse_fii_stats_bytes(content: bytes, url: str) -> dict:
    """
    Parses FII Statistics from XLS bytes or JSON API response.
    Returns dict keyed by index symbol.
    """
    result = {}

    # Try JSON API response first
    if b'"data"' in content or b'"NIFTY"' in content:
        import json
        try:
            j = json.loads(content)
            rows = j.get("data", j) if isinstance(j, dict) else j
            if isinstance(rows, list):
                for row in rows:
                    idx = str(row.get("underlying", row.get("index", ""))).upper().strip()
                    idx = idx.replace(" ", "").replace("50", "")  # Normalize
                    if not idx:
                        continue
                    result[idx] = {
                        "fut_buy_contracts": int(row.get("futBuyContracts", row.get("buy_contracts", 0)) or 0),
                        "fut_sell_contracts": int(row.get("futSellContracts", row.get("sell_contracts", 0)) or 0),
                        "fut_oi": int(row.get("futOI", row.get("oi", 0)) or 0),
                        "opt_buy_contracts": int(row.get("optBuyContracts", 0) or 0),
                        "opt_sell_contracts": int(row.get("optSellContracts", 0) or 0),
                        "opt_oi": int(row.get("optOI", 0) or 0),
                    }
            return result
        except Exception:
            pass

    # Try XLS parsing with xlrd if available
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=content)
        ws = wb.sheet_by_index(0)
        for row_idx in range(ws.nrows):
            row = [str(ws.cell_value(row_idx, c)).strip() for c in range(ws.ncols)]
            idx_name = row[0].upper() if row else ""
            for known in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
                if known in idx_name:
                    try:
                        nums = [int(float(v.replace(",", ""))) for v in row[1:] if v.replace(",", "").replace(".", "").lstrip("-").isdigit()]
                        if len(nums) >= 3:
                            result[known] = {
                                "fut_buy_contracts":  nums[0] if len(nums) > 0 else 0,
                                "fut_sell_contracts": nums[1] if len(nums) > 1 else 0,
                                "fut_oi":             nums[2] if len(nums) > 2 else 0,
                                "opt_buy_contracts":  nums[3] if len(nums) > 3 else 0,
                                "opt_sell_contracts": nums[4] if len(nums) > 4 else 0,
                                "opt_oi":             nums[5] if len(nums) > 5 else 0,
                            }
                    except Exception:
                        pass
    except ImportError:
        pass
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# File 4: UDiFF Common Bhavcopy Final
#          (BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip)
#          Replaces legacy/empty 0 KB fo.zip with modern NSE format
# ---------------------------------------------------------------------------

def fetch_udiff_bhavcopy(dt: datetime) -> tuple:
    """
    Fetches File 4 — Official NSE UDiFF Common Bhavcopy Final ZIP for a given date.
    Replaces the legacy 0 KB fo.zip with the modern UDiFF format.
    Returns (success_bool, zip_bytes). Caches locally.
    """
    date_code = dt.strftime("%Y%m%d")
    cache_path = os.path.join(CACHE_DIR, f"bhavcopy_{date_code}.zip")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 10000:
        with open(cache_path, "rb") as f:
            return True, f.read()

    urls = [
        f"https://archives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_code}_F_0000.csv.zip",
        f"https://archives.nseindia.com/content/historical/DERIVATIVES/{dt.year}/{dt.strftime('%b').upper()}/fo{dt.strftime('%d%b%Y').upper()}bhav.csv.zip"
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=NSE_HEADERS, timeout=12)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(cache_path, "wb") as f:
                    f.write(r.content)
                return True, r.content
        except Exception:
            continue

    return False, None


# ---------------------------------------------------------------------------
# File 5: Cash Market Security-Wise Deliverable Positions
#          (sec_bhavdata_full_DDMMYYYY.csv)
# ---------------------------------------------------------------------------

def fetch_cash_delivery_data(dt: datetime) -> list:
    """
    Fetches File 5 — Cash Market Delivery data for a given date.
    Returns a list of row dicts. Falls back to empty list if unavailable.
    Caches locally as CSV.
    """
    date_code  = dt.strftime("%d%m%Y")
    cache_path = os.path.join(CACHE_DIR, f"sec_bhavdata_{date_code}.csv")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000:
        with open(cache_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    urls = [
        f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_code}.csv",
        f"https://archives.nseindia.com/content/cm/sec_bhavdata_full_{date_code}.csv",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=NSE_HEADERS, timeout=12)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(cache_path, "wb") as f:
                    f.write(r.content)
                text = r.content.decode("utf-8", errors="ignore")
                return list(csv.DictReader(io.StringIO(text)))
        except Exception:
            continue

    return []


# ---------------------------------------------------------------------------
# Retention Ratio helper (used by oi_engine upgrade)
# ---------------------------------------------------------------------------

def compute_retention_ratio(oi_data: dict, vol_data: dict) -> dict:
    """
    Retention Ratio_{p, Segment} = |OI_{T} - OI_{T-1}| / max(1, Volume_{p,T})
    > 0.20 → sticky overnight positions built for tomorrow
    < 0.08 → mostly intraday scalping

    oi_data and vol_data are dicts keyed by participant with instrument sub-dicts.
    """
    ratios = {}
    participants = ["Client", "DII", "FII", "Pro"]
    instruments  = ["Index Futures", "Index Calls", "Index Puts", "Stock Futures"]

    for p in participants:
        ratios[p] = {}
        p_oi  = oi_data.get(p, {})
        p_vol = vol_data.get(p, {})
        for inst in instruments:
            oi_l  = p_oi.get(inst, {}).get("long",  0)
            oi_s  = p_oi.get(inst, {}).get("short", 0)
            vol_l = p_vol.get(inst, {}).get("long",  0)
            vol_s = p_vol.get(inst, {}).get("short", 0)

            delta_l  = abs(oi_l)
            delta_s  = abs(oi_s)
            total_vol = max(1, vol_l + vol_s)

            retention = (delta_l + delta_s) / total_vol
            ratios[p][inst] = {
                "ratio":      round(retention, 4),
                "label":      "Sticky Overnight" if retention > 0.20 else ("Intraday Scalping" if retention < 0.08 else "Mixed"),
                "is_sticky":  retention > 0.20,
                "is_intraday": retention < 0.08,
            }

    return ratios

def get_available_cached_dates() -> list:
    """Returns sorted list of distinct available session dates (YYYY-MM-DD) from local cache."""
    dates = set()
    files = glob.glob(os.path.join(CACHE_DIR, "fao_participant_oi_*.csv"))
    for f in files:
        b = os.path.basename(f)
        m = re.search(r"fao_participant_oi_(\d{8})\.csv", b)
        if m:
            raw = m.group(1)
            for fmt in ['%Y%m%d', '%d%m%Y']:
                try:
                    dt = datetime.strptime(raw, fmt)
                    dates.add(dt.strftime("%Y-%m-%d"))
                    break
                except ValueError:
                    pass
    return sorted(list(dates))


def find_nearest_cached_date(target_date_str: str) -> str:
    """Finds the chronologically closest available session in cache for target_date_str."""
    avail = get_available_cached_dates()
    if not avail:
        return "2026-10-30"
    if target_date_str in avail:
        return target_date_str
    try:
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    except Exception:
        return avail[-1]

    # Find closest date
    best = None
    min_diff = 999999
    for d in avail:
        try:
            cur_dt = datetime.strptime(d, "%Y-%m-%d")
            diff = abs((cur_dt - target_dt).days)
            if diff < min_diff:
                min_diff = diff
                best = d
        except Exception:
            continue
    return best or avail[-1]


def get_cached_file(date_str):
    """Check if date CSV is already cached locally in any standard format (YYYYMMDD or DDMMYYYY)."""
    clean_iso = date_str.replace('-', '')
    paths = [
        os.path.join(CACHE_DIR, f"fao_participant_oi_{clean_iso}.csv")
    ]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        paths.append(os.path.join(CACHE_DIR, f"fao_participant_oi_{dt.strftime('%d%m%Y')}.csv"))
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%d%m%Y")
            paths.append(os.path.join(CACHE_DIR, f"fao_participant_oi_{dt.strftime('%Y%m%d')}.csv"))
        except Exception:
            pass

    for path in paths:
        if os.path.exists(path) and os.path.getsize(path) > 100:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "Client" in content or "CLIENT" in content:
                        return content
            except Exception:
                continue
    return None


def save_to_cache(date_str, content):
    """Saves date CSV to cache in both ISO (YYYYMMDD) and NSE archive (DDMMYYYY) format."""
    clean_iso = date_str.replace('-', '')
    try:
        p1 = os.path.join(CACHE_DIR, f"fao_participant_oi_{clean_iso}.csv")
        with open(p1, "w", encoding="utf-8") as f:
            f.write(content)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        p2 = os.path.join(CACHE_DIR, f"fao_participant_oi_{dt.strftime('%d%m%Y')}.csv")
        with open(p2, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def fetch_single_day_from_nse(dt):
    """Fetch one trading day's CSV from NSE archive with fast timeout and cache."""
    dt_str = dt.strftime("%Y-%m-%d")
    cached = get_cached_file(dt_str)
    if cached:
        return True, cached, "cached"

    # NSE archive URL format: fao_participant_oi_DDMMYYYY.csv
    date_code = dt.strftime("%d%m%Y")
    urls = [
        f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{date_code}.csv",
        f"https://archives.nseindia.com/content/fo/fao_participant_oi_{date_code}.csv",
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=NSE_HEADERS, timeout=3.5)
            if r.status_code == 200 and len(r.text) > 200 and ("Client" in r.text or "CLIENT" in r.text):
                save_to_cache(dt_str, r.text)
                return True, r.text, "live_nse"
        except Exception:
            continue

    return False, None, "not_found"


def fetch_nse_range(target_date_str, requested_days=5):
    """
    Given a target date string 'YYYY-MM-DD' and number of trading days (e.g. 2, 3, 4, 5):
    Walk backward from target date, skipping weekends and trading holidays,
    and fetch the previous N trading days.
    Includes smart fallback to nearest available cached session.
    """
    try:
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        return {"status": "error", "message": f"Invalid date format '{target_date_str}'. Expected YYYY-MM-DD."}

    records = []
    fetch_logs = []
    
    # Historical or Live date: Fetch from NSE / local cache
    curr = target_dt
    lookback_limit = 18 # up to 18 calendar days lookback to cover holidays & weekends
    consecutive_network_failures = 0
    
    while len(records) < requested_days and (target_dt - curr).days < lookback_limit:
        # 0 = Monday, ..., 4 = Friday, 5 = Saturday, 6 = Sunday
        if curr.weekday() < 5:
            dt_str = curr.strftime("%Y-%m-%d")
            success, content, source_type = fetch_single_day_from_nse(curr)
            if success:
                rec = parse_csv(content, f"fao_participant_oi_{dt_str.replace('-','')}.csv")
                rec["date"] = dt_str
                if rec.get("data") and len(rec["data"]) >= 3:
                    records.append(rec)
                    fetch_logs.append(f"Successfully retrieved {dt_str} ({source_type})")
                    consecutive_network_failures = 0
            else:
                fetch_logs.append(f"Skipped {dt_str} (Market Holiday / Data not published)")
                if source_type == "not_found":
                    consecutive_network_failures += 1
                    if consecutive_network_failures >= 3:
                        fetch_logs.append("Network lookback stopped: NSE archives unreachable or weekend/holiday block.")
                        break
        else:
            fetch_logs.append(f"Skipped {curr.strftime('%Y-%m-%d')} (Weekend)")
            
        curr -= timedelta(days=1)

    # If no records were found, fallback to nearest available cached session
    if not records:
        nearest = find_nearest_cached_date(target_date_str)
        if nearest and nearest != target_date_str:
            fetch_logs.append(f"Target date {target_date_str} unavailable. Fallback to nearest cached session: {nearest}")
            fallback_res = fetch_nse_range(nearest, requested_days)
            if fallback_res.get("status") == "success":
                fallback_res["notice"] = f"NSE archives for {target_date_str} are unavailable. Loaded nearest session: {nearest}"
                fallback_res["effective_date"] = nearest
                fallback_res["logs"] = fetch_logs + (fallback_res.get("logs") or [])
                return fallback_res

        return {
            "status": "error",
            "message": f"Could not find any published participant OI data from NSE for {target_date_str} (NSE updates daily around 6:30 PM IST).",
            "logs": fetch_logs
        }

    # Sort records ascending chronologically before analysis
    records.sort(key=lambda x: x["date"])
    analysis = calculate_multi_day_oi(records)

    return {
        "status": "success",
        "source": "nse_data_cache",
        "is_future": False,
        "days_fetched": len(records),
        "requested_days": requested_days,
        "logs": fetch_logs,
        "result": analysis
    }

if __name__ == "__main__":
    print("Testing 5-day fetch for 2024-10-15:")
    res = fetch_nse_range("2024-10-15", 5)
    print("Result status:", res["status"])
    print("Days fetched:", res["days_fetched"])
    print("Logs:")
    for l in res["logs"]:
        print(" ", l)
    print("Market Outlook:", res["result"]["market_outlook"]["stance"])
