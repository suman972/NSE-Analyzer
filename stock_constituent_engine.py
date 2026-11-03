"""
Stock Constituent Engine — Stage 3 Helper
==========================================
Validates the index option chain signals using heavyweight stock
constituent data from:
  - File 4 (Bhavcopy): STF / STO instruments for stock futures & options
  - File 5 (Cash Delivery): DELIV_PER, DELIV_QTY for top stocks

Outputs a constituent alignment score (-10 to +10).
"""

# ---------------------------------------------------------------------------
# Heavyweight Stock Lists
# ---------------------------------------------------------------------------

NIFTY_HEAVYWEIGHTS = [
    "HDFCBANK", "RELIANCE", "ICICIBANK", "INFY", "TCS",
    "BHARTIARTL", "LT", "SBIN"
]

BANKNIFTY_HEAVYWEIGHTS = [
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK"
]

FINNIFTY_HEAVYWEIGHTS = [
    "HDFCBANK", "ICICIBANK", "SBIN", "BAJFINANCE", "AXISBANK", "KOTAKBANK"
]

HEAVYWEIGHT_MAP = {
    "NIFTY":     NIFTY_HEAVYWEIGHTS,
    "BANKNIFTY": BANKNIFTY_HEAVYWEIGHTS,
    "FINNIFTY":  FINNIFTY_HEAVYWEIGHTS,
}

# Delivery % threshold: >= 45% is high institutional delivery
DELIVERY_HIGH_THRESHOLD = 45.0
DELIVERY_LOW_THRESHOLD  = 25.0


# ---------------------------------------------------------------------------
# 1. Delivery Data Parser (File 5: sec_bhavdata_full_DDMMYYYY.csv)
# ---------------------------------------------------------------------------

def parse_cash_delivery_data(cash_csv_rows: list) -> dict:
    """
    Parses rows from the cash market security-wise delivery file.
    Returns a dict keyed by stock symbol with delivery data.

    Expected columns (flexible, case-insensitive):
        SYMBOL / TckrSymb
        CLOSE_PRICE / ClsPric
        TTL_TRD_QNTY / TtlTradgVol
        DELIV_QTY
        DELIV_PER / Delivery %
    """
    result = {}
    if not cash_csv_rows:
        return result

    for row in cash_csv_rows:
        # Normalize keys
        norm = {k.strip().upper().replace(" ", "_"): v for k, v in row.items()}

        sym = (
            norm.get("SYMBOL")
            or norm.get("TCKRSYMB")
            or norm.get("SCRIP_CD")
            or ""
        ).strip().upper()

        if not sym:
            continue

        try:
            close_price = float(norm.get("CLOSE_PRICE") or norm.get("CLSPRIC") or 0)
            total_qty   = float(norm.get("TTL_TRD_QNTY") or norm.get("TTLTRADGVOL") or 0)
            deliv_qty   = float(norm.get("DELIV_QTY") or 0)
            deliv_per   = float(norm.get("DELIV_PER") or norm.get("DELIVERY_PER") or 0)
        except (ValueError, TypeError):
            continue

        # If DELIV_PER not directly provided, compute it
        if deliv_per == 0 and total_qty > 0:
            deliv_per = (deliv_qty / total_qty) * 100.0

        result[sym] = {
            "close_price": close_price,
            "total_qty":   total_qty,
            "deliv_qty":   deliv_qty,
            "deliv_per":   round(deliv_per, 2),
        }

    return result


# ---------------------------------------------------------------------------
# 2. Stock Futures Buildup from Bhavcopy (File 4: STF instrument)
# ---------------------------------------------------------------------------

def extract_stock_futures_buildup(bhavcopy_rows: list) -> dict:
    """
    Filters File 4 (Bhavcopy) for STF / FUTSTK instruments and
    classifies each heavyweight stock's futures buildup into one of:
      FRESH_LONG  : ΔOI > 0, ΔPrice > 0
      FRESH_SHORT : ΔOI > 0, ΔPrice < 0
      SHORT_COVER : ΔOI < 0, ΔPrice > 0
      LONG_UNWIND : ΔOI < 0, ΔPrice ≤ 0
      NEUTRAL     : ΔOI == 0
    """
    result = {}
    if not bhavcopy_rows:
        return result

    for row in bhavcopy_rows:
        norm = {k.strip().upper().replace(" ", "_"): v for k, v in row.items()}

        inst = (norm.get("FININSTRMTP") or norm.get("INSTRUMENT") or "").strip().upper()
        if inst not in ("STF", "FUTSTK"):
            continue

        sym = (norm.get("TCKRSYMB") or norm.get("SYMBOL") or "").strip().upper()
        if not sym:
            continue

        try:
            chg_oi  = float(norm.get("CHNGINOPNINTRS") or norm.get("CHG_IN_OI") or 0)
            cls_p   = float(norm.get("CLSPRIC")         or norm.get("CLOSE")     or 0)
            prv_p   = float(norm.get("PRVSCLSGPRIC")    or norm.get("SETTLE_PR") or cls_p)
            delta_p = cls_p - prv_p
        except (ValueError, TypeError):
            continue

        if chg_oi > 0:
            buildup = "FRESH_LONG" if delta_p > 0 else "FRESH_SHORT"
        elif chg_oi < 0:
            buildup = "SHORT_COVER" if delta_p > 0 else "LONG_UNWIND"
        else:
            buildup = "NEUTRAL"

        if sym not in result:
            result[sym] = {
                "chg_oi": 0, "close": 0.0, "prev_close": 0.0,
                "delta_p": 0.0, "buildup": "NEUTRAL",
            }

        # Take the nearest expiry only (largest OI usually)
        existing_oi = abs(result[sym].get("chg_oi", 0))
        if abs(chg_oi) > existing_oi:
            result[sym] = {
                "chg_oi":    int(chg_oi),
                "close":     round(cls_p, 2),
                "prev_close": round(prv_p, 2),
                "delta_p":   round(delta_p, 2),
                "buildup":   buildup,
            }

    return result


# ---------------------------------------------------------------------------
# 3. Constituent Alignment Score (-10 to +10)
# ---------------------------------------------------------------------------

BULLISH_BUILDUPS = {"FRESH_LONG", "SHORT_COVER"}
BEARISH_BUILDUPS = {"FRESH_SHORT", "LONG_UNWIND"}


def compute_constituent_alignment_score(
    symbol:            str,
    futures_buildup:   dict,  # from extract_stock_futures_buildup
    delivery_data:     dict,  # from parse_cash_delivery_data
) -> dict:
    """
    For each of the Top-5 heavyweights of the given index, checks:
      - Futures buildup direction (Bullish or Bearish)
      - Cash delivery % (≥45% = institutional accumulation → Bullish)

    Alignment Score = (Σ stock_scores) capped at [-10, +10]
      Each stock can contribute: +2 (strongly bullish), +1, 0, -1, -2
    """
    heavyweights = HEAVYWEIGHT_MAP.get(symbol.upper(), NIFTY_HEAVYWEIGHTS)[:5]
    scores       = []
    details      = []

    for stk in heavyweights:
        stk_score = 0
        stk_detail = {
            "symbol":    stk,
            "futures":   futures_buildup.get(stk, {}),
            "delivery":  delivery_data.get(stk, {}),
            "score":     0,
            "verdict":   "Neutral",
        }

        # Futures direction
        buildup = (futures_buildup.get(stk) or {}).get("buildup", "NEUTRAL")
        if buildup in BULLISH_BUILDUPS:
            stk_score += 1
        elif buildup in BEARISH_BUILDUPS:
            stk_score -= 1

        # Delivery %
        deliv_per = (delivery_data.get(stk) or {}).get("deliv_per", 0.0)
        if deliv_per >= DELIVERY_HIGH_THRESHOLD:
            stk_score += 1  # institutional accumulation = Bullish
        elif deliv_per > 0 and deliv_per < DELIVERY_LOW_THRESHOLD:
            stk_score -= 1  # low delivery = mostly speculative / retail churn

        stk_detail["score"] = stk_score
        stk_detail["buildup_label"] = {
            "FRESH_LONG":  "🟢 Fresh Long (Bullish)",
            "SHORT_COVER": "🟢 Short Cover (Bullish)",
            "FRESH_SHORT": "🔴 Fresh Short (Bearish)",
            "LONG_UNWIND": "🔴 Long Unwind (Bearish)",
            "NEUTRAL":     "⚪ Neutral",
        }.get(buildup, "⚪ Neutral")
        stk_detail["delivery_label"] = (
            f"📦 High Delivery {deliv_per:.1f}% (Institutional)"
            if deliv_per >= DELIVERY_HIGH_THRESHOLD
            else (
                f"⚠️ Low Delivery {deliv_per:.1f}% (Speculative)"
                if deliv_per > 0 and deliv_per < DELIVERY_LOW_THRESHOLD
                else f"📊 Delivery {deliv_per:.1f}%"
            )
        )
        stk_detail["verdict"] = (
            "Bullish" if stk_score > 0 else ("Bearish" if stk_score < 0 else "Neutral")
        )

        scores.append(stk_score)
        details.append(stk_detail)

    total_score = max(-10, min(10, sum(scores)))
    bullish_count = sum(1 for s in scores if s > 0)
    bearish_count = sum(1 for s in scores if s < 0)

    if total_score >= 6:
        verdict = f"✅ {bullish_count}/5 Heavyweights Bullish — Strong Index Support"
    elif total_score >= 3:
        verdict = f"🟡 {bullish_count}/5 Heavyweights Bullish — Mild Support"
    elif total_score <= -6:
        verdict = f"❌ {bearish_count}/5 Heavyweights Bearish — Strong Index Drag"
    elif total_score <= -3:
        verdict = f"🟡 {bearish_count}/5 Heavyweights Bearish — Mild Drag"
    else:
        verdict = "⚪ Mixed / Neutral Constituent Signals"

    return {
        "symbol":          symbol,
        "heavyweights":    heavyweights,
        "alignment_score": total_score,
        "bullish_count":   bullish_count,
        "bearish_count":   bearish_count,
        "verdict":         verdict,
        "details":         details,
    }


# ---------------------------------------------------------------------------
# 4. Simulated fallback (when real files unavailable)
# ---------------------------------------------------------------------------

def get_simulated_constituent_data(symbol: str = "NIFTY") -> dict:
    """Returns a realistic simulated constituent alignment for demo/future dates."""
    heavyweights = HEAVYWEIGHT_MAP.get(symbol.upper(), NIFTY_HEAVYWEIGHTS)[:5]
    details = []
    for i, stk in enumerate(heavyweights):
        buildup = ["FRESH_LONG", "FRESH_LONG", "SHORT_COVER", "FRESH_SHORT", "NEUTRAL"][i % 5]
        deliv_per = [52.3, 48.1, 61.5, 23.8, 41.2][i % 5]
        stk_score = (1 if buildup in BULLISH_BUILDUPS else (-1 if buildup in BEARISH_BUILDUPS else 0))
        stk_score += (1 if deliv_per >= DELIVERY_HIGH_THRESHOLD else (-1 if deliv_per < DELIVERY_LOW_THRESHOLD else 0))
        details.append({
            "symbol":         stk,
            "futures":        {"buildup": buildup, "chg_oi": 12500, "delta_p": 3.5},
            "delivery":       {"deliv_per": deliv_per},
            "score":          stk_score,
            "buildup_label":  f"🟢 {buildup}" if buildup in BULLISH_BUILDUPS else ("🔴 " + buildup if buildup in BEARISH_BUILDUPS else "⚪ Neutral"),
            "delivery_label": f"📦 High Delivery {deliv_per:.1f}%" if deliv_per >= 45 else f"📊 Delivery {deliv_per:.1f}%",
            "verdict":        "Bullish" if stk_score > 0 else ("Bearish" if stk_score < 0 else "Neutral"),
        })

    total = sum(d["score"] for d in details)
    return {
        "symbol":          symbol,
        "heavyweights":    heavyweights,
        "alignment_score": max(-10, min(10, total)),
        "bullish_count":   sum(1 for d in details if d["verdict"] == "Bullish"),
        "bearish_count":   sum(1 for d in details if d["verdict"] == "Bearish"),
        "verdict":         "✅ 3/5 Heavyweights Bullish — Mild Support",
        "details":         details,
        "source":          "simulated",
    }
