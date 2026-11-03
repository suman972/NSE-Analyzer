"""
Participant-to-Strike Matching Engine — Stage 3
================================================
Connects Stage 1 (WHO: Participant OI segregation) with Stage 2 (WHERE: Option Chain strikes)
to compute Smart-Money Wall Scores, identify Institutional Strike Levels, and classify
Retail Lottery Traps, Short-Covering Squeeze strikes, and Trapped Writers.

Formulas are derived from NSE Indian microstructure — NOT US-style GEX or textbook Kelly/CVaR.
"""
import math
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Smart-Money Writing Share (W_CE_Smart / W_PE_Smart)
# ---------------------------------------------------------------------------

def compute_smart_writing_shares(oi_engine_result: dict) -> dict:
    """
    Given the multi-day OI engine result (from oi_engine.calculate_multi_day_oi),
    extracts delta-OI changes for each participant and computes:
      - W_CE_Smart : Smart-Money Call Writing Share  (FII + Pro vs. all writers)
      - W_PE_Smart : Smart-Money Put Writing Share   (FII + Pro vs. all writers)
      - Retention Ratio per participant per segment (requires vol data if available)

    Returns a dict with all computed shares and raw delta values.
    """
    tables = (oi_engine_result or {}).get("instrument_tables", {})

    def _get(participant_key: str, instrument: str) -> dict:
        rows = tables.get(instrument, [])
        for r in rows:
            if r.get("p_key") == participant_key:
                return r
        return {}

    participants = ["FII", "Pro", "Client", "DII"]

    # --- Index Call deltas ---
    ce_short_chg = {}
    ce_long_chg  = {}
    for p in participants:
        r = _get(p, "Index Calls")
        ce_short_chg[p] = r.get("short_chg", 0)
        ce_long_chg[p]  = r.get("long_chg",  0)

    # --- Index Put deltas ---
    pe_short_chg = {}
    pe_long_chg  = {}
    for p in participants:
        r = _get(p, "Index Puts")
        pe_short_chg[p] = r.get("short_chg", 0)
        pe_long_chg[p]  = r.get("long_chg",  0)

    # --- Index Futures deltas ---
    fut_net = {}
    for p in participants:
        r = _get(p, "Index Futures")
        fut_net[p] = r.get("net_buy_sell", 0)

    # --- Smart writing shares ---
    # Only count additions (positive short_chg = new shorts written)
    smart_ce_write = max(0, ce_short_chg.get("FII", 0)) + max(0, ce_short_chg.get("Pro", 0))
    total_ce_write = sum(max(0, ce_short_chg[p]) for p in participants)
    W_CE_Smart = smart_ce_write / max(1, total_ce_write)

    smart_pe_write = max(0, pe_short_chg.get("FII", 0)) + max(0, pe_short_chg.get("Pro", 0))
    total_pe_write = sum(max(0, pe_short_chg[p]) for p in participants)
    W_PE_Smart = smart_pe_write / max(1, total_pe_write)

    # --- FII Hedge Filter (Rank #4 in signal hierarchy) ---
    # Classify FII Put Long additions as "Portfolio Hedge" (not bearish) if:
    # FII also added Futures Longs AND Pro Desks wrote Puts
    fii_put_long_added = max(0, pe_long_chg.get("FII", 0))
    fii_fut_long       = fut_net.get("FII", 0)
    pro_put_written    = max(0, pe_short_chg.get("Pro", 0))

    fii_hedge_active = (
        fii_put_long_added > 50_000
        and fii_fut_long > 0
        and pro_put_written > 50_000
    )
    fii_hedge_badge = (
        "🛡️ Portfolio Crash Insurance (Hedge) — True Bias is Bullish"
        if fii_hedge_active else ""
    )

    return {
        "W_CE_Smart": round(W_CE_Smart, 4),
        "W_PE_Smart": round(W_PE_Smart, 4),
        "ce_short_chg": ce_short_chg,
        "pe_short_chg": pe_short_chg,
        "ce_long_chg":  ce_long_chg,
        "pe_long_chg":  pe_long_chg,
        "fut_net":      fut_net,
        "fii_hedge_active": fii_hedge_active,
        "fii_hedge_badge":  fii_hedge_badge,
        "smart_ce_written": smart_ce_write,
        "smart_pe_written": smart_pe_write,
        "total_ce_written": total_ce_write,
        "total_pe_written": total_pe_write,
    }


# ---------------------------------------------------------------------------
# 2. Zone Classification (A / B / C / D)
# ---------------------------------------------------------------------------

ZONE_WEIGHTS = {"A": 1.0, "B": 0.65, "C": 0.20, "D": 1.15}

def classify_moneyness_zone(strike: float, spot: float, sigma_pts: float,
                             option_price: float = 0.0) -> dict:
    """
    Classifies a strike into NSE institutional moneyness zones using
    sigma_pts = Spot * (VIX / (100 * sqrt(252))).

    Zones:
      A — Institutional Defense (0 ≤ d_K ≤ 1.25)
      B — Intermediate Wing    (1.25 < d_K ≤ 2.0)
      C — Far-OTM Retail Wing  (d_K > 2.0 or price < ₹15)
      D — ITM Institutional    (strike is ITM by > 1.25σ)
    """
    if sigma_pts <= 0:
        sigma_pts = spot * 0.007  # fallback ~0.7% daily

    d_K = abs(strike - spot) / sigma_pts

    # ITM check
    is_itm = (strike < spot and option_price > (spot - strike)) or \
             (strike > spot and option_price > (strike - spot))

    if is_itm and d_K > 1.25:
        zone = "D"
    elif d_K <= 1.25:
        zone = "A"
    elif d_K <= 2.0:
        zone = "B"
    else:
        zone = "C"

    # Override to C if option price < ₹15 regardless of d_K
    if option_price > 0 and option_price < 15.0 and zone != "D":
        zone = "C"

    return {
        "zone": zone,
        "zone_weight": ZONE_WEIGHTS[zone],
        "d_K": round(d_K, 3),
        "zone_label": {
            "A": "Institutional Defense Zone (ATM ±1.25σ)",
            "B": "Intermediate Wing (1.25–2.0σ)",
            "C": "Far-OTM Retail Lottery Wing (>2σ)",
            "D": "ITM Institutional Zone",
        }[zone],
    }


# ---------------------------------------------------------------------------
# 3. Four-Quadrant Buildup Classifier
# ---------------------------------------------------------------------------

QUADRANT_MAP = {
    "FRESH_WRITING":    {"label": "Fresh Writing (Short Buildup)",   "emoji": "🔴", "color": "#ef4444"},
    "FRESH_BUYING":     {"label": "Fresh Buying (Long Buildup)",     "emoji": "🟢", "color": "#10b981"},
    "SHORT_COVERING":   {"label": "Short Covering (Trapped Writers)", "emoji": "⚡", "color": "#38bdf8"},
    "LONG_UNWINDING":   {"label": "Long Unwinding (Buyers Exiting)", "emoji": "🟡", "color": "#f59e0b"},
    "NEUTRAL":          {"label": "Neutral / Inactive",              "emoji": "⚪", "color": "#94a3b8"},
}

def classify_buildup_quadrant(delta_oi: float, delta_price: float) -> str:
    """
    Returns the 4-quadrant buildup code for a CE or PE strike.
      FRESH_WRITING  : ΔOI > 0, ΔPrice < 0   ← Option Writing (Short Buildup)
      FRESH_BUYING   : ΔOI > 0, ΔPrice ≥ 0   ← Long Buildup
      SHORT_COVERING : ΔOI < 0, ΔPrice > 0   ← Trapped Writers Running Away
      LONG_UNWINDING : ΔOI < 0, ΔPrice ≤ 0   ← Buyers Exiting
      NEUTRAL        : ΔOI == 0
    """
    if delta_oi > 0:
        return "FRESH_WRITING" if delta_price < 0 else "FRESH_BUYING"
    elif delta_oi < 0:
        return "SHORT_COVERING" if delta_price > 0 else "LONG_UNWINDING"
    return "NEUTRAL"


def buildup_info(code: str) -> dict:
    return QUADRANT_MAP.get(code, QUADRANT_MAP["NEUTRAL"])


# ---------------------------------------------------------------------------
# 4. Strike Carry-Over Ratio, Fresh Money Deployed, Strike VWAP
# ---------------------------------------------------------------------------

def compute_strike_metrics(
    delta_oi: float,
    volume_contracts: float,
    lot_size: float,
    close_price: float,
    total_trade_value_lakhs: float,
    total_trading_volume: float,
    opt_type: str,
    strike: float,
) -> dict:
    """
    Computes 3 institutional strike filters:
      1. Carry-Over Ratio = |ΔOI| / max(1, Volume × LotSize)
         > 0.20 → sticky overnight position
         < 0.08 → mostly intraday scalping
      2. Fresh Money Deployed (₹ Crores) = ΔOI × Close_Price (positive only)
      3. Strike VWAP = TotalTradeValue / max(1, TotalTradingVol × LotSize)
         Writer Panic Breakeven (CE): Strike + VWAP
         Writer Panic Breakeven (PE): Strike - VWAP
    """
    lot_size = max(1.0, lot_size)
    vol_contracts = max(1.0, volume_contracts)

    carry_over_ratio = abs(delta_oi) / max(1.0, vol_contracts * lot_size)

    fresh_money_crores = 0.0
    if delta_oi > 0:
        fresh_money_crores = (delta_oi * close_price) / 10_000_000  # ₹ Crores: contracts × price × lot_size / 1Cr

    vwap = total_trade_value_lakhs * 1e5 / max(1.0, total_trading_volume * lot_size) if total_trade_value_lakhs > 0 else close_price

    # Writer Panic / Breakeven Level
    if opt_type.lower() in ("ce", "call"):
        writer_panic = strike + vwap
        panic_label  = f"{int(strike + vwap):,} (CE Breakeven)"
    else:
        writer_panic = strike - vwap
        panic_label  = f"{int(strike - vwap):,} (PE Breakeven)"

    carry_label = "Sticky Overnight" if carry_over_ratio >= 0.20 else ("Intraday Scalping" if carry_over_ratio < 0.08 else "Mixed")

    return {
        "carry_over_ratio":   round(carry_over_ratio, 4),
        "carry_label":        carry_label,
        "fresh_money_crores": round(fresh_money_crores, 2),
        "strike_vwap":        round(vwap, 2),
        "writer_panic":       round(writer_panic, 1),
        "writer_panic_label": panic_label,
    }


# ---------------------------------------------------------------------------
# 5. Smart-Money Wall Score per Strike
# ---------------------------------------------------------------------------

def compute_smart_wall_score(
    opt_type: str,
    delta_oi: float,
    strike_volume: float,
    total_volume: float,
    close_price: float,
    total_oi: float,
    zone_weight: float,
    W_smart: float,
) -> float:
    """
    Smart Call Wall Score (CE) or Smart Put Floor Score (PE) per strike K.

    = max(0, ΔOI_K) × (Vol_K / Σ Vol) × ln(1 + Price_K) × ZoneWeight × W_Smart
      + 0.25 × OI_K × ZoneWeight
    """
    flow_term = (
        max(0.0, delta_oi)
        * (strike_volume / max(1.0, total_volume))
        * math.log(1.0 + max(0.0, close_price))
        * zone_weight
        * W_smart
    )
    inventory_term = 0.25 * total_oi * zone_weight
    return flow_term + inventory_term


# ---------------------------------------------------------------------------
# 6. PCR ATM and WAS Centroid Migration
# ---------------------------------------------------------------------------

def compute_pcr_atm(strikes_data: dict, spot: float, sigma_pts: float) -> dict:
    """
    Computes PCR strictly on Zone A & B strikes (d_K ≤ 1.5σ) so far-OTM noise
    doesn't distort the PCR signal. Also computes Volume-Weighted centroid
    of Put vs. Call strikes (WAS_PE, WAS_CE).
    """
    total_pe_oi = 0
    total_ce_oi = 0
    pe_was_num  = 0.0
    pe_was_den  = 0.0
    ce_was_num  = 0.0
    ce_was_den  = 0.0

    for strike, data in strikes_data.items():
        d_K = abs(float(strike) - spot) / max(1.0, sigma_pts)
        if d_K > 1.5:
            continue

        ce = data.get("ce", {})
        pe = data.get("pe", {})
        ce_oi  = ce.get("oi", 0)
        pe_oi  = pe.get("oi", 0)
        ce_vol = ce.get("volume", 0)
        pe_vol = pe.get("volume", 0)

        total_pe_oi += pe_oi
        total_ce_oi += ce_oi

        pe_was_num += float(strike) * pe_vol
        pe_was_den += pe_vol
        ce_was_num += float(strike) * ce_vol
        ce_was_den += ce_vol

    pcr_atm = total_pe_oi / max(1, total_ce_oi)
    was_pe  = pe_was_num / max(1.0, pe_was_den)
    was_ce  = ce_was_num / max(1.0, ce_was_den)

    return {
        "pcr_atm":       round(pcr_atm, 4),
        "pcr_atm_label": "Bullish (>1.2)" if pcr_atm > 1.2 else ("Bearish (<0.8)" if pcr_atm < 0.8 else "Neutral"),
        "was_pe":        round(was_pe, 1),
        "was_ce":        round(was_ce, 1),
        "total_pe_oi":   total_pe_oi,
        "total_ce_oi":   total_ce_oi,
    }


# ---------------------------------------------------------------------------
# 7. Master Matcher — Full Strike Classification
# ---------------------------------------------------------------------------

def match_participants_to_strikes(
    oi_engine_result:    dict,
    option_chain_result: dict,
    symbol:              str  = "NIFTY",
    lot_size:            float = 25.0,
    prev_was_pe:         Optional[float] = None,
    prev_was_ce:         Optional[float] = None,
) -> dict:
    """
    Full Stage 3 pipeline:
      1. Extracts Smart Writing Shares and FII Hedge Flag from Stage 1
      2. Classifies every strike by zone, quadrant, carry-over, VWAP, Wall Score
      3. Identifies K_Floor, K_Ceiling, K_Squeeze, K_RetailTrap
      4. Computes PCR_ATM and WAS centroid migration

    Returns a structured dict ready for the Stage 4 candlestick predictor.
    """
    spot = float(option_chain_result.get("spot") or option_chain_result.get("spot_price") or 25000.0)

    # Normalize strikes_dict: handle dict or list format from get_option_chain_data()
    strikes_dict = option_chain_result.get("strikes_dict", {})
    if not strikes_dict and "strikes" in option_chain_result:
        raw_strikes = option_chain_result["strikes"]
        if isinstance(raw_strikes, list):
            strikes_dict = {}
            for item in raw_strikes:
                k = float(item.get("strike", 0))
                if k > 0:
                    ce_data = item.get("call") or item.get("ce") or {}
                    pe_data = item.get("put") or item.get("pe") or {}
                    strikes_dict[k] = {"ce": ce_data, "pe": pe_data}
        elif isinstance(raw_strikes, dict):
            strikes_dict = raw_strikes

    # --- σ_pts from daily_expected_move (pre-computed by option_chain_engine) ---
    daily_move = (
        option_chain_result.get("daily_expected_move")
        or (option_chain_result.get("probabilistic_model") or {}).get("daily_expected_move")
        or (spot * 0.007)
    )
    sigma_pts = float(daily_move)
    if sigma_pts <= 0:
        sigma_pts = spot * 0.007

    # --- Smart Writing Shares from Stage 1 ---
    smart_shares = compute_smart_writing_shares(oi_engine_result)
    W_CE = smart_shares["W_CE_Smart"]
    W_PE = smart_shares["W_PE_Smart"]

    # --- Total volumes for volume-share computation ---
    total_ce_vol = sum(
        strikes_dict[k].get("ce", {}).get("volume", 0)
        for k in strikes_dict
    )
    total_pe_vol = sum(
        strikes_dict[k].get("pe", {}).get("volume", 0)
        for k in strikes_dict
    )

    # --- Per-strike classification ---
    classified = {}
    for k_raw, data in strikes_dict.items():
        k = float(k_raw)
        ce = data.get("ce", {})
        pe = data.get("pe", {})

        ce_ltp   = float(ce.get("ltp", 0) or 0)
        pe_ltp   = float(pe.get("ltp", 0) or 0)
        ce_prev  = float(ce.get("prev_price", ce_ltp) or ce_ltp)
        pe_prev  = float(pe.get("prev_price", pe_ltp) or pe_ltp)
        ce_chg_p = float(ce.get("chg_p", ce_ltp - ce_prev) or 0)
        pe_chg_p = float(pe.get("chg_p", pe_ltp - pe_prev) or 0)
        ce_chg_oi = int(ce.get("chg_oi", 0) or 0)
        pe_chg_oi = int(pe.get("chg_oi", 0) or 0)
        ce_oi   = int(ce.get("oi", 0) or 0)
        pe_oi   = int(pe.get("oi", 0) or 0)
        ce_vol  = int(ce.get("volume", 0) or 0)
        pe_vol  = int(pe.get("volume", 0) or 0)
        ce_tv   = float(ce.get("total_trade_value", 0) or 0)
        pe_tv   = float(pe.get("total_trade_value", 0) or 0)

        # Zone
        ce_zone = classify_moneyness_zone(k, spot, sigma_pts, ce_ltp)
        pe_zone = classify_moneyness_zone(k, spot, sigma_pts, pe_ltp)

        # Quadrant
        ce_quad = classify_buildup_quadrant(ce_chg_oi, ce_chg_p)
        pe_quad = classify_buildup_quadrant(pe_chg_oi, pe_chg_p)

        # Metrics
        ce_metrics = compute_strike_metrics(ce_chg_oi, ce_vol, lot_size, ce_ltp, ce_tv, ce_vol, "ce", k)
        pe_metrics = compute_strike_metrics(pe_chg_oi, pe_vol, lot_size, pe_ltp, pe_tv, pe_vol, "pe", k)

        # Smart Wall Scores
        ce_score = compute_smart_wall_score("ce", ce_chg_oi, ce_vol, total_ce_vol, ce_ltp, ce_oi, ce_zone["zone_weight"], W_CE)
        pe_score = compute_smart_wall_score("pe", pe_chg_oi, pe_vol, total_pe_vol, pe_ltp, pe_oi, pe_zone["zone_weight"], W_PE)

        classified[k] = {
            "strike": k,
            "ce": {
                "oi": ce_oi, "chg_oi": ce_chg_oi, "ltp": ce_ltp, "volume": ce_vol,
                "chg_p": ce_chg_p, "prev_price": ce_prev,
                "zone": ce_zone["zone"], "zone_weight": ce_zone["zone_weight"],
                "zone_label": ce_zone["zone_label"], "d_K": ce_zone["d_K"],
                "quadrant": ce_quad, "quadrant_info": buildup_info(ce_quad),
                "smart_wall_score": round(ce_score, 2),
                **ce_metrics,
            },
            "pe": {
                "oi": pe_oi, "chg_oi": pe_chg_oi, "ltp": pe_ltp, "volume": pe_vol,
                "chg_p": pe_chg_p, "prev_price": pe_prev,
                "zone": pe_zone["zone"], "zone_weight": pe_zone["zone_weight"],
                "zone_label": pe_zone["zone_label"], "d_K": pe_zone["d_K"],
                "quadrant": pe_quad, "quadrant_info": buildup_info(pe_quad),
                "smart_put_floor_score": round(pe_score, 2),
                **pe_metrics,
            },
        }

    # --- Identify Key Institutional Strikes ---
    step = 50.0 if symbol.upper() in ("NIFTY", "FINNIFTY") else 100.0
    sorted_strikes = sorted(classified.keys())

    # K_Ceiling: Top 2 CE FRESH_WRITING strikes at or ABOVE Spot - 0.25σ
    ceil_candidates = [
        (k, classified[k]["ce"]["smart_wall_score"])
        for k in sorted_strikes
        if k >= spot - 0.25 * sigma_pts
        and classified[k]["ce"]["quadrant"] == "FRESH_WRITING"
    ]
    ceil_candidates.sort(key=lambda x: x[1], reverse=True)
    if not ceil_candidates:
        above = [(k, classified[k]["ce"]["smart_wall_score"]) for k in sorted_strikes if k >= spot]
        above.sort(key=lambda x: x[1], reverse=True)
        K_ceiling   = above[0][0] if above else (round((spot + sigma_pts) / step) * step)
        K_ceiling_2 = above[1][0] if len(above) > 1 else K_ceiling
    else:
        K_ceiling   = ceil_candidates[0][0]
        K_ceiling_2 = ceil_candidates[1][0] if len(ceil_candidates) > 1 else K_ceiling

    # K_Floor: Top 2 PE FRESH_WRITING strikes at or BELOW Spot + 0.25σ
    floor_candidates = [
        (k, classified[k]["pe"]["smart_put_floor_score"])
        for k in sorted_strikes
        if k <= spot + 0.25 * sigma_pts
        and classified[k]["pe"]["quadrant"] == "FRESH_WRITING"
    ]
    floor_candidates.sort(key=lambda x: x[1], reverse=True)
    if not floor_candidates:
        below = [(k, classified[k]["pe"]["smart_put_floor_score"]) for k in sorted_strikes if k <= spot]
        below.sort(key=lambda x: x[1], reverse=True)
        K_floor   = below[0][0] if below else (round((spot - sigma_pts) / step) * step)
        K_floor_2 = below[1][0] if len(below) > 1 else K_floor
    else:
        K_floor   = floor_candidates[0][0]
        K_floor_2 = floor_candidates[1][0] if len(floor_candidates) > 1 else K_floor

    # K_Squeeze: Near-ATM SHORT_COVERING with high CE volume
    squeeze_candidates = [
        (k, classified[k]["ce"]["volume"])
        for k in sorted_strikes
        if abs(k - spot) <= 1.5 * sigma_pts
        and classified[k]["ce"]["quadrant"] == "SHORT_COVERING"
    ]
    squeeze_candidates.sort(key=lambda x: x[1], reverse=True)
    K_squeeze = squeeze_candidates[0][0] if squeeze_candidates else None

    # K_RetailTrap: Far-OTM (d_K > 1.5) with large FRESH_BUYING CE (retail buying cheap calls)
    retail_trap_ce = [
        (k, classified[k]["ce"]["chg_oi"])
        for k in sorted_strikes
        if classified[k]["ce"]["d_K"] > 1.5
        and classified[k]["ce"]["quadrant"] == "FRESH_BUYING"
        and classified[k]["ce"]["chg_oi"] > 0
    ]
    retail_trap_ce.sort(key=lambda x: x[1], reverse=True)
    K_retail_trap = retail_trap_ce[0][0] if retail_trap_ce else None

    # --- PCR ATM and WAS centroid ---
    pcr_was = compute_pcr_atm(strikes_dict, spot, sigma_pts)

    was_pe_shift = None
    was_ce_shift = None
    if prev_was_pe is not None:
        was_pe_shift = "higher" if pcr_was["was_pe"] > prev_was_pe else ("lower" if pcr_was["was_pe"] < prev_was_pe else "flat")
    if prev_was_ce is not None:
        was_ce_shift = "higher" if pcr_was["was_ce"] > prev_was_ce else ("lower" if pcr_was["was_ce"] < prev_was_ce else "flat")

    # --- VWAP of primary floor/ceiling for candlestick predictor ---
    k_floor_vwap  = classified.get(K_floor,   {}).get("pe", {}).get("strike_vwap", 0)
    k_ceil_vwap   = classified.get(K_ceiling,  {}).get("ce", {}).get("strike_vwap", 0)
    k_floor_ltp   = classified.get(K_floor,   {}).get("pe", {}).get("ltp", 0)
    k_ceil_ltp    = classified.get(K_ceiling,  {}).get("ce", {}).get("ltp", 0)
    k_floor_panic = classified.get(K_floor,   {}).get("pe", {}).get("writer_panic", K_floor - sigma_pts * 0.5)
    k_ceil_panic  = classified.get(K_ceiling,  {}).get("ce", {}).get("writer_panic", K_ceiling + sigma_pts * 0.5)

    k_floor_2_ltp   = classified.get(K_floor_2,   {}).get("pe", {}).get("ltp", 0)
    k_ceil_2_ltp    = classified.get(K_ceiling_2,  {}).get("ce", {}).get("ltp", 0)
    k_floor_2_panic = classified.get(K_floor_2,   {}).get("pe", {}).get("writer_panic", K_floor_2 - sigma_pts * 0.5)
    k_ceil_2_panic  = classified.get(K_ceiling_2,  {}).get("ce", {}).get("writer_panic", K_ceiling_2 + sigma_pts * 0.5)

    return {
        "symbol":            symbol,
        "spot":              spot,
        "sigma_pts":         round(sigma_pts, 1),
        "smart_shares":      smart_shares,
        "classified_strikes": classified,
        "key_strikes": {
            "K_floor":     K_floor,
            "K_floor_2":   K_floor_2,
            "K_ceiling":   K_ceiling,
            "K_ceiling_2": K_ceiling_2,
            "K_squeeze":   K_squeeze,
            "K_retail_trap": K_retail_trap,
        },
        "floor_vwap":      round(k_floor_vwap, 2),
        "ceiling_vwap":    round(k_ceil_vwap, 2),
        "floor_ltp":       round(k_floor_ltp, 2),
        "ceiling_ltp":     round(k_ceil_ltp, 2),
        "floor_panic":     round(k_floor_panic, 1),
        "ceiling_panic":   round(k_ceil_panic, 1),
        "floor_2_ltp":     round(k_floor_2_ltp, 2),
        "ceiling_2_ltp":   round(k_ceil_2_ltp, 2),
        "floor_2_panic":   round(k_floor_2_panic, 1),
        "ceiling_2_panic": round(k_ceil_2_panic, 1),
        "pcr_atm":         pcr_was["pcr_atm"],
        "pcr_atm_label":   pcr_was["pcr_atm_label"],
        "was_pe":          pcr_was["was_pe"],
        "was_ce":          pcr_was["was_ce"],
        "was_pe_shift":    was_pe_shift,
        "was_ce_shift":    was_ce_shift,
    }
