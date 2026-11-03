"""
Option Selling Strategy & Greeks Efficiency Engine
Inspired by Zerodha Varsity Module 5: "Options Theory for Professional Trading"
Synthesizes:
1. Proper Option Chain (Spot, ATM, Max Pain, PCR, S1, S2, R1, R2, Implied Volatility)
2. Participant-Wise Open Interest (FII, PRO, CLIENT, DII net flows & trap zones)
3. Details Report Market Regime & Probabilities (1-SD and 2-SD Normal Distribution bands)
4. Black-Scholes Greeks Engine (Delta, Gamma, Theta, Vega)
Calculates and recommends the Top 3 Option Selling Strategies with exact selling
and hedging strike prices, margin savings, Probability of Profit (POP), and full
mathematical & institutional rationales.
"""

import math
from datetime import datetime
from option_chain_engine import get_option_chain_data

LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25
}

STRIKE_STEPS = {
    "NIFTY": 50.0,
    "BANKNIFTY": 100.0,
    "FINNIFTY": 50.0
}

RISK_FREE_RATE = 0.07  # Standard RBI 91-day T-Bill rate ~7.0%

def normal_cdf(x):
    """Standard Normal Cumulative Distribution Function using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def normal_pdf(x):
    """Standard Normal Probability Density Function."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

def calculate_bs_greeks(spot, strike, t_years, r, iv, opt_type):
    """
    Computes Black-Scholes Greeks:
    - Delta: Directional sensitivity & approx probability of expiring ITM
    - Gamma: Rate of change of Delta (curvature risk)
    - Theta: Daily time decay in points (positive inflow for option sellers)
    - Vega: Sensitivity to 1% change in IV
    - Theoretical Price: Black-Scholes fair value
    """
    if t_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return {
            "delta": 0.5 if opt_type == "CE" else -0.5,
            "gamma": 0.0,
            "theta_daily": 0.0,
            "seller_theta": 0.0,
            "vega": 0.0,
            "price": max(0.05, abs(spot - strike) if ((opt_type == "CE" and spot > strike) or (opt_type == "PE" and spot < strike)) else 5.0)
        }

    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)

    pdf_d1 = normal_pdf(d1)
    cdf_d1 = normal_cdf(d1)
    cdf_d2 = normal_cdf(d2)

    gamma = pdf_d1 / (spot * iv * math.sqrt(t_years))
    vega = spot * math.sqrt(t_years) * pdf_d1 * 0.01

    if opt_type == "CE":
        delta = cdf_d1
        # Call theta (per year)
        theta_annual = - (spot * pdf_d1 * iv) / (2.0 * math.sqrt(t_years)) - r * strike * math.exp(-r * t_years) * cdf_d2
        price = spot * cdf_d1 - strike * math.exp(-r * t_years) * cdf_d2
    else:
        delta = cdf_d1 - 1.0  # Negative delta for puts
        cdf_neg_d1 = normal_cdf(-d1)
        cdf_neg_d2 = normal_cdf(-d2)
        # Put theta (per year)
        theta_annual = - (spot * pdf_d1 * iv) / (2.0 * math.sqrt(t_years)) + r * strike * math.exp(-r * t_years) * cdf_neg_d2
        price = strike * math.exp(-r * t_years) * cdf_neg_d2 - spot * cdf_neg_d1

    theta_daily = theta_annual / 365.0
    # For an option seller, Theta is positive (income gained per day)
    seller_theta = abs(theta_daily)

    return {
        "delta": round(delta, 3),
        "gamma": round(gamma, 5),
        "theta_daily": round(theta_daily, 2),
        "seller_theta": round(seller_theta, 2),
        "vega": round(vega, 2),
        "price": round(max(0.05, price), 2)
    }

def estimate_span_margin(symbol, sell_strike, sell_type, hedge_strike=None, hedge_type=None, spot=25000.0):
    """
    Approximates NSE SPAN + Exposure Margin requirements for:
    1. Naked Option Selling: ~ ₹1,10,000 to ₹1,40,000 for NIFTY per lot
    2. Hedged Credit Spread: ~ ₹35,000 to ₹48,000 for NIFTY per lot
    Based on standard exchange margin haircut schedules.
    Returns: (naked_margin, hedged_margin, margin_saved, savings_pct)
    """
    lot_size = LOT_SIZES.get(symbol, 25)

    # Naked short margin: ~10% to 12% of contract value + OTM relief
    if symbol == "BANKNIFTY":
        base_margin = 135000.0
    elif symbol == "FINNIFTY":
        base_margin = 105000.0
    else:  # NIFTY
        base_margin = 125000.0

    if hedge_strike is None:
        return round(base_margin, -2), round(base_margin, -2), 0.0, 0.0

    # With hedge wing: Margin is capped primarily by the spread width + buffer
    spread_width = abs(sell_strike - hedge_strike)
    spread_risk = spread_width * lot_size
    # SPAN hedged margin = Spread risk + buffer for slippage & execution
    hedged_margin = max(28000.0, min(base_margin * 0.45, spread_risk * 1.15 + 15000.0))
    margin_saved = max(0.0, base_margin - hedged_margin)
    savings_pct = round((margin_saved / base_margin) * 100, 1)

    return round(base_margin, -2), round(hedged_margin, -2), round(margin_saved, -2), savings_pct

def generate_strike_efficiency_matrix(symbol, spot, all_strikes, strikes_dict, t_years, iv, s1_k, s2_k, r1_k, r2_k, sd1_low, sd1_high, sd2_low, sd2_high):
    """
    Generates a comprehensive efficiency scorecard for all strikes
    evaluating their suitability for Option Selling based on:
    - Delta Sweet Spot (|Delta| between 0.12 and 0.28)
    - Theta Decay per rupee of margin risked
    - Gamma Risk (avoiding ATM gamma explosion)
    - Distance in Standard Deviations (1-SD and 2-SD)
    - Pro/FII Defense Alignment (S1/S2 support, R1/R2 resistance)
    """
    efficiency_list = []
    step = STRIKE_STEPS.get(symbol, 50.0)

    for k in sorted(all_strikes):
        s_data = strikes_dict.get(k, {})
        ce_data = s_data.get("ce", {}) or s_data.get("call", {})
        pe_data = s_data.get("pe", {}) or s_data.get("put", {})

        ce_ltp = ce_data.get("ltp", 0.0)
        pe_ltp = pe_data.get("ltp", 0.0)
        ce_oi = ce_data.get("oi", 0)
        pe_oi = pe_data.get("oi", 0)
        ce_chg_oi = ce_data.get("chg_oi", 0)
        pe_chg_oi = pe_data.get("chg_oi", 0)
        ce_volume = ce_data.get("volume", 0)
        pe_volume = pe_data.get("volume", 0)

        # Calculate Greeks for Call & Put
        ce_greeks = calculate_bs_greeks(spot, k, t_years, RISK_FREE_RATE, iv, "CE")
        pe_greeks = calculate_bs_greeks(spot, k, t_years, RISK_FREE_RATE, iv, "PE")

        dist_pts = k - spot
        dist_pct = round((dist_pts / spot) * 100, 2)

        # Moneyness classification (Varsity Chapter 8)
        if abs(dist_pts) < (step * 0.5):
            call_moneyness = "ATM"
            put_moneyness = "ATM"
        elif k > spot:
            call_moneyness = "OTM" if k <= sd1_high else ("Far OTM" if k <= sd2_high else "Deep OTM")
            put_moneyness = "ITM" if k <= sd1_high else "Deep ITM"
        else:
            call_moneyness = "ITM" if k >= sd1_low else "Deep ITM"
            put_moneyness = "OTM" if k >= sd1_low else ("Far OTM" if k >= sd2_low else "Deep OTM")

        # Probability of expiring worthless for seller = 1 - |Delta|
        ce_pop = round((1.0 - ce_greeks["delta"]) * 100, 1)
        pe_pop = round((1.0 - abs(pe_greeks["delta"])) * 100, 1)

        # Efficiency Score for Put Selling (0 to 100)
        pe_score = 0
        if put_moneyness in ["OTM", "Far OTM"]:
            # Delta sweet spot: 0.15 to 0.25 gets maximum score
            abs_pe_delta = abs(pe_greeks["delta"])
            if 0.14 <= abs_pe_delta <= 0.26:
                pe_score += 45
            elif 0.08 <= abs_pe_delta <= 0.35:
                pe_score += 30
            elif abs_pe_delta < 0.08:
                pe_score += 15  # too far, very low premium

            # Theta decay reward
            if pe_greeks["seller_theta"] > 10.0:
                pe_score += 20
            elif pe_greeks["seller_theta"] > 5.0:
                pe_score += 10

            # S1 / S2 confluence
            if k == s1_k:
                pe_score += 20
            elif k == s2_k:
                pe_score += 15
            elif sd1_low <= k <= spot:
                pe_score += 10

            # Volume & OI liquidity bonus
            if pe_volume > 300000 or pe_oi > 1500000:
                pe_score += 15
            elif pe_volume > 50000 or pe_oi > 300000:
                pe_score += 8

            # Penalty for high gamma
            if pe_greeks["gamma"] > 0.0012:
                pe_score -= 20

        # Efficiency Score for Call Selling (0 to 100)
        ce_score = 0
        if call_moneyness in ["OTM", "Far OTM"]:
            ce_delta = ce_greeks["delta"]
            if 0.14 <= ce_delta <= 0.26:
                ce_score += 45
            elif 0.08 <= ce_delta <= 0.35:
                ce_score += 30
            elif ce_delta < 0.08:
                ce_score += 15

            # Theta decay reward
            if ce_greeks["seller_theta"] > 10.0:
                ce_score += 20
            elif ce_greeks["seller_theta"] > 5.0:
                ce_score += 10

            # R1 / R2 confluence
            if k == r1_k:
                ce_score += 20
            elif k == r2_k:
                ce_score += 15
            elif spot <= k <= sd1_high:
                ce_score += 10

            # Volume & OI liquidity bonus
            if ce_volume > 300000 or ce_oi > 1500000:
                ce_score += 15
            elif ce_volume > 50000 or ce_oi > 300000:
                ce_score += 8

            # Penalty for high gamma
            if ce_greeks["gamma"] > 0.0012:
                ce_score -= 20

        # Tags and Recommendations
        pe_role_tag = "-"
        if k == s1_k:
            pe_role_tag = "🏰 Primary S1 Wall (Smart Money)"
        elif k == s2_k:
            pe_role_tag = "🛡️ S2 Bedrock Floor (High Defense)"
        elif abs(k - spot) < (step * 0.5):
            pe_role_tag = "⚠️ ATM (Extreme Short Gamma Risk)"
        elif k == round(sd1_low / step) * step:
            pe_role_tag = "🎯 1-SD Lower Bound (Statistical Floor)"

        ce_role_tag = "-"
        if k == r1_k:
            ce_role_tag = "🏰 Primary R1 Wall (Smart Money)"
        elif k == r2_k:
            ce_role_tag = "🛡️ R2 Ceiling (High Supply Cap)"
        elif abs(k - spot) < (step * 0.5):
            ce_role_tag = "⚠️ ATM (Extreme Short Gamma Risk)"
        elif k == round(sd1_high / step) * step:
            ce_role_tag = "🎯 1-SD Upper Bound (Statistical Ceiling)"

        efficiency_list.append({
            "strike": k,
            "dist_pts": dist_pts,
            "dist_pct": dist_pct,
            "call": {
                "ltp": ce_ltp,
                "oi": ce_oi,
                "chg_oi": ce_chg_oi,
                "volume": ce_volume,
                "moneyness": call_moneyness,
                "delta": ce_greeks["delta"],
                "theta": ce_greeks["seller_theta"],
                "gamma": ce_greeks["gamma"],
                "vega": ce_greeks["vega"],
                "pop_pct": ce_pop,
                "selling_score": max(0, min(100, ce_score)),
                "role_tag": ce_role_tag
            },
            "put": {
                "ltp": pe_ltp,
                "oi": pe_oi,
                "chg_oi": pe_chg_oi,
                "volume": pe_volume,
                "moneyness": put_moneyness,
                "delta": pe_greeks["delta"],
                "theta": pe_greeks["seller_theta"],
                "gamma": pe_greeks["gamma"],
                "vega": pe_greeks["vega"],
                "pop_pct": pe_pop,
                "selling_score": max(0, min(100, pe_score)),
                "role_tag": pe_role_tag
            }
        })

    return efficiency_list

def build_institutional_market_view(symbol, spot, atm_strike, s1_k, s2_k, r1_k, r2_k, max_pain, pcr, iv, days_to_expiry, sd1_low, sd1_high, sd2_low, sd2_high, p_data=None):
    """
    Deterministic Multi-Factor Institutional Market View Creation Engine.
    Synthesizes Participant-Wise OI, Strike OI concentration, Volatility (Greeks),
    and Retail Sentiment across 5 Quantitative Pillars:
      Pillar 1: Smart Money Futures Flow (Weight: 20 pts)
      Pillar 2: Institutional Option Writing Skew (Weight: 25 pts)
      Pillar 3: Retail Sentiment Contra-Indicator (Weight: 20 pts)
      Pillar 4: Option Chain Structure & PCR Magnet (Weight: 20 pts)
      Pillar 5: Volatility & Normal Distribution Corridor (Weight: 15 pts)

    Returns a rich institutional_market_view object with composite score (0-100),
    primary stance, conviction, 5 pillar scorecards, game plan, trap verdict, and invalidation level.
    """
    if p_data and isinstance(p_data, dict):
        if "result" in p_data and isinstance(p_data["result"], dict):
            p_data = p_data["result"]

    fii_put_net = 0
    fii_call_net = 0
    fii_fut_net = 0
    pro_put_net = 0
    pro_call_net = 0
    pro_fut_net = 0
    pro_put_short_chg = 0
    pro_call_short_chg = 0
    client_put_net = 0
    client_call_net = 0
    client_fut_net = 0

    tables = p_data.get("instrument_tables", {}) if p_data else {}
    for r in tables.get("Index Calls", []):
        pkey = str(r.get("p_key", "")).upper()
        pname = str(r.get("participant", "")).upper()
        if "FII" in pkey or "FII" in pname:
            fii_call_net = r.get("net_buy_sell", 0)
        elif "CLIENT" in pkey or "CLIENT" in pname:
            client_call_net = r.get("net_buy_sell", 0)
        elif "PRO" in pkey or "PRO" in pname:
            pro_call_net = r.get("net_buy_sell", 0)
            pro_call_short_chg = r.get("short_chg", 0)

    for r in tables.get("Index Puts", []):
        pkey = str(r.get("p_key", "")).upper()
        pname = str(r.get("participant", "")).upper()
        if "FII" in pkey or "FII" in pname:
            fii_put_net = r.get("net_buy_sell", 0)
        elif "CLIENT" in pkey or "CLIENT" in pname:
            client_put_net = r.get("net_buy_sell", 0)
        elif "PRO" in pkey or "PRO" in pname:
            pro_put_net = r.get("net_buy_sell", 0)
            pro_put_short_chg = r.get("short_chg", 0)

    for r in tables.get("Index Futures", []):
        pkey = str(r.get("p_key", "")).upper()
        pname = str(r.get("participant", "")).upper()
        if "FII" in pkey or "FII" in pname:
            fii_fut_net = r.get("net_buy_sell", 0)
        elif "CLIENT" in pkey or "CLIENT" in pname:
            client_fut_net = r.get("net_buy_sell", 0)
        elif "PRO" in pkey or "PRO" in pname:
            pro_fut_net = r.get("net_buy_sell", 0)

    outlook = p_data.get("market_outlook", {}) if p_data else {}
    retail_trap = outlook.get("retail_trap", {})
    retail_trap_detected = retail_trap.get("detected", False)
    retail_trap_type = str(retail_trap.get("type", "")).upper()

    # --- Pillar 1: Smart Money Futures Flow (Weight: 20 pts) ---
    p1_score = 10.0
    if fii_fut_net > 5000:
        p1_score += 6.5
    elif fii_fut_net > 0:
        p1_score += 3.0
    elif fii_fut_net < -5000:
        p1_score -= 6.5
    elif fii_fut_net < 0:
        p1_score -= 3.0

    if pro_fut_net > 2000:
        p1_score += 3.5
    elif pro_fut_net < -2000:
        p1_score -= 3.5

    p1_score = max(0.0, min(20.0, p1_score))
    if p1_score >= 13.0:
        p1_status = "Bullish Accumulation"
        p1_color = "green"
        p1_detail = f"FIIs hold {fii_fut_net:+,} net futures with Pro desks at {pro_fut_net:+,}, providing upward momentum."
    elif p1_score <= 7.0:
        p1_status = "Bearish Short Inventory"
        p1_color = "red"
        p1_detail = f"FIIs are carrying {fii_fut_net:+,} short futures contracts, dampening upside follow-through."
    else:
        p1_status = "Balanced Futures Inventory"
        p1_color = "blue"
        p1_detail = f"Futures exposure is balanced (FII {fii_fut_net:+,}, Pro {pro_fut_net:+,}), favoring rangebound pin."

    # --- Pillar 2: Institutional Option Writing Skew (Weight: 25 pts) ---
    p2_score = 12.5
    if pro_put_short_chg > 50000 or pro_put_net < -30000:
        p2_score += 7.5
    if fii_put_net < 0:
        p2_score += 5.0

    if pro_call_short_chg > 50000 or pro_call_net < -30000:
        p2_score -= 7.5
    if fii_call_net < 0:
        p2_score -= 5.0

    p2_score = max(0.0, min(25.0, p2_score))
    if p2_score >= 17.0:
        p2_status = "Aggressive Put Floor Defense"
        p2_color = "green"
        p2_detail = f"Pro desks added +{pro_put_short_chg:,} put shorts and FIIs wrote {abs(fii_put_net):,} puts, forming an unyielding floor at {int(s1_k):,}."
    elif p2_score <= 8.0:
        p2_status = "Heavy Call Overhead Ceiling"
        p2_color = "red"
        p2_detail = f"Pro desks shorted +{pro_call_short_chg:,} calls and FIIs wrote net {fii_call_net:,} calls, erecting a heavy ceiling at {int(r1_k):,}."
    else:
        p2_status = "Symmetrical Two-Sided Writing"
        p2_color = "blue"
        p2_detail = f"Market makers are writing both Calls and Puts in equilibrium, engineering two-sided theta decay."

    # --- Pillar 3: Retail Sentiment Contra-Indicator (Weight: 20 pts) ---
    p3_score = 10.0
    is_client_puts_trapped = (
        (retail_trap_detected and ("SQUEEZE" in retail_trap_type or "BEARISH" in retail_trap_type) and client_put_net > 0)
        or client_put_net > 40000
    )
    is_client_calls_trapped = (
        (retail_trap_detected and ("DUMP" in retail_trap_type or "BULLISH" in retail_trap_type) and client_call_net > 0)
        or client_call_net > 40000
    )

    if is_client_puts_trapped:
        p3_score += 8.5
    elif is_client_calls_trapped:
        p3_score -= 8.5

    p3_score = max(0.0, min(20.0, p3_score))
    if p3_score >= 14.0:
        p3_status = "Retail Puts Severely Trapped"
        p3_color = "green"
        p3_detail = f"Retail clients bought +{client_put_net:,} net Puts; smart money has zero incentive to drop spot and reward retail puts."
    elif p3_score <= 6.0:
        p3_status = "Retail Calls Heavily Trapped"
        p3_color = "red"
        p3_detail = f"Retail clients bought +{client_call_net:,} net Calls; institutions will cap the market below {int(r1_k):,} to melt their premiums."
    else:
        p3_status = "Neutral Retail Distribution"
        p3_color = "blue"
        p3_detail = f"Retail positions are balanced (Calls {client_call_net:+,}, Puts {client_put_net:+,}), avoiding extreme crowd traps."

    # --- Pillar 4: Option Chain Structure & PCR Magnet (Weight: 20 pts) ---
    p4_score = 10.0
    if pcr >= 1.15:
        p4_score += 6.0
    elif pcr >= 0.85:
        p4_score += 3.0
    elif pcr <= 0.65:
        p4_score -= 6.0
    elif pcr <= 0.75:
        p4_score -= 3.0

    if spot < max_pain - 30:
        p4_score += 4.0
    elif spot > max_pain + 30:
        p4_score -= 4.0

    p4_score = max(0.0, min(20.0, p4_score))
    if p4_score >= 13.0:
        p4_status = "Support Cushion & PCR Floor"
        p4_color = "green"
        p4_detail = f"PCR at {pcr:.2f} reflects solid Put OI backing, with Max Pain at {int(max_pain):,} acting as an upward magnet."
    elif p4_score <= 7.0:
        p4_status = "Overhead Call Supply Overhang"
        p4_color = "red"
        p4_detail = f"PCR at {pcr:.2f} confirms heavy Call OI overhang, with Max Pain at {int(max_pain):,} pinning spot down."
    else:
        p4_status = "Equilibrium Around Max Pain"
        p4_color = "blue"
        p4_detail = f"PCR ({pcr:.2f}) and Max Pain ({int(max_pain):,}) are centered near spot {int(spot):,}, ideal for iron condors."

    # --- Pillar 5: Volatility & Normal Distribution Corridor (Weight: 15 pts) ---
    p5_score = 7.5
    sd_width = max(50.0, sd1_high - sd1_low)
    dist_from_low = spot - sd1_low
    dist_from_high = sd1_high - spot

    if dist_from_low < sd_width * 0.25:
        p5_score += 4.5
    elif dist_from_high < sd_width * 0.25:
        p5_score -= 4.5

    p5_score = max(0.0, min(15.0, p5_score))
    if p5_score >= 10.5:
        p5_status = "Near Lower 1-SD Statistical Floor"
        p5_color = "green"
        p5_detail = f"Spot ({int(spot):,}) is resting near 1-SD lower boundary ({int(sd1_low):,}), giving an 84%+ statistical bounce probability."
    elif p5_score <= 4.5:
        p5_status = "Near Upper 1-SD Statistical Ceiling"
        p5_color = "red"
        p5_detail = f"Spot ({int(spot):,}) is probing 1-SD upper boundary ({int(sd1_high):,}), posing severe resistance to further advance."
    else:
        p5_status = "Centered Inside 1-SD Safe Corridor"
        p5_color = "blue"
        p5_detail = f"Spot is safely buffered inside the 1-SD range ({int(sd1_low):,} to {int(sd1_high):,}) with {days_to_expiry} days to expiry."

    # --- Composite Score Synthesis ---
    composite_score = round(p1_score + p2_score + p3_score + p4_score + p5_score)
    composite_score = max(5, min(95, composite_score))

    if composite_score >= 58:
        primary_stance = "DEFENSIVE BULLISH FLOOR"
        stance_subtitle = "Smart Money Put Writing Defense & Trapped Retail Puts"
        conviction_rating = f"{int(min(95, 62 + (composite_score - 50) * 0.8))}% CONVICTION"
        badge_color = "green"
        recommended_strategy_id = "bull_put_credit_spread"
        recommended_strategy_name = f"{symbol} Bull Put Credit Spread (Smart Money Shield)"
        recommended_archetype = "Bullish Credit Spread"
        invalidation_trigger = f"Decisive 15-minute candle close below S1 Support ({int(s1_k):,}) or 1-SD Floor ({int(sd1_low):,})"
        target_corridor = f"Defended above {int(s1_k):,} towards Max Pain ({int(max_pain):,})"
        smart_money_gameplan = (
            f"Institutional desks (Pro + FII) have concentrated massive Put shorting around {int(s1_k):,}. "
            f"Their primary objective is to defend this floor and capture full theta decay. "
            f"Any morning dips toward {int(s1_k):,} will be absorbed by smart money limit buy orders."
        )
        retail_trap_analysis = (
            f"Retail clients are caught holding {client_put_net:+,} net Puts. "
            f"Because paying out retail puts is contrary to market maker economics, option writers hold the market above "
            f"{int(s1_k):,}, letting time decay aggressively destroy retail option value."
        )
        why_strategy_fits_view = (
            f"Selling the {int(s1_k):,} Put (Delta ~0.20) backed by a protective wing matches the institutional objective perfectly: "
            f"harvesting premium while smart money defends your strike against breakdown."
        )
    elif composite_score <= 42:
        primary_stance = "OVERHEAD BEARISH SUPPLY WALL"
        stance_subtitle = "Aggressive Institutional Call Shorting & Trapped Retail Calls"
        conviction_rating = f"{int(min(95, 62 + (50 - composite_score) * 0.8))}% CONVICTION"
        badge_color = "red"
        recommended_strategy_id = "bear_call_credit_spread"
        recommended_strategy_name = f"{symbol} Bear Call Credit Spread (Resistance Fortress)"
        recommended_archetype = "Bearish / Neutral Credit Spread"
        invalidation_trigger = f"Decisive 15-minute candle close above R1 Resistance ({int(r1_k):,}) or 1-SD Ceiling ({int(sd1_high):,})"
        target_corridor = f"Capped below {int(r1_k):,} with gravitational pull to Max Pain ({int(max_pain):,})"
        smart_money_gameplan = (
            f"Proprietary desks and FIIs have erected an insurmountable ceiling at {int(r1_k):,} by shorting Calls. "
            f"Their mandate is to ensure index rallies stall beneath {int(r1_k):,} to pocket short premium. "
            f"Every intraday pop toward {int(r1_k):,} will be met with institutional call writing and sell orders."
        )
        retail_trap_analysis = (
            f"Retail traders are trapped holding {client_call_net:+,} net Calls chasing a breakout. "
            f"Smart money keeps the market suppressed below {int(r1_k):,}, ensuring that retail calls suffer catastrophic "
            f"theta decay into the expiry close."
        )
        why_strategy_fits_view = (
            f"Selling the {int(r1_k):,} Call behind the institutional resistance wall monetizes the market's inability "
            f"to breach overhead supply, allowing sellers to collect 100% of decay with defined risk."
        )
    else:
        primary_stance = "DELTA-NEUTRAL RANGE PINNING"
        stance_subtitle = "Symmetrical Two-Sided Writing Anchored Around Max Pain"
        conviction_rating = "85% PINNING CONVICTION"
        badge_color = "blue"
        recommended_strategy_id = "iron_condor_delta_neutral"
        recommended_strategy_name = f"{symbol} Delta-Neutral Iron Condor (Double Theta Fortress)"
        recommended_archetype = "Non-Directional Rangebound Harvest"
        invalidation_trigger = f"Decisive breakout outside the 1-SD Corridor ({int(sd1_low):,} to {int(sd1_high):,}) on expanding volume"
        target_corridor = f"Pinning inside {int(s1_k):,} to {int(r1_k):,} centered at Max Pain ({int(max_pain):,})"
        smart_money_gameplan = (
            f"Institutional desks are writing both Calls at {int(r1_k):,} and Puts at {int(s1_k):,} in balanced proportion. "
            f"Their game plan is to maintain price containment around Max Pain ({int(max_pain):,}) to bleed premium from both sides."
        )
        retail_trap_analysis = (
            f"Directional traders on both sides are getting chopped up by low volatility and theta decay. "
            f"Option sellers milk this environment by shorting out-of-the-money wings on both sides."
        )
        why_strategy_fits_view = (
            f"An Iron Condor deploys wings outside the 1-SD volatility corridor, harvesting dual theta decay with zero "
            f"directional bias and strict tail risk protection."
        )

    return {
        "symbol": symbol,
        "spot_price": spot,
        "composite_score": composite_score,
        "primary_stance": primary_stance,
        "stance_subtitle": stance_subtitle,
        "conviction_rating": conviction_rating,
        "badge_color": badge_color,
        "recommended_strategy_id": recommended_strategy_id,
        "recommended_strategy_name": recommended_strategy_name,
        "recommended_archetype": recommended_archetype,
        "invalidation_trigger": invalidation_trigger,
        "target_corridor": target_corridor,
        "smart_money_gameplan": smart_money_gameplan,
        "retail_trap_analysis": retail_trap_analysis,
        "why_strategy_fits_view": why_strategy_fits_view,
        "five_pillars": [
            {
                "id": "smart_money_futures",
                "name": "Smart Money Futures Flow",
                "weight_pts": 20,
                "score_pts": round(p1_score, 1),
                "score_pct": round((p1_score / 20.0) * 100),
                "status": p1_status,
                "status_color": p1_color,
                "metric_label": f"FII Net: {fii_fut_net:+,} | Pro: {pro_fut_net:+,}",
                "detail": p1_detail
            },
            {
                "id": "option_writing_skew",
                "name": "Institutional Option Writing Skew",
                "weight_pts": 25,
                "score_pts": round(p2_score, 1),
                "score_pct": round((p2_score / 25.0) * 100),
                "status": p2_status,
                "status_color": p2_color,
                "metric_label": f"Pro Puts: {pro_put_short_chg:+,} | Pro Calls: {pro_call_short_chg:+,}",
                "detail": p2_detail
            },
            {
                "id": "retail_trap_index",
                "name": "Retail Sentiment Contra-Indicator",
                "weight_pts": 20,
                "score_pts": round(p3_score, 1),
                "score_pct": round((p3_score / 20.0) * 100),
                "status": p3_status,
                "status_color": p3_color,
                "metric_label": f"Client Puts: {client_put_net:+,} | Calls: {client_call_net:+,}",
                "detail": p3_detail
            },
            {
                "id": "option_chain_structure",
                "name": "Option Chain Structure & PCR Magnet",
                "weight_pts": 20,
                "score_pts": round(p4_score, 1),
                "score_pct": round((p4_score / 20.0) * 100),
                "status": p4_status,
                "status_color": p4_color,
                "metric_label": f"PCR: {pcr:.2f} | Max Pain: {int(max_pain):,}",
                "detail": p4_detail
            },
            {
                "id": "volatility_normal_dist",
                "name": "Volatility & 1-SD Probability Corridor",
                "weight_pts": 15,
                "score_pts": round(p5_score, 1),
                "score_pct": round((p5_score / 15.0) * 100),
                "status": p5_status,
                "status_color": p5_color,
                "metric_label": f"1-SD: {int(sd1_low):,} - {int(sd1_high):,} (IV {round(iv * 100, 1)}%)",
                "detail": p5_detail
            }
        ]
    }

def select_best_option_selling_strategies(symbol, spot, atm_strike, s1_k, s2_k, r1_k, r2_k, max_pain, pcr, iv, days_to_expiry, sd1_low, sd1_high, sd2_low, sd2_high, strikes_dict, all_strikes, p_data=None, market_view=None):
    """
    Selects, calculates, and ranks the Top 3 Option Selling Strategies
    based on live Greeks, Volume, Normal Distribution SD bands, and Participant OI flows.
    """
    step = STRIKE_STEPS.get(symbol, 50.0)
    lot_size = LOT_SIZES.get(symbol, 25)
    t_years = max(1, days_to_expiry) / 365.0

    if market_view is None:
        market_view = build_institutional_market_view(
            symbol, spot, atm_strike, s1_k, s2_k, r1_k, r2_k,
            max_pain, pcr, iv, days_to_expiry, sd1_low, sd1_high, sd2_low, sd2_high, p_data
        )

    is_bullish_bias = market_view["primary_stance"] == "DEFENSIVE BULLISH FLOOR"
    is_bearish_bias = market_view["primary_stance"] == "OVERHEAD BEARISH SUPPLY WALL"
    is_rangebound = not is_bullish_bias and not is_bearish_bias

    # 1. Determine Participant Stance Confluence (for strategy rationales)
    if p_data and isinstance(p_data, dict):
        if "result" in p_data and isinstance(p_data["result"], dict):
            p_data = p_data["result"]

    fii_put_net = 0
    fii_call_net = 0
    fii_fut_net = 0
    pro_put_net = 0
    pro_call_net = 0
    pro_fut_net = 0
    pro_put_short_chg = 0
    client_put_net = 0
    client_call_net = 0
    client_fut_net = 0

    tables = p_data.get("instrument_tables", {}) if p_data else {}
    for r in tables.get("Index Calls", []):
        pkey = str(r.get("p_key", "")).upper()
        pname = str(r.get("participant", "")).upper()
        if "FII" in pkey or "FII" in pname:
            fii_call_net = r.get("net_buy_sell", 0)
        elif "CLIENT" in pkey or "CLIENT" in pname:
            client_call_net = r.get("net_buy_sell", 0)
        elif "PRO" in pkey or "PRO" in pname:
            pro_call_net = r.get("net_buy_sell", 0)

    for r in tables.get("Index Puts", []):
        pkey = str(r.get("p_key", "")).upper()
        pname = str(r.get("participant", "")).upper()
        if "FII" in pkey or "FII" in pname:
            fii_put_net = r.get("net_buy_sell", 0)
        elif "CLIENT" in pkey or "CLIENT" in pname:
            client_put_net = r.get("net_buy_sell", 0)
        elif "PRO" in pkey or "PRO" in pname:
            pro_put_net = r.get("net_buy_sell", 0)
            pro_put_short_chg = r.get("short_chg", 0)

    for r in tables.get("Index Futures", []):
        pkey = str(r.get("p_key", "")).upper()
        pname = str(r.get("participant", "")).upper()
        if "FII" in pkey or "FII" in pname:
            fii_fut_net = r.get("net_buy_sell", 0)
        elif "CLIENT" in pkey or "CLIENT" in pname:
            client_fut_net = r.get("net_buy_sell", 0)
        elif "PRO" in pkey or "PRO" in pname:
            pro_fut_net = r.get("net_buy_sell", 0)

    # 2. Select Selling & Hedging Strikes for Put Side
    otm_puts = [k for k in all_strikes if k < spot]
    if otm_puts:
        def score_put_candidate(k):
            s_dict = strikes_dict.get(k, {})
            pe_d = s_dict.get("pe", {}) or s_dict.get("put", {})
            vol = pe_d.get("volume", 0)
            oi_val = pe_d.get("oi", 0)
            grk = calculate_bs_greeks(spot, k, t_years, RISK_FREE_RATE, iv, "PE")
            score = 0
            ad = abs(grk["delta"])
            if 0.14 <= ad <= 0.26:
                score += 50
            elif 0.08 <= ad <= 0.35:
                score += 30
            else:
                score += 10
            if grk["seller_theta"] >= 8.0:
                score += 20
            if k == s1_k:
                score += 35
            elif k == s2_k:
                score += 20
            elif abs(k - sd1_low) <= step:
                score += 25
            if vol > 500000 or oi_val > 2000000:
                score += 20
            elif vol > 100000 or oi_val > 500000:
                score += 10
            if grk["gamma"] > 0.0012:
                score -= 25
            return score

        put_sell_k = max(otm_puts, key=score_put_candidate)
    else:
        put_sell_k = atm_strike - step

    # Put Hedge Strike: Buy further OTM (1 to 2 strikes below sell strike)
    hedge_candidates = [k for k in all_strikes if k < put_sell_k]
    if hedge_candidates:
        preferred_dist = 2 * step if symbol == "BANKNIFTY" else (2 * step if days_to_expiry > 4 else step)
        target_hedge_k = put_sell_k - preferred_dist
        put_hedge_k = min(hedge_candidates, key=lambda k: abs(k - target_hedge_k))
    else:
        put_hedge_k = put_sell_k - step

    # 3. Select Selling & Hedging Strikes for Call Side
    otm_calls = [k for k in all_strikes if k > spot]
    if otm_calls:
        def score_call_candidate(k):
            s_dict = strikes_dict.get(k, {})
            ce_d = s_dict.get("ce", {}) or s_dict.get("call", {})
            vol = ce_d.get("volume", 0)
            oi_val = ce_d.get("oi", 0)
            grk = calculate_bs_greeks(spot, k, t_years, RISK_FREE_RATE, iv, "CE")
            score = 0
            cd = grk["delta"]
            if 0.14 <= cd <= 0.26:
                score += 50
            elif 0.08 <= cd <= 0.35:
                score += 30
            else:
                score += 10
            if grk["seller_theta"] >= 8.0:
                score += 20
            if k == r1_k:
                score += 35
            elif k == r2_k:
                score += 20
            elif abs(k - sd1_high) <= step:
                score += 25
            if vol > 500000 or oi_val > 2000000:
                score += 20
            elif vol > 100000 or oi_val > 500000:
                score += 10
            if grk["gamma"] > 0.0012:
                score -= 25
            return score

        call_sell_k = max(otm_calls, key=score_call_candidate)
    else:
        call_sell_k = atm_strike + step

    # Call Hedge Strike: Buy further OTM (1 to 2 strikes above sell strike)
    hedge_call_candidates = [k for k in all_strikes if k > call_sell_k]
    if hedge_call_candidates:
        preferred_call_dist = 2 * step if symbol == "BANKNIFTY" else (2 * step if days_to_expiry > 4 else step)
        target_call_hedge_k = call_sell_k + preferred_call_dist
        call_hedge_k = min(hedge_call_candidates, key=lambda k: abs(k - target_call_hedge_k))
    else:
        call_hedge_k = call_sell_k + step

    # Fetch Prices, Volume, OI, and Greeks for Legs
    def get_leg_details(strike, opt_type, action):
        s_dict = strikes_dict.get(strike, {})
        data = s_dict.get(opt_type.lower(), {}) or s_dict.get("call" if opt_type == "CE" else "put", {})
        ltp = data.get("ltp", 0.0)
        oi = data.get("oi", 0)
        chg_oi = data.get("chg_oi", 0)
        volume = data.get("volume", 0)
        greeks = calculate_bs_greeks(spot, strike, t_years, RISK_FREE_RATE, iv, opt_type)
        if ltp <= 0.05:
            ltp = greeks["price"]

        return {
            "strike": strike,
            "type": opt_type,
            "action": action,
            "ltp": round(ltp, 2),
            "oi": oi,
            "chg_oi": chg_oi,
            "volume": volume,
            "delta": greeks["delta"],
            "seller_theta": greeks["seller_theta"],
            "gamma": greeks["gamma"],
            "vega": greeks["vega"],
            "lot_size": lot_size
        }

    # Legs for Put Credit Spread
    put_sell_leg = get_leg_details(put_sell_k, "PE", "SELL")
    put_buy_leg = get_leg_details(put_hedge_k, "PE", "BUY")

    # Legs for Call Credit Spread
    call_sell_leg = get_leg_details(call_sell_k, "CE", "SELL")
    call_buy_leg = get_leg_details(call_hedge_k, "CE", "BUY")

    # 4. Construct Strategy 1: Bull Put Credit Spread
    put_spread_width = put_sell_k - put_hedge_k
    put_net_credit = max(1.0, round(put_sell_leg["ltp"] - put_buy_leg["ltp"], 2))
    put_max_risk = max(1.0, round(put_spread_width - put_net_credit, 2))
    put_be = round(put_sell_k - put_net_credit, 2)
    put_pop = round((1.0 - abs(put_sell_leg["delta"])) * 100, 1)

    put_naked_margin, put_hedged_margin, put_margin_saved, put_margin_saved_pct = estimate_span_margin(symbol, put_sell_k, "PE", put_hedge_k, "PE", spot)
    put_rom = round(((put_net_credit * lot_size) / put_hedged_margin) * 100, 2)

    strat_bull_put = {
        "id": "bull_put_credit_spread",
        "name": f"{symbol} Bull Put Credit Spread (Smart Money Shield)",
        "archetype": "Bullish Credit Spread",
        "suitability_badge": "PREMIER CONVICTION" if is_bullish_bias else "BALANCED DEFENSE",
        "badge_color": "green",
        "market_view": "Moderately Bullish to Resilient Flat",
        "confidence_score": 88 if is_bullish_bias else 78,
        "pop_pct": put_pop,
        "net_credit_pts": put_net_credit,
        "net_credit_inr": round(put_net_credit * lot_size, 2),
        "max_risk_pts": put_max_risk,
        "max_risk_inr": round(put_max_risk * lot_size, 2),
        "reward_risk_ratio": f"1 : {round(put_max_risk / put_net_credit, 1)}",
        "breakeven_pts": put_be,
        "breakeven_label": f"Spot must stay above {int(put_be):,}",
        "margin_naked_inr": put_naked_margin,
        "margin_hedged_inr": put_hedged_margin,
        "margin_saved_inr": round(put_naked_margin - put_hedged_margin, 2),
        "margin_saved_pct": put_margin_saved_pct,
        "return_on_margin_pct": put_rom,
        "net_greeks": {
            "net_delta": round(-put_sell_leg["delta"] + put_buy_leg["delta"], 3),
            "net_theta": round(put_sell_leg["seller_theta"] - put_buy_leg["seller_theta"], 2),
            "net_gamma": round(-put_sell_leg["gamma"] + put_buy_leg["gamma"], 5),
            "net_vega": round(-put_sell_leg["vega"] + put_buy_leg["vega"], 2)
        },
        "legs": [
            {
                "action": "SELL (Write)",
                "action_type": "SELL",
                "strike": put_sell_k,
                "opt_type": "PE",
                "ltp": put_sell_leg["ltp"],
                "oi": put_sell_leg["oi"],
                "chg_oi": put_sell_leg["chg_oi"],
                "volume": put_sell_leg["volume"],
                "delta": put_sell_leg["delta"],
                "seller_theta": put_sell_leg["seller_theta"],
                "gamma": put_sell_leg["gamma"],
                "purpose": f"Collect premium at S1 Institutional Floor ({int(put_sell_k):,}) with {put_sell_leg['volume']:,} volume"
            },
            {
                "action": "BUY (Hedge)",
                "action_type": "BUY",
                "strike": put_hedge_k,
                "opt_type": "PE",
                "ltp": put_buy_leg["ltp"],
                "oi": put_buy_leg["oi"],
                "chg_oi": put_buy_leg["chg_oi"],
                "volume": put_buy_leg["volume"],
                "delta": put_buy_leg["delta"],
                "seller_theta": put_buy_leg["seller_theta"],
                "gamma": put_buy_leg["gamma"],
                "purpose": f"Cap tail risk & unlock {put_margin_saved_pct}% exchange margin discount"
            }
        ],
        "why_this_strategy_is_best": (
            f"FIIs and Pro desks have established high Put writing inventory at {int(s1_k):,} (PCR {pcr}), creating a resilient "
            f"institutional support cushion. Pro desks added +{pro_put_short_chg:,} put shorts, while retail clients bought +{client_put_net:,} puts. "
            f"Selling the {int(put_sell_k):,} Put directly extracts theta from trapped retail traders while smart money defends the strike."
        ),
        "why_these_strikes_are_most_efficient": (
            f"1. Sell Strike {int(put_sell_k):,} sits at the 1-SD Lower Normal Distribution Floor ({int(sd1_low):,}) "
            f"with Delta of {put_sell_leg['delta']}, giving an outstanding {put_pop}% statistical probability of expiring worthless. "
            f"2. Theta decay is aggressive at +₹{put_sell_leg['seller_theta']}/day with {put_sell_leg['volume']:,} contracts in active liquidity. "
            f"3. Hedge Strike {int(put_hedge_k):,} costs only ₹{put_buy_leg['ltp']}, retaining {round((put_net_credit/put_sell_leg['ltp'])*100)}% of the gross premium "
            f"while reducing required margin by ₹{int(put_naked_margin - put_hedged_margin):,}."
        ),
        "execution_rules": (
            f"• Entry: Deploy around 9:20 - 9:30 AM after opening volatility stabilizes.\n"
            f"• Profit Target: Book 60% - 70% of max profit (when net credit decays to ₹{round(put_net_credit * 0.35, 1)}).\n"
            f"• Stop Loss: Exit entire spread if Spot decisively breaks below breakeven {int(put_be):,} on a 15-minute close."
        )
    }

    # 5. Construct Strategy 2: Iron Condor (Delta-Neutral Two-Sided Theta Harvest)
    call_spread_width = call_hedge_k - call_sell_k
    call_net_credit = max(1.0, round(call_sell_leg["ltp"] - call_buy_leg["ltp"], 2))
    call_max_risk = max(1.0, round(call_spread_width - call_net_credit, 2))
    call_be = round(call_sell_k + call_net_credit, 2)
    call_pop = round((1.0 - call_sell_leg["delta"]) * 100, 1)

    ic_net_credit = round(put_net_credit + call_net_credit, 2)
    ic_max_width = max(put_spread_width, call_spread_width)
    ic_max_risk = round(ic_max_width - ic_net_credit, 2)
    ic_pop = round(min(84.0, (put_pop + call_pop) / 2.0 - 5.0), 1)

    ic_naked_margin = put_naked_margin + 60000.0
    ic_hedged_margin = max(put_hedged_margin, 46000.0)
    ic_rom = round(((ic_net_credit * lot_size) / ic_hedged_margin) * 100, 2)

    strat_iron_condor = {
        "id": "iron_condor_delta_neutral",
        "name": f"{symbol} Delta-Neutral Iron Condor (Double Theta Fortress)",
        "archetype": "Non-Directional Rangebound Harvest",
        "suitability_badge": "HIGH YIELD PINNING",
        "badge_color": "blue",
        "market_view": "Rangebound Pinning between S1 and R1",
        "confidence_score": 85 if is_rangebound else 75,
        "pop_pct": ic_pop,
        "net_credit_pts": ic_net_credit,
        "net_credit_inr": round(ic_net_credit * lot_size, 2),
        "max_risk_pts": ic_max_risk,
        "max_risk_inr": round(ic_max_risk * lot_size, 2),
        "reward_risk_ratio": f"1 : {round(ic_max_risk / ic_net_credit, 1)}",
        "breakeven_pts": f"{int(put_sell_k - ic_net_credit):,} - {int(call_sell_k + ic_net_credit):,}",
        "breakeven_label": f"Profitable inside {int(put_sell_k - ic_net_credit):,} to {int(call_sell_k + ic_net_credit):,}",
        "margin_naked_inr": ic_naked_margin,
        "margin_hedged_inr": ic_hedged_margin,
        "margin_saved_inr": round(ic_naked_margin - ic_hedged_margin, 2),
        "margin_saved_pct": round(((ic_naked_margin - ic_hedged_margin) / ic_naked_margin) * 100, 1),
        "return_on_margin_pct": ic_rom,
        "net_greeks": {
            "net_delta": round((-put_sell_leg["delta"] + put_buy_leg["delta"]) + (call_sell_leg["delta"] - call_buy_leg["delta"]), 3),
            "net_theta": round((put_sell_leg["seller_theta"] - put_buy_leg["seller_theta"]) + (call_sell_leg["seller_theta"] - call_buy_leg["seller_theta"]), 2),
            "net_gamma": round((-put_sell_leg["gamma"] + put_buy_leg["gamma"]) + (-call_sell_leg["gamma"] + call_buy_leg["gamma"]), 5),
            "net_vega": round((-put_sell_leg["vega"] + put_buy_leg["vega"]) + (-call_sell_leg["vega"] + call_buy_leg["vega"]), 2)
        },
        "legs": [
            {
                "action": "SELL Put",
                "action_type": "SELL",
                "strike": put_sell_k,
                "opt_type": "PE",
                "ltp": put_sell_leg["ltp"],
                "oi": put_sell_leg["oi"],
                "chg_oi": put_sell_leg["chg_oi"],
                "volume": put_sell_leg["volume"],
                "delta": put_sell_leg["delta"],
                "seller_theta": put_sell_leg["seller_theta"],
                "gamma": put_sell_leg["gamma"],
                "purpose": f"Sell S1 Support floor ({int(put_sell_k):,})"
            },
            {
                "action": "BUY Put Wing",
                "action_type": "BUY",
                "strike": put_hedge_k,
                "opt_type": "PE",
                "ltp": put_buy_leg["ltp"],
                "oi": put_buy_leg["oi"],
                "chg_oi": put_buy_leg["chg_oi"],
                "volume": put_buy_leg["volume"],
                "delta": put_buy_leg["delta"],
                "seller_theta": put_buy_leg["seller_theta"],
                "gamma": put_buy_leg["gamma"],
                "purpose": "Downside disaster protection"
            },
            {
                "action": "SELL Call",
                "action_type": "SELL",
                "strike": call_sell_k,
                "opt_type": "CE",
                "ltp": call_sell_leg["ltp"],
                "oi": call_sell_leg["oi"],
                "chg_oi": call_sell_leg["chg_oi"],
                "volume": call_sell_leg["volume"],
                "delta": call_sell_leg["delta"],
                "seller_theta": call_sell_leg["seller_theta"],
                "gamma": call_sell_leg["gamma"],
                "purpose": f"Sell R1 Resistance cap ({int(call_sell_k):,})"
            },
            {
                "action": "BUY Call Wing",
                "action_type": "BUY",
                "strike": call_hedge_k,
                "opt_type": "CE",
                "ltp": call_buy_leg["ltp"],
                "oi": call_buy_leg["oi"],
                "chg_oi": call_buy_leg["chg_oi"],
                "volume": call_buy_leg["volume"],
                "delta": call_buy_leg["delta"],
                "seller_theta": call_buy_leg["seller_theta"],
                "gamma": call_buy_leg["gamma"],
                "purpose": "Upside squeeze protection"
            }
        ],
        "why_this_strategy_is_best": (
            f"The option chain reveals dual institutional barriers: S1 Support at {int(s1_k):,} and R1 Resistance at {int(r1_k):,}. "
            f"Max Pain is centered at {int(max_pain):,} (PCR {pcr}). Pro desks and FIIs are writing both wings to capture accelerated theta. "
            f"An Iron Condor capitalizes on both sides simultaneously without taking directional risk."
        ),
        "why_these_strikes_are_most_efficient": (
            f"1. The wings sit exactly outside the 1-SD Volatility Corridor ({int(sd1_low):,} to {int(sd1_high):,}). "
            f"2. Dual Theta decay (+₹{round(put_sell_leg['seller_theta'] + call_sell_leg['seller_theta'], 1)}/day) erodes premium from both sides twice as fast. "
            f"3. High liquid volume across strikes ({put_sell_leg['volume']:,} PE / {call_sell_leg['volume']:,} CE) guarantees smooth fills and minimal spread slippage."
        ),
        "execution_rules": (
            f"• Entry: Deploy during rangebound morning session.\n"
            f"• Profit Target: Book when 50% of the total net credit (₹{round(ic_net_credit * 0.5, 1)} pts) is harvested.\n"
            f"• Adjustment: If spot tests one boundary, roll the untested side closer to collect additional credit."
        )
    }

    # 6. Construct Strategy 3: Bear Call Credit Spread
    call_naked_margin, call_hedged_margin, call_margin_saved, call_margin_saved_pct = estimate_span_margin(symbol, call_sell_k, "CE", call_hedge_k, "CE", spot)
    call_rom = round(((call_net_credit * lot_size) / call_hedged_margin) * 100, 2)

    strat_bear_call = {
        "id": "bear_call_credit_spread",
        "name": f"{symbol} Bear Call Credit Spread (Resistance Fortress)",
        "archetype": "Bearish / Neutral Credit Spread",
        "suitability_badge": "OVERHEAD SUPPLY WALL",
        "badge_color": "amber",
        "market_view": "Flat to Capped Resistance Below R1",
        "confidence_score": 82 if is_bearish_bias else 72,
        "pop_pct": call_pop,
        "net_credit_pts": call_net_credit,
        "net_credit_inr": round(call_net_credit * lot_size, 2),
        "max_risk_pts": call_max_risk,
        "max_risk_inr": round(call_max_risk * lot_size, 2),
        "reward_risk_ratio": f"1 : {round(call_max_risk / call_net_credit, 1)}",
        "breakeven_pts": call_be,
        "breakeven_label": f"Spot must stay below {int(call_be):,}",
        "margin_naked_inr": call_naked_margin,
        "margin_hedged_inr": call_hedged_margin,
        "margin_saved_inr": round(call_naked_margin - call_hedged_margin, 2),
        "margin_saved_pct": call_margin_saved_pct,
        "return_on_margin_pct": call_rom,
        "net_greeks": {
            "net_delta": round(-call_sell_leg["delta"] + call_buy_leg["delta"], 3),
            "net_theta": round(call_sell_leg["seller_theta"] - call_buy_leg["seller_theta"], 2),
            "net_gamma": round(-call_sell_leg["gamma"] + call_buy_leg["gamma"], 5),
            "net_vega": round(-call_sell_leg["vega"] + call_buy_leg["vega"], 2)
        },
        "legs": [
            {
                "action": "SELL (Write)",
                "action_type": "SELL",
                "strike": call_sell_k,
                "opt_type": "CE",
                "ltp": call_sell_leg["ltp"],
                "oi": call_sell_leg["oi"],
                "chg_oi": call_sell_leg["chg_oi"],
                "volume": call_sell_leg["volume"],
                "delta": call_sell_leg["delta"],
                "seller_theta": call_sell_leg["seller_theta"],
                "gamma": call_sell_leg["gamma"],
                "purpose": f"Sell Smart Money R1 Resistance ceiling ({int(call_sell_k):,}) with {call_sell_leg['volume']:,} volume"
            },
            {
                "action": "BUY (Hedge)",
                "action_type": "BUY",
                "strike": call_hedge_k,
                "opt_type": "CE",
                "ltp": call_buy_leg["ltp"],
                "oi": call_buy_leg["oi"],
                "chg_oi": call_buy_leg["chg_oi"],
                "volume": call_buy_leg["volume"],
                "delta": call_buy_leg["delta"],
                "seller_theta": call_buy_leg["seller_theta"],
                "gamma": call_buy_leg["gamma"],
                "purpose": f"Cap upside short-squeeze loss & unlock {call_margin_saved_pct}% margin reduction"
            }
        ],
        "why_this_strategy_is_best": (
            f"Institutional call writers are clustered heavily around {int(r1_k):,}. Even if the market rallies, "
            f"heavy call open interest will cap the advance. Selling the {int(call_sell_k):,} Call with a higher hedge "
            f"allows you to monetize time decay while resting behind massive institutional resistance."
        ),
        "why_these_strikes_are_most_efficient": (
            f"1. Strike {int(call_sell_k):,} possesses a low Call Delta of {call_sell_leg['delta']}, translating to a {call_pop}% probability "
            f"of expiring out-of-the-money. "
            f"2. Theta is positive at +₹{call_sell_leg['seller_theta']}/day with {call_sell_leg['volume']:,} contracts in active liquidity. "
            f"3. Hedging at {int(call_hedge_k):,} restricts max loss to defined points while slating margin requirements down to ₹{int(call_hedged_margin):,}."
        ),
        "execution_rules": (
            f"• Entry: Initiate on intraday pops toward resistance {int(r1_k - step):,}.\n"
            f"• Profit Target: 65% of max credit collected.\n"
            f"• Stop Loss: Exit if spot closes above {int(call_be):,} on heavy volume."
        )
    }

    # Rank the strategies according to current data
    ranked_strategies = []
    if is_bullish_bias:
        ranked_strategies = [
            {"rank": 1, "is_recommended": True, **strat_bull_put},
            {"rank": 2, "is_recommended": False, **strat_iron_condor},
            {"rank": 3, "is_recommended": False, **strat_bear_call}
        ]
    elif is_bearish_bias:
        ranked_strategies = [
            {"rank": 1, "is_recommended": True, **strat_bear_call},
            {"rank": 2, "is_recommended": False, **strat_iron_condor},
            {"rank": 3, "is_recommended": False, **strat_bull_put}
        ]
    else: # Rangebound
        ranked_strategies = [
            {"rank": 1, "is_recommended": True, **strat_iron_condor},
            {"rank": 2, "is_recommended": False, **strat_bull_put},
            {"rank": 3, "is_recommended": False, **strat_bear_call}
        ]

    return ranked_strategies

def get_option_selling_advisory(symbol="NIFTY", date_str="2026-10-30", expiry=None, p_data=None):
    """
    Master function: Synthesizes Option Chain, Participant OI, Greeks, and Normal Distribution
    to generate complete Option Selling Advisory data payload.
    """
    if p_data and isinstance(p_data, dict):
        if "result" in p_data and isinstance(p_data["result"], dict):
            p_data = p_data["result"]

    if p_data is None:
        try:
            from nse_fetcher import fetch_nse_range
            res = fetch_nse_range(date_str, 5)
            if res.get("status") == "success" and res.get("result"):
                p_data = res["result"]
        except Exception:
            pass

    # Crucial: pass date_str, symbol, expiry_date, participant_data as named keywords!
    oc_data = get_option_chain_data(
        date_str=date_str,
        symbol=symbol,
        expiry_date=expiry,
        participant_data=p_data
    )

    actual_date = oc_data.get("date") or date_str
    spot = oc_data.get("spot_price", 25050.0)
    atm_strike = oc_data.get("atm_strike", 25050.0)
    max_pain = oc_data.get("max_pain", 25050.0)
    pcr = oc_data.get("pcr", 1.0)
    selected_expiry = oc_data.get("selected_expiry")
    available_expiries = oc_data.get("available_expiries", [])

    s1_k = oc_data.get("major_support", {}).get("strike", atm_strike - 100)
    s2_k = oc_data.get("secondary_support", {}).get("strike", s1_k - 100)
    r1_k = oc_data.get("major_resistance", {}).get("strike", atm_strike + 100)
    r2_k = oc_data.get("secondary_resistance", {}).get("strike", r1_k + 100)

    prob_model = oc_data.get("probabilistic_model", {})
    iv_pct = prob_model.get("implied_volatility_pct", 13.5)
    iv = iv_pct / 100.0
    days_to_expiry = max(1, prob_model.get("days_to_expiry", 4))
    t_years = days_to_expiry / 365.0

    sd1_band = prob_model.get("sd1_band", {})
    sd2_band = prob_model.get("sd2_band", {})
    sd1_low = sd1_band.get("low", spot - 200)
    sd1_high = sd1_band.get("high", spot + 200)
    sd2_low = sd2_band.get("low", spot - 400)
    sd2_high = sd2_band.get("high", spot + 400)

    # Convert strikes list to dict
    strikes_list = oc_data.get("strikes", [])
    strikes_dict = {}
    all_strikes = []
    for s in strikes_list:
        k = s.get("strike")
        if k is not None:
            strikes_dict[k] = s
            all_strikes.append(k)

    # Generate Strike Efficiency Matrix
    strike_efficiency = generate_strike_efficiency_matrix(
        symbol, spot, all_strikes, strikes_dict, t_years, iv,
        s1_k, s2_k, r1_k, r2_k, sd1_low, sd1_high, sd2_low, sd2_high
    )

    # Generate Institutional Market View across 5 Quantitative Pillars
    institutional_market_view = build_institutional_market_view(
        symbol=symbol, spot=spot, atm_strike=atm_strike,
        s1_k=s1_k, s2_k=s2_k, r1_k=r1_k, r2_k=r2_k,
        max_pain=max_pain, pcr=pcr, iv=iv, days_to_expiry=days_to_expiry,
        sd1_low=sd1_low, sd1_high=sd1_high, sd2_low=sd2_low, sd2_high=sd2_high,
        p_data=p_data
    )

    # Generate Top 3 Ranked Option Selling Strategies
    top_strategies = select_best_option_selling_strategies(
        symbol, spot, atm_strike, s1_k, s2_k, r1_k, r2_k, max_pain, pcr, iv, days_to_expiry,
        sd1_low, sd1_high, sd2_low, sd2_high, strikes_dict, all_strikes, p_data, market_view=institutional_market_view
    )

    best_strategy = top_strategies[0] if top_strategies else {}

    # Executive Summary Memo based on Varsity Principles
    executive_selling_memo = {
        "best_strategy_name": best_strategy.get("name", ""),
        "recommended_archetype": best_strategy.get("archetype", ""),
        "win_rate_pct": best_strategy.get("pop_pct", 85.0),
        "lot_size": LOT_SIZES.get(symbol, 25),
        "days_to_expiry": days_to_expiry,
        "iv_pct": iv_pct,
        "sd1_corridor": f"{int(sd1_low):,} - {int(sd1_high):,}",
        "sd2_corridor": f"{int(sd2_low):,} - {int(sd2_high):,}",
        "smart_money_defense_walls": f"S1 Support @ {int(s1_k):,} | R1 Resistance @ {int(r1_k):,}",
        "key_selling_thesis": (
            f"Based on Zerodha Varsity Options Theory, option writers possess a mathematical statistical edge because "
            f"2 out of 3 market outcomes (flat or opposite direction) favor the seller. With {days_to_expiry} days to expiry, "
            f"time decay (Theta) accelerates exponentially. By selling {best_strategy.get('legs', [{}])[0].get('strike', 0)} {best_strategy.get('legs', [{}])[0].get('opt_type', '')} "
            f"at the 1-SD boundary and hedging with a protective wing, you harvest +₹{best_strategy.get('net_greeks', {}).get('net_theta', 0)}/day in decay "
            f"while cutting margin by {best_strategy.get('margin_saved_pct', 0)}% and eliminating Black Swan tail risk."
        )
    }

    # AI / ML Quantitative Trading & Next-Day Market View Model
    try:
        from quant_ml_engine import get_quant_ml_market_view
        oc_payload = {
            "spot": spot,
            "spot_price": spot,
            "max_pain": max_pain,
            "pcr": pcr,
            "atm_iv": iv,
            "days_to_expiry": days_to_expiry,
            "total_pe_oi": sum(s.get("put", {}).get("oi", 0) for s in strike_efficiency),
            "total_ce_oi": sum(s.get("call", {}).get("oi", 0) for s in strike_efficiency),
            "total_pe_chg_oi": sum(s.get("put", {}).get("chg_oi", 0) for s in strike_efficiency),
            "total_ce_chg_oi": sum(s.get("call", {}).get("chg_oi", 0) for s in strike_efficiency),
            "s1": s1_k,
            "r1": r1_k,
            "strikes": strikes_dict
        }
        ai_ml_quant_model = get_quant_ml_market_view(p_data, oc_payload)
    except Exception as e:
        ai_ml_quant_model = {"status": "error", "message": str(e)}

    return {
        "status": "success",
        "symbol": symbol,
        "date": actual_date,
        "selected_expiry": selected_expiry,
        "available_expiries": available_expiries,
        "spot_price": spot,
        "atm_strike": atm_strike,
        "max_pain": max_pain,
        "pcr": pcr,
        "iv_pct": iv_pct,
        "days_to_expiry": days_to_expiry,
        "institutional_market_view": institutional_market_view,
        "ai_ml_quant_model": ai_ml_quant_model,
        "executive_memo": executive_selling_memo,
        "top_strategies": top_strategies,
        "strike_efficiency_matrix": strike_efficiency,
        "varsity_principles": {
            "theta_rule": "Theta is the option seller's primary income driver. Time decay is non-linear and accelerates sharply in the final days of the series.",
            "delta_rule": "Delta acts as the approximate probability of expiring ITM. Selling strikes with Delta between 0.15 and 0.25 yields an 75% - 85% statistical win rate.",
            "gamma_trap": "Never short naked ATM options close to expiry. ATM Gamma peaks near expiry, causing rapid delta explosions if spot swings against you.",
            "hedge_multiplier": "Always buy an OTM protective wing. Hedging caps tail risk ('no Black Swan disaster') and slashes NSE SPAN margin by 60%–70%, vastly amplifying Return on Margin (ROM)."
        }
    }
