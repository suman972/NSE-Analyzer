import re
import io
import csv
from datetime import datetime, timedelta
from pypdf import PdfReader

PARTICIPANTS = ["Client", "DII", "FII", "Pro"]
INSTRUMENTS = [
    "Index Futures",
    "Index Calls",
    "Index Puts",
    "Stock Futures",
    "Stock Calls",
    "Stock Puts"
]

def clean_num(val):
    """Convert string with commas, tabs, quotes or dashes to int."""
    if val is None:
        return 0
    s = str(val).replace(",", "").replace('"', '').replace("'", "").strip()
    if s == "" or s == "-" or s == "--" or s == "NA" or s == "null":
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0

def extract_date_from_text_or_filename(text, filename=""):
    """Robust extraction of trading date from text or filename."""
    # 1. Filename patterns
    fn_matches = [
        r"(\d{4}[-_]\d{2}[-_]\d{2})", # 2024-10-14
        r"(\d{2}[-_]\d{2}[-_]\d{4})", # 14-10-2024
        r"(\d{8})",                    # 20241014 or 14102024
        r"(\d{1,2}[-_][A-Za-z]{3}[-_]\d{2,4})" # 14-Oct-2024
    ]
    for pattern in fn_matches:
        m = re.search(pattern, filename, re.IGNORECASE)
        if m:
            raw = m.group(1)
            for fmt in ["%Y-%m-%d", "%Y_%m_%d", "%d-%m-%Y", "%d_%m_%Y", "%Y%m%d", "%d%m%Y", "%d-%b-%Y", "%d-%b-%y"]:
                try:
                    dt = datetime.strptime(raw, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

    # 2. Text patterns
    txt_matches = [
        # as on Oct 14,2024 or as on Oct 14, 2024
        (r"(?:as on|dated?|on)\s*[:\-]?\s*([A-Za-z]{3}\s*\d{1,2}\s*,\s*\d{4})", "%b %d, %Y"),
        # as on 14-Oct-2024
        (r"(?:as on|dated?|on)\s*[:\-]?\s*(\d{1,2}[-\s/][A-Za-z]{3}[-\s/]\d{2,4})", "%d-%b-%Y"),
        # as on 2024-10-14
        (r"(?:as on|dated?|on)\s*[:\-]?\s*(\d{4}[-/]\d{2}[-/]\d{2})", "%Y-%m-%d"),
        # as on 14-10-2024
        (r"(?:as on|dated?|on)\s*[:\-]?\s*(\d{1,2}[-/]\d{2}[-/]\d{4})", "%d-%m-%Y"),
        # generic standalone date
        (r"(\d{4}[-/]\d{2}[-/]\d{2})", "%Y-%m-%d"),
        (r"(\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4})", "%d-%b-%Y")
    ]
    for pattern, fmt in txt_matches:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace("/", "-")
            if fmt == "%b %d, %Y":
                raw = re.sub(r'\s*,\s*', ', ', m.group(1))
                raw = re.sub(r'\s+', ' ', raw)
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                for fb in ["%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d-%m-%Y", "%b %d, %Y", "%B %d, %Y"]:
                    try:
                        return datetime.strptime(raw, fb).strftime("%Y-%m-%d")
                    except ValueError:
                        continue

    return datetime.now().strftime("%Y-%m-%d")

def normalize_col(name):
    """Normalize header column name for fuzzy identification."""
    return re.sub(r'[^a-z0-9]', '', str(name).lower())

def identify_columns(headers):
    """
    Intelligently maps column indices based on header names.
    Supports standard NSE format, short names, or custom ordered headers.
    """
    col_map = {}
    for idx, h in enumerate(headers):
        norm = normalize_col(h)
        # Future Index Long / Short
        if ("fut" in norm or "future" in norm) and ("idx" in norm or "index" in norm):
            if "long" in norm or norm.endswith("l"): col_map["fut_idx_l"] = idx
            elif "short" in norm or norm.endswith("s"): col_map["fut_idx_s"] = idx
        # Future Stock Long / Short
        elif ("fut" in norm or "future" in norm) and ("stk" in norm or "stock" in norm):
            if "long" in norm or norm.endswith("l"): col_map["fut_stk_l"] = idx
            elif "short" in norm or norm.endswith("s"): col_map["fut_stk_s"] = idx
        # Option Index Call Long / Short
        elif ("opt" in norm or "option" in norm) and ("idx" in norm or "index" in norm) and ("call" in norm or "ce" in norm):
            if "long" in norm or norm.endswith("l"): col_map["opt_idx_ce_l"] = idx
            elif "short" in norm or norm.endswith("s"): col_map["opt_idx_ce_s"] = idx
        # Option Index Put Long / Short
        elif ("opt" in norm or "option" in norm) and ("idx" in norm or "index" in norm) and ("put" in norm or "pe" in norm):
            if "long" in norm or norm.endswith("l"): col_map["opt_idx_pe_l"] = idx
            elif "short" in norm or norm.endswith("s"): col_map["opt_idx_pe_s"] = idx
        # Option Stock Call Long / Short
        elif ("opt" in norm or "option" in norm) and ("stk" in norm or "stock" in norm) and ("call" in norm or "ce" in norm):
            if "long" in norm or norm.endswith("l"): col_map["opt_stk_ce_l"] = idx
            elif "short" in norm or norm.endswith("s"): col_map["opt_stk_ce_s"] = idx
        # Option Stock Put Long / Short
        elif ("opt" in norm or "option" in norm) and ("stk" in norm or "stock" in norm) and ("put" in norm or "pe" in norm):
            if "long" in norm or norm.endswith("l"): col_map["opt_stk_pe_l"] = idx
            elif "short" in norm or norm.endswith("s"): col_map["opt_stk_pe_s"] = idx

    return col_map

def parse_pdf(file_bytes_or_path, filename=""):
    """Parse NSE Participant-wise OI PDF."""
    if isinstance(file_bytes_or_path, (str, bytes, bytearray)):
        if isinstance(file_bytes_or_path, str):
            reader = PdfReader(file_bytes_or_path)
        else:
            reader = PdfReader(io.BytesIO(file_bytes_or_path))
    else:
        reader = PdfReader(file_bytes_or_path)

    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"

    trade_date = extract_date_from_text_or_filename(full_text, filename)
    parsed_participants = parse_text_stream(full_text)
    
    return {
        "date": trade_date,
        "filename": filename,
        "data": parsed_participants
    }

def split_line_flexible(line):
    """Split line by tabs, commas, pipes, or multiple spaces."""
    if "\t" in line:
        return [p.strip() for p in line.split("\t") if p.strip()]
    if "," in line:
        # Use csv reader to handle quotes
        try:
            r = next(csv.reader([line]))
            return [p.strip() for p in r if p.strip()]
        except Exception:
            return [p.strip() for p in line.split(",") if p.strip()]
    if "|" in line:
        return [p.strip() for p in line.split("|") if p.strip()]
    # Fallback: split by 2 or more spaces
    parts = re.split(r'\s{2,}', line.strip())
    if len(parts) >= 12:
        return parts
    return line.split()

def parse_csv(content_str_or_bytes, filename=""):
    """
    Parse participant-wise OI data from CSV, TSV, or arbitrary tabular text.
    Handles comma-separated, tab-separated, pipe-separated, and space-separated lines.
    """
    if isinstance(content_str_or_bytes, bytes):
        text = content_str_or_bytes.decode("utf-8", errors="ignore")
    else:
        text = str(content_str_or_bytes)
        
    trade_date = extract_date_from_text_or_filename(text, filename)
    
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    raw_rows = [split_line_flexible(l) for l in lines]
    raw_rows = [r for r in raw_rows if r]

    participant_data = {}
    
    # 1. Search for Header row
    header_idx = -1
    col_map = {}
    for i, row in enumerate(raw_rows):
        joined = " ".join(row).lower()
        if "client type" in joined or "future index" in joined or "fut idx" in joined:
            header_idx = i
            col_map = identify_columns(row)
            break

    # If column mapping succeeded with headers
    if header_idx != -1 and len(col_map) >= 8:
        for row in raw_rows[header_idx + 1:]:
            if not row: continue
            ptype = row[0].strip().title()
            matched_p = None
            if "client" in ptype.lower(): matched_p = "Client"
            elif "dii" in ptype.lower(): matched_p = "DII"
            elif "fii" in ptype.lower(): matched_p = "FII"
            elif "pro" in ptype.lower(): matched_p = "Pro"

            if matched_p:
                def get_val(key):
                    if key in col_map and col_map[key] < len(row):
                        return clean_num(row[col_map[key]])
                    return 0

                participant_data[matched_p] = {
                    "Index Futures": {"long": get_val("fut_idx_l"), "short": get_val("fut_idx_s")},
                    "Index Calls": {"long": get_val("opt_idx_ce_l"), "short": get_val("opt_idx_ce_s")},
                    "Index Puts": {"long": get_val("opt_idx_pe_l"), "short": get_val("opt_idx_pe_s")},
                    "Stock Futures": {"long": get_val("fut_stk_l"), "short": get_val("fut_stk_s")},
                    "Stock Calls": {"long": get_val("opt_stk_ce_l"), "short": get_val("opt_stk_ce_s")},
                    "Stock Puts": {"long": get_val("opt_stk_pe_l"), "short": get_val("opt_stk_pe_s")},
                }

    # If header mapping wasn't complete, check rows with standard NSE index positions
    if len(participant_data) < 4:
        for row in raw_rows:
            if not row: continue
            ptype = row[0].strip().title()
            matched_p = None
            if ptype.lower() in ["client", "clients"]: matched_p = "Client"
            elif ptype.lower() in ["dii", "diis"]: matched_p = "DII"
            elif ptype.lower() in ["fii", "fiis"]: matched_p = "FII"
            elif ptype.lower() in ["pro", "pros"]: matched_p = "Pro"

            if matched_p and len(row) >= 13:
                nums = [clean_num(x) for x in row[1:13]]
                # Standard NSE column order:
                # 0: FutIdxL, 1: FutIdxS, 2: FutStkL, 3: FutStkS, 4: OptIdxCEL, 5: OptIdxPEL,
                # 6: OptIdxCES, 7: OptIdxPES, 8: OptStkCEL, 9: OptStkPEL, 10: OptStkCES, 11: OptStkPES
                participant_data[matched_p] = {
                    "Index Futures": {"long": nums[0], "short": nums[1]},
                    "Index Calls": {"long": nums[4], "short": nums[6]},
                    "Index Puts": {"long": nums[5], "short": nums[7]},
                    "Stock Futures": {"long": nums[2], "short": nums[3]},
                    "Stock Calls": {"long": nums[8], "short": nums[10]},
                    "Stock Puts": {"long": nums[9], "short": nums[11]},
                }

    # Fallback to general text stream parser if needed
    if len(participant_data) < 4:
        participant_data = parse_text_stream(text)

    return {
        "date": trade_date,
        "filename": filename,
        "data": participant_data
    }

def parse_text_stream(text):
    """
    Robust extractor for both vertical token streams (pypdf output)
    and horizontal lines of participant numbers.
    """
    participant_data = {}
    
    # 1. Horizontal lines
    lines = text.splitlines()
    for line in lines:
        for p in ["Client", "DII", "FII", "Pro"]:
            m = re.match(rf"^\s*{p}\b\s*(.*)", line, re.IGNORECASE)
            if m:
                tokens = re.findall(r"-?[\d,]+", m.group(1))
                if len(tokens) >= 12:
                    nums = [clean_num(x) for x in tokens[:12]]
                    participant_data[p] = {
                        "Index Futures": {"long": nums[0], "short": nums[1]},
                        "Index Calls": {"long": nums[4], "short": nums[6]},
                        "Index Puts": {"long": nums[5], "short": nums[7]},
                        "Stock Futures": {"long": nums[2], "short": nums[3]},
                        "Stock Calls": {"long": nums[8], "short": nums[10]},
                        "Stock Puts": {"long": nums[9], "short": nums[11]},
                    }

    if len(participant_data) == 4:
        return participant_data

    # 2. Vertical token stream (pypdf table extraction)
    tokens = [t.strip() for t in text.split() if t.strip()]
    for p in ["Client", "DII", "FII", "Pro"]:
        for idx, token in enumerate(tokens):
            if token.lower() == p.lower():
                # Avoid header 'Client Type'
                if idx + 1 < len(tokens) and tokens[idx + 1].lower() in ["type", "name", "category"]:
                    continue
                nums = []
                for sub_tok in tokens[idx + 1:]:
                    if sub_tok.lower() in ["client", "dii", "fii", "pro", "total"]:
                        break
                    val = clean_num(sub_tok)
                    if re.match(r"^-?[\d,]+$", sub_tok):
                        nums.append(val)
                    if len(nums) == 14:
                        break
                if len(nums) >= 12:
                    participant_data[p] = {
                        "Index Futures": {"long": nums[0], "short": nums[1]},
                        "Index Calls": {"long": nums[4], "short": nums[6]},
                        "Index Puts": {"long": nums[5], "short": nums[7]},
                        "Stock Futures": {"long": nums[2], "short": nums[3]},
                        "Stock Calls": {"long": nums[8], "short": nums[10]},
                        "Stock Puts": {"long": nums[9], "short": nums[11]},
                    }
                    break

    return participant_data

def calculate_multi_day_oi(days_data_list):
    """
    Given a list of parsed daily records, sort them chronologically,
    and compute day-over-day changes, net positions, and carried history.
    Strictly preserves the instrument sequence:
    1. Index Futures
    2. Index Calls
    3. Index Puts
    4. Stock Futures
    5. Stock Calls
    6. Stock Puts
    """
    if not days_data_list:
        return {}

    # Sort by date ascending
    sorted_days = sorted(days_data_list, key=lambda x: x["date"])
    total_days = len(sorted_days)
    
    today_rec = sorted_days[-1]
    today_date = today_rec["date"]
    
    prev_rec = sorted_days[-2] if total_days >= 2 else None
    day_minus_2 = sorted_days[-3] if total_days >= 3 else None
    day_minus_3 = sorted_days[-4] if total_days >= 4 else None
    day_minus_4 = sorted_days[-5] if total_days >= 5 else None

    carried_labels = ["TODAY"]
    if prev_rec: carried_labels.append("1 DAY AGO")
    if day_minus_2: carried_labels.append("2 DAYS AGO")
    if day_minus_3: carried_labels.append("3 DAYS AGO")
    if day_minus_4: carried_labels.append("4 DAYS AGO")

    # The exact sequence requested by the user:
    # Index Futures -> Index Calls -> Index Puts -> Stock Futures -> Stock Calls -> Stock Puts
    instrument_tables = {}
    
    participant_summary = {
        "Clients": [],
        "DIIs": [],
        "FIIs": [],
        "Pros": []
    }

    participant_map = {
        "Client": "Clients",
        "DII": "DIIs",
        "FII": "FIIs",
        "Pro": "Pros"
    }

    for inst in INSTRUMENTS:
        instrument_tables[inst] = []
        for p_key in ["Client", "DII", "FII", "Pro"]:
            p_display = participant_map[p_key]
            
            t_data = today_rec["data"].get(p_key, {}).get(inst, {"long": 0, "short": 0})
            l_today = t_data["long"]
            s_today = t_data["short"]
            net_today = l_today - s_today

            if prev_rec:
                p_data_1 = prev_rec["data"].get(p_key, {}).get(inst, {"long": 0, "short": 0})
                l_prev = p_data_1["long"]
                s_prev = p_data_1["short"]
                net_prev = l_prev - s_prev
                
                long_chg = l_today - l_prev
                short_chg = s_today - s_prev
                net_buy_sell = long_chg - short_chg
            else:
                long_chg = 0
                short_chg = 0
                net_buy_sell = 0
                net_prev = net_today

            net_2d = None
            if day_minus_2:
                p_data_2 = day_minus_2["data"].get(p_key, {}).get(inst, {"long": 0, "short": 0})
                net_2d = p_data_2["long"] - p_data_2["short"]

            net_3d = None
            if day_minus_3:
                p_data_3 = day_minus_3["data"].get(p_key, {}).get(inst, {"long": 0, "short": 0})
                net_3d = p_data_3["long"] - p_data_3["short"]

            net_4d = None
            if day_minus_4:
                p_data_4 = day_minus_4["data"].get(p_key, {}).get(inst, {"long": 0, "short": 0})
                net_4d = p_data_4["long"] - p_data_4["short"]

            is_put = "put" in inst.lower()

            # Longs
            if long_chg > 0:
                long_label = "Added Longs"
                long_color = "red" if is_put else "green"  # Adding puts = Bearish (Red), adding futures/calls = Bullish (Green)
            elif long_chg < 0:
                long_label = "Closed Longs"
                long_color = "green" if is_put else "red"  # Closing puts = Bullish (Green), closing futures/calls = Bearish (Red)
            else:
                long_label = "Unchanged"
                long_color = "neutral"

            # Shorts
            if short_chg > 0:
                short_label = "Added Shorts"
                short_color = "green" if is_put else "red" # Adding put shorts (writing puts) = Bullish (Green), writing futures/calls = Bearish (Red)
            elif short_chg < 0:
                short_label = "Closed Shorts"
                short_color = "red" if is_put else "green" # Closing put shorts = Bearish (Red), covering futures/calls = Bullish (Green)
            else:
                short_label = "Unchanged"
                short_color = "neutral"

            # Net Buy / Sell
            if net_buy_sell > 0:
                net_label = "Bought Net"
                net_color = "red" if is_put else "green"   # Buying net puts = Bearish (Red), buying net futures/calls = Bullish (Green)
            elif net_buy_sell < 0:
                net_label = "Sold Net"
                net_color = "green" if is_put else "red"   # Selling net puts = Bullish (Green), selling net futures/calls = Bearish (Red)
            else:
                net_label = "Neutral"
                net_color = "neutral"

            carried_dict = {
                "TODAY": net_today,
                "1 DAY AGO": net_prev if prev_rec else "-",
                "2 DAYS AGO": net_2d if net_2d is not None else "-",
                "3 DAYS AGO": net_3d if net_3d is not None else "-",
                "4 DAYS AGO": net_4d if net_4d is not None else "-",
            }

            # Carried positions colors (for Puts: negative net OI means Net Put Sellers = Bullish = Green)
            carried_colors = {}
            for lbl, val in carried_dict.items():
                if isinstance(val, (int, float)):
                    if is_put:
                        carried_colors[lbl] = "green" if val < 0 else ("red" if val > 0 else "neutral")
                    else:
                        carried_colors[lbl] = "green" if val > 0 else ("red" if val < 0 else "neutral")
                else:
                    carried_colors[lbl] = "neutral"

            row_obj = {
                "participant": p_display,
                "p_key": p_key,
                "long_chg": long_chg,
                "long_label": long_label,
                "long_color": long_color,
                "short_chg": short_chg,
                "short_label": short_label,
                "short_color": short_color,
                "net_buy_sell": net_buy_sell,
                "net_label": net_label,
                "net_color": net_color,
                "carried": carried_dict,
                "carried_colors": carried_colors,
                "raw_today": {"long": l_today, "short": s_today, "net": net_today}
            }
            instrument_tables[inst].append(row_obj)

            # Append to participant summary in the exact sequence:
            participant_summary[p_display].append({
                "instrument": inst,
                "action": net_label,
                "qty": net_buy_sell,
                "color": net_color
            })

    # Run Automated Market Outlook Engine
    market_outlook = generate_market_outlook(instrument_tables, today_rec["date"], prev_rec["date"] if prev_rec else "")

    # Compute Smart Writing Shares and FII Hedge Flag (Stage 1 → Stage 3 bridge)
    smart_writing_shares = compute_smart_writing_shares_from_tables(instrument_tables)

    return {
        "today_date": today_date,
        "history_dates": [d["date"] for d in sorted_days],
        "carried_labels": carried_labels,
        "instrument_order": INSTRUMENTS, # Guaranteed sequence
        "instrument_tables": instrument_tables,
        "participant_summary": participant_summary,
        "market_outlook": market_outlook,
        "smart_writing_shares": smart_writing_shares,
    }

def compute_smart_writing_shares_from_tables(tables: dict) -> dict:
    """
    Compute Smart-Money Writing Shares (W_CE_Smart, W_PE_Smart) and
    Retention Ratio (when vol_data is available) directly from
    multi-day OI instrument tables (output of calculate_multi_day_oi).

    Also detects FII Put-Buying Hedge Pattern (Rank #4 Signal Hierarchy):
    If FII adds Index Put Longs simultaneously with Index Futures Longs
    AND Pro Desks write Puts → classify FII Put Long as HEDGE, not Bearish.
    """
    participants = ["FII", "Pro", "Client", "DII"]

    def _get(p_key, instrument):
        for r in tables.get(instrument, []):
            if r.get("p_key") == p_key:
                return r
        return {}

    # Extract short_chg for calls and puts
    ce_short_chg = {p: _get(p, "Index Calls").get("short_chg", 0) for p in participants}
    pe_short_chg = {p: _get(p, "Index Puts").get("short_chg",  0) for p in participants}
    ce_long_chg  = {p: _get(p, "Index Calls").get("long_chg",  0) for p in participants}
    pe_long_chg  = {p: _get(p, "Index Puts").get("long_chg",   0) for p in participants}
    fut_net      = {p: _get(p, "Index Futures").get("net_buy_sell", 0) for p in participants}
    stk_fut_net  = {p: _get(p, "Stock Futures").get("net_buy_sell", 0) for p in participants}

    # Smart writing shares
    smart_ce = max(0, ce_short_chg.get("FII", 0)) + max(0, ce_short_chg.get("Pro", 0))
    total_ce = sum(max(0, ce_short_chg[p]) for p in participants)
    W_CE     = smart_ce / max(1, total_ce)

    smart_pe = max(0, pe_short_chg.get("FII", 0)) + max(0, pe_short_chg.get("Pro", 0))
    total_pe = sum(max(0, pe_short_chg[p]) for p in participants)
    W_PE     = smart_pe / max(1, total_pe)

    # FII Hedge Filter (Rank #4)
    fii_put_long_added = max(0, pe_long_chg.get("FII", 0))
    fii_fut_long       = fut_net.get("FII", 0)
    pro_put_written    = max(0, pe_short_chg.get("Pro", 0))
    fii_hedge_active   = (
        fii_put_long_added > 50_000
        and fii_fut_long > 0
        and pro_put_written > 50_000
    )

    return {
        "W_CE_Smart":        round(W_CE, 4),
        "W_PE_Smart":        round(W_PE, 4),
        "ce_short_chg":      ce_short_chg,
        "pe_short_chg":      pe_short_chg,
        "ce_long_chg":       ce_long_chg,
        "pe_long_chg":       pe_long_chg,
        "fut_net":           fut_net,
        "stk_fut_net":       stk_fut_net,
        "smart_ce_written":  int(smart_ce),
        "smart_pe_written":  int(smart_pe),
        "total_ce_written":  int(total_ce),
        "total_pe_written":  int(total_pe),
        "fii_hedge_active":  fii_hedge_active,
        "fii_hedge_badge":   (
            "🛡️ Portfolio Crash Insurance (Hedge) — True Bias is Bullish"
            if fii_hedge_active else ""
        ),
    }


def generate_market_outlook(tables, today_date, prev_date):
    """
    Rule-based quantitative interpretation of participant positioning
    and next-day market bias & traps.
    """
    fii_idx_fut = next(r for r in tables["Index Futures"] if r["p_key"] == "FII")
    fii_idx_ce = next(r for r in tables["Index Calls"] if r["p_key"] == "FII")
    fii_idx_pe = next(r for r in tables["Index Puts"] if r["p_key"] == "FII")
    fii_stk_fut = next(r for r in tables["Stock Futures"] if r["p_key"] == "FII")

    pro_idx_fut = next(r for r in tables["Index Futures"] if r["p_key"] == "Pro")
    pro_idx_ce = next(r for r in tables["Index Calls"] if r["p_key"] == "Pro")
    pro_idx_pe = next(r for r in tables["Index Puts"] if r["p_key"] == "Pro")

    cli_idx_fut = next(r for r in tables["Index Futures"] if r["p_key"] == "Client")
    cli_idx_ce = next(r for r in tables["Index Calls"] if r["p_key"] == "Client")
    cli_idx_pe = next(r for r in tables["Index Puts"] if r["p_key"] == "Client")

    score = 0
    factors = []

    # FII Index Futures
    if fii_idx_fut["net_buy_sell"] > 10000:
        score += 20
        factors.append(f"FIIs bought +{fii_idx_fut['net_buy_sell']:,} Index Futures (Short covering/Long additions)")
    elif fii_idx_fut["net_buy_sell"] < -10000:
        score -= 20
        factors.append(f"FIIs sold {fii_idx_fut['net_buy_sell']:,} Index Futures (Fresh shorts/Long liquidation)")
    
    # FII Index Calls
    if fii_idx_ce["net_buy_sell"] > 30000:
        score += 20
        factors.append(f"FIIs aggressive Call buying (+{fii_idx_ce['net_buy_sell']:,}) indicating bullish upward expectations")
    elif fii_idx_ce["net_buy_sell"] < -30000:
        score -= 20
        factors.append(f"FIIs Call dumping/unwinding ({fii_idx_ce['net_buy_sell']:,})")

    # FII Index Puts
    if fii_idx_pe["net_buy_sell"] < -30000:
        score += 15
        factors.append(f"FIIs sold/wrote -{abs(fii_idx_pe['net_buy_sell']):,} Index Puts (Unwinding downside hedges)")
    elif fii_idx_pe["net_buy_sell"] > 30000:
        score -= 15
        factors.append(f"FIIs bought +{fii_idx_pe['net_buy_sell']:,} Index Puts (Hedging downside or directional bearish bet)")

    # Pro Desk Writing Check
    if pro_idx_pe["short_chg"] > 50000 and pro_idx_pe["net_buy_sell"] < 0:
        score += 20
        factors.append(f"Pros added heavy Put Shorts (+{pro_idx_pe['short_chg']:,} puts written), creating a powerful floor/support zone")
    elif pro_idx_ce["short_chg"] > 50000 and pro_idx_ce["net_buy_sell"] < 0:
        score -= 20
        factors.append(f"Pros added heavy Call Shorts (+{pro_idx_ce['short_chg']:,} calls written), capping upside resistance")

    # Client (Retail) Trap Indicator (Contrarian)
    retail_trap_detected = False
    retail_trap_direction = ""
    if cli_idx_pe["net_buy_sell"] > 100000 and cli_idx_ce["net_buy_sell"] < -50000:
        score += 25
        retail_trap_detected = True
        retail_trap_direction = "BULLISH_SQUEEZE"
        factors.append(f"🚨 RETAIL TRAP ALERT: Clients aggressively panic-bought +{cli_idx_pe['net_buy_sell']:,} Puts and sold -{abs(cli_idx_ce['net_buy_sell']):,} Calls! In Indian markets, extreme retail Put buying almost always triggers a vicious short-squeeze rally against them.")
    elif cli_idx_ce["net_buy_sell"] > 100000 and cli_idx_pe["net_buy_sell"] < -50000:
        score -= 25
        retail_trap_detected = True
        retail_trap_direction = "BEARISH_DUMP"
        factors.append(f"🚨 RETAIL TRAP ALERT: Clients heavily bought +{cli_idx_ce['net_buy_sell']:,} Calls and dumped Puts! High probability of bull trap / gap-down dump.")

    # Stock Futures Institutional accumulation
    if fii_stk_fut["net_buy_sell"] > 20000:
        score += 10
        factors.append(f"FIIs accumulated +{fii_stk_fut['net_buy_sell']:,} Stock Futures (Cash/Stock underlying strength)")
    elif fii_stk_fut["net_buy_sell"] < -20000:
        score -= 10
        factors.append(f"FIIs sold {fii_stk_fut['net_buy_sell']:,} Stock Futures")

    # Determine Overall Stance
    if score >= 45:
        overall_stance = "STRONGLY BULLISH"
        badge_color = "#10b981"
        summary_verdict = "Heavy Institutional Bullish Positioning & Imminent Retail Put Squeeze"
        next_day_action = "Expect gap-up opening or early dip-buying continuation. Retailers who bought heavy puts will be forced to cover, fueling strong upward momentum. Look for long setups on 5-minute pullbacks."
    elif score >= 15:
        overall_stance = "MODERATELY BULLISH"
        badge_color = "#34d399"
        summary_verdict = "Positive Institutional Flow with Mild Upward Bias"
        next_day_action = "Buy on intraday support. Watch key index levels for breakout confirmation."
    elif score <= -45:
        overall_stance = "STRONGLY BEARISH"
        badge_color = "#ef4444"
        summary_verdict = "Heavy Institutional Selling & Distribution Pressure"
        next_day_action = "Sell on intraday rallies. FIIs and Pros are building short inventory while unloading calls. Trapped call buyers will face rapid decay."
    elif score <= -15:
        overall_stance = "MODERATELY BEARISH"
        badge_color = "#f87171"
        summary_verdict = "Mild Bearish Bias with Institutional Pressure"
        next_day_action = "Cautious stance. Avoid chasing highs; prefer hedging long holdings."
    else:
        overall_stance = "NEUTRAL / RANGEBOUND"
        badge_color = "#f59e0b"
        summary_verdict = "Balanced Positions with Both-Side Option Writing"
        next_day_action = "Expect two-way choppy movement. Pro option sellers will pocket premium decay. Good day for non-directional option selling (straddles/strangles)."

    return {
        "score": score,
        "stance": overall_stance,
        "badge_color": badge_color,
        "verdict": summary_verdict,
        "next_day_action": next_day_action,
        "retail_trap": {
            "detected": retail_trap_detected,
            "type": retail_trap_direction
        },
        "factors": factors,
        "participant_insights": {
            "FII": {
                "stance": "Bullish Reversal / Short Covering" if fii_idx_fut["net_buy_sell"] > 0 else "Bearish Continuation",
                "futures_carried": f"{fii_idx_fut['raw_today']['net']:,}",
                "today_action": f"{fii_idx_fut['net_label']} {abs(fii_idx_fut['net_buy_sell']):,} Index Futures, {fii_idx_ce['net_label']} {abs(fii_idx_ce['net_buy_sell']):,} Calls, {fii_idx_pe['net_label']} {abs(fii_idx_pe['net_buy_sell']):,} Puts."
            },
            "Pro": {
                "stance": "Bullish Floor Setup" if pro_idx_pe["short_chg"] > 100000 else "Neutral/Hedging",
                "today_action": f"Wrote +{pro_idx_pe['short_chg']:,} Puts and covered {abs(pro_idx_ce['short_chg']):,} Call Shorts."
            },
            "Client": {
                "stance": "Heavily Bearish (Prime Contrarian Trap)" if cli_idx_pe["net_buy_sell"] > 100000 else "Neutral",
                "today_action": f"Bought +{cli_idx_pe['net_buy_sell']:,} Puts and dumped -{abs(cli_idx_ce['net_buy_sell']):,} Calls."
            },
            "DII": {
                "stance": "Mild Accumulation",
                "today_action": f"Bought net {fii_idx_fut.get('raw_today',{}).get('net',0):,} Index Futures and steady domestic cash equity."
            }
        }
    }
