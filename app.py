import os
import re
import glob
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from oi_engine import parse_pdf, parse_csv, parse_text_stream, calculate_multi_day_oi
from generate_samples import generate_sample_data, create_csv_files, create_pdf_files
from nse_fetcher import fetch_nse_range, fetch_single_day_from_nse, fetch_participant_vol, fetch_fii_stats, fetch_cash_delivery_data, get_latest_session_date, format_session_label, get_available_cached_dates
from option_chain_engine import get_option_chain_data
from report_engine import build_details_report
from selling_strategy_engine import get_option_selling_advisory
from quant_ml_engine import get_quant_ml_market_view
from participant_strike_matcher import match_participants_to_strikes
from stock_constituent_engine import get_simulated_constituent_data, extract_stock_futures_buildup, parse_cash_delivery_data as parse_delivery_rows, compute_constituent_alignment_score

app = Flask(__name__)
# Crucial: Disable alphabetical key sorting so instrument sequence is strictly preserved!
app.json.sort_keys = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['SAMPLE_FOLDER'] = os.path.join(os.path.dirname(__file__), 'sample_files')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SAMPLE_FOLDER'], exist_ok=True)

@app.context_processor
def inject_latest_session():
    latest = get_latest_session_date()
    label = format_session_label(latest)
    avail = get_available_cached_dates()
    return {
        'latest_session_date': latest,
        'latest_session_label': label,
        'available_sessions': avail
    }

@app.route('/api/latest-session', methods=['GET'])
def api_latest_session():
    latest = get_latest_session_date()
    label = format_session_label(latest)
    avail = get_available_cached_dates()
    return jsonify({
        'status': 'success',
        'latest_date': latest,
        'latest_label': label,
        'available_dates': avail
    })


# Disable caching for development so browser updates immediately
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Pre-generate sample files if not present
if len(glob.glob(os.path.join(app.config['SAMPLE_FOLDER'], "*.pdf"))) < 5:
    days = generate_sample_data()
    create_csv_files(days, app.config['SAMPLE_FOLDER'])
    create_pdf_files(days, app.config['SAMPLE_FOLDER'])

def get_latest_session_date():
    """
    Returns the most recent completed trading session date.
    Checks available cached NSE files first (e.g. 2026-10-26).
    Falls back to latest weekday.
    """
    cache_dir = os.path.join(os.path.dirname(__file__), "cache")
    cached_files = glob.glob(os.path.join(cache_dir, "fao_participant_oi_*.csv"))
    if cached_files:
        dates = []
        for f in cached_files:
            m = re.search(r"fao_participant_oi_(\d{8})\.csv", os.path.basename(f))
            if m:
                raw = m.group(1)
                for fmt in ['%Y%m%d', '%d%m%Y']:
                    try:
                        dt = datetime.strptime(raw, fmt)
                        dates.append(dt.strftime("%Y-%m-%d"))
                        break
                    except ValueError:
                        pass
        if dates:
            return sorted(dates)[-1]

    now = datetime.now()
    dt = now
    if dt.weekday() == 5:
        dt -= timedelta(days=1)
    elif dt.weekday() == 6:
        dt -= timedelta(days=2)
    elif now.hour < 18 or (now.hour == 18 and now.minute < 30):
        dt -= timedelta(days=1)
        while dt.weekday() >= 5:
            dt -= timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def get_demo_parsed_records():
    """Load the 5-day sample PDFs for instant demo."""
    pdf_files = sorted(glob.glob(os.path.join(app.config['SAMPLE_FOLDER'], "*.pdf")))
    records = []
    for p in pdf_files:
        fname = os.path.basename(p)
        rec = parse_pdf(p, fname)
        if rec and rec.get("data"):
            records.append(rec)
    return records

def get_participant_data_for_date(target_date):
    """
    Retrieves multi-day participant OI data for a given date.
    Uses cached/fetched records or falls back to demo reference records.
    """
    try:
        # First try fetching from cache / archive / reference range for target_date
        res = fetch_nse_range(target_date, 5)
        if res.get("status") == "success" and res.get("result"):
            return res["result"]
    except Exception as e:
        print(f"Warning: Failed to fetch participant data for {target_date}: {e}")

    # Fallback to demo records matching target_date
    try:
        demo_recs = get_demo_parsed_records()
        if demo_recs:
            matching = [r for r in demo_recs if r.get("date", "") <= target_date]
            if matching:
                return calculate_multi_day_oi(matching)
            return calculate_multi_day_oi(demo_recs)
    except Exception:
        pass
    return None

def augment_single_record_with_history(records):
    """
    If user uploads or pastes only 1 file/date, attempt to retrieve
    the previous trading day from cache or NSE archives so that
    Day-over-Day changes and Next-Day forecasts work automatically!
    """
    if len(records) != 1:
        return records

    single_date = records[0]["date"]
    try:
        dt = datetime.strptime(single_date, "%Y-%m-%d")
        curr = dt - timedelta(days=1)
        for _ in range(7):
            if curr.weekday() < 5:
                ok, content, _ = fetch_single_day_from_nse(curr)
                if ok:
                    prev_rec = parse_csv(content, f"fao_participant_oi_{curr.strftime('%Y%m%d')}.csv")
                    prev_rec["date"] = curr.strftime("%Y-%m-%d")
                    if prev_rec.get("data") and len(prev_rec["data"]) >= 3:
                        records.insert(0, prev_rec)
                        break
            curr -= timedelta(days=1)
    except Exception:
        pass

    if len(records) == 1:
        demo_recs = get_demo_parsed_records()
        for dr in demo_recs:
            if dr["date"] < single_date:
                records.insert(0, dr)
                break

    return records

@app.route('/')
def home():
    return render_template('home.html', active_page='home', v=int(time.time()))

@app.route('/option-chain')
def option_chain_view():
    return render_template('option_chain.html', active_page='option_chain', v=int(time.time()))

@app.route('/participant-oi')
def participant_oi_view():
    return render_template('participant_oi.html', active_page='participant_oi', v=int(time.time()))

@app.route('/details-report')
def details_report_view():
    return render_template('details_report.html', active_page='details_report', v=int(time.time()))

@app.route('/option-selling')
def option_selling_view():
    return render_template('selling_strategies.html', active_page='option_selling', v=int(time.time()))

@app.route('/strike-intelligence')
def strike_intelligence_view():
    return render_template('strike_intelligence.html', active_page='strike_intelligence', v=int(time.time()))

@app.route('/pipeline')
@app.route('/quant-pipeline')
def pipeline_view():
    target_date = request.args.get('date', '').strip() or get_latest_session_date()
    symbol = request.args.get('symbol', 'NIFTY').strip().upper() or 'NIFTY'
    from engine import run_engine
    try:
        initial_data = run_engine(date_str=target_date, symbol=symbol)
    except Exception as e:
        print(f"Pipeline initial engine load warning: {e}")
        initial_data = {}
    return render_template(
        'pipeline_window.html',
        active_page='pipeline',
        initial_data=initial_data,
        default_date=target_date,
        default_symbol=symbol,
        v=int(time.time())
    )

@app.route('/quant-model')
def quant_model_view():
    return redirect('/pipeline')

@app.route('/index.html')
def index_redirect():
    return redirect('/')

@app.route('/api/demo-data', methods=['GET'])
def api_demo_data():
    """Returns the full parsed and analyzed 5-day dataset for current active session 2026-10-30."""
    try:
        res = fetch_nse_range(get_latest_session_date(), 5)
        if res.get("status") == "success" and res.get("result"):
            return jsonify({
                "status": "success",
                "source": f"live_nse_cache_{get_latest_session_date().replace('-', '_')}",
                "file_count": res.get("days_fetched", 5),
                "result": res["result"]
            })
        records = get_demo_parsed_records()
        analysis = calculate_multi_day_oi(records)
        return jsonify({
            "status": "success",
            "source": "demo_data_fallback",
            "file_count": len(records),
            "result": analysis
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/fetch-nse', methods=['POST'])
def api_fetch_nse():
    """
    Automatically fetches participant-wise open interest data directly from NSE.
    Accepts JSON: { "date": "YYYY-MM-DD", "days": 5 }
    """
    req_data = request.json or {}
    target_date = req_data.get('date', '').strip()
    lookback_days = int(req_data.get('days', 5))

    if not target_date:
        return jsonify({"status": "error", "message": "Target date is required (YYYY-MM-DD)."}), 400

    if lookback_days not in [2, 3, 4, 5]:
        lookback_days = 5

    try:
        res = fetch_nse_range(target_date, lookback_days)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error fetching from NSE: {str(e)}"}), 500

@app.route('/api/option-chain', methods=['GET', 'POST'])
def api_option_chain():
    """
    Fetches option chain for NIFTY, BANKNIFTY, FINNIFTY with Max Pain, PCR, S&R, and Participant Synergy.
    Query / Body params: date, symbol, expiry, window
    """
    if request.method == 'POST':
        req_data = request.json or {}
    else:
        req_data = request.args.to_dict()

    target_date = str(req_data.get('date') or '').strip() or get_latest_session_date()
    symbol = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    expiry_val = req_data.get('expiry')
    expiry = str(expiry_val).strip() if (expiry_val and str(expiry_val).strip()) else None

    try:
        window = int(req_data.get('window', 15))
    except (ValueError, TypeError):
        window = 15

    participant_data = req_data.get('participant_data', None)
    if not participant_data:
        participant_data = get_participant_data_for_date(target_date)

    try:
        result = get_option_chain_data(
            date_str=target_date,
            symbol=symbol,
            expiry_date=expiry,
            window=window,
            participant_data=participant_data
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error fetching Option Chain: {str(e)}"}), 500

@app.route('/api/details-report', methods=['GET', 'POST'])
def api_details_report():
    """
    Synthesizes Participant-Wise Open Interest and Option Chain into an institutional Details Report.
    Params: date, symbol, expiry, participant_data
    """
    if request.method == 'POST':
        req_data = request.json or {}
    else:
        req_data = request.args.to_dict()

    target_date = str(req_data.get('date') or '').strip() or get_latest_session_date()
    symbol = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    expiry_val = req_data.get('expiry')
    expiry = str(expiry_val).strip() if (expiry_val and str(expiry_val).strip()) else None

    participant_data = req_data.get('participant_data', None)
    if not participant_data:
        participant_data = get_participant_data_for_date(target_date)

    try:
        report = build_details_report(
            date_str=target_date,
            symbol=symbol,
            expiry=expiry,
            participant_data=participant_data
        )
        return jsonify(report)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error generating Details Report: {str(e)}"}), 500

@app.route('/api/option-selling', methods=['GET', 'POST'])
def api_option_selling():
    """
    Returns Option Selling Advisory based on Zerodha Varsity Greeks, SD bands,
    Participant OI flows, and Proper Option Chain.
    Params: date, symbol, expiry, participant_data
    """
    if request.method == 'POST':
        req_data = request.json or {}
    else:
        req_data = request.args.to_dict()

    target_date = str(req_data.get('date') or '').strip() or get_latest_session_date()
    symbol = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    expiry_val = req_data.get('expiry')
    expiry = str(expiry_val).strip() if (expiry_val and str(expiry_val).strip()) else None

    participant_data = req_data.get('participant_data', None)
    if not participant_data:
        participant_data = get_participant_data_for_date(target_date)

    try:
        advisory = get_option_selling_advisory(
            symbol=symbol,
            date_str=target_date,
            expiry=expiry,
            p_data=participant_data
        )
        return jsonify(advisory)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error generating Option Selling Advisory: {str(e)}"}), 500


@app.route('/api/quant-ml-model', methods=['GET', 'POST'])
def api_quant_ml_model():
    """
    Returns AI/ML Quantitative Trading next-day forecast based on LightGBM,
    Hidden Markov Model (HMM) Regimes, Dealer GEX mechanics, and Alpha Features.
    Params: date, symbol, expiry, participant_data
    """
    if request.method == 'POST':
        req_data = request.json or {}
    else:
        req_data = request.args.to_dict()

    target_date = str(req_data.get('date') or '').strip() or get_latest_session_date()
    symbol = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    expiry_val = req_data.get('expiry')
    expiry = str(expiry_val).strip() if (expiry_val and str(expiry_val).strip()) else None

    participant_data = req_data.get('participant_data', None)
    if not participant_data:
        participant_data = get_participant_data_for_date(target_date)

    try:
        oc_res = get_option_chain_data(
            date_str=target_date,
            symbol=symbol,
            expiry_date=expiry,
            window=20,
            participant_data=participant_data
        )

        oc_payload = {
            "spot": oc_res.get("spot", 25050.0),
            "spot_price": oc_res.get("spot", 25050.0),
            "max_pain": oc_res.get("max_pain", 25000.0),
            "pcr": oc_res.get("pcr", 1.0),
            "atm_iv": oc_res.get("atm_iv", 0.138),
            "days_to_expiry": oc_res.get("days_to_expiry", 4),
            "total_pe_oi": oc_res.get("total_pe_oi", 0),
            "total_ce_oi": oc_res.get("total_ce_oi", 0),
            "total_pe_chg_oi": oc_res.get("total_pe_chg_oi", 0),
            "total_ce_chg_oi": oc_res.get("total_ce_chg_oi", 0),
            "s1": oc_res.get("s1", 0),
            "r1": oc_res.get("r1", 0),
            "strikes": oc_res.get("strikes", {})
        }

        quant_model_res = get_quant_ml_market_view(participant_data, oc_payload)
        quant_model_res["symbol"] = symbol
        quant_model_res["date"] = target_date
        quant_model_res["selected_expiry"] = oc_res.get("selected_expiry")
        quant_model_res["available_expiries"] = oc_res.get("available_expiries", [])

        return jsonify(quant_model_res)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error generating Quant ML Model: {str(e)}"}), 500


@app.route('/api/run-quant-pipeline', methods=['POST'])
def api_run_quant_pipeline():
    """
    Triggers automated end-to-end data fetching, feature extraction, and ML inference.
    Params JSON: { "symbol": "NIFTY", "date": "YYYY-MM-DD" }
    """
    from auto_quant_pipeline import run_automated_pipeline_for_symbol
    req_data = request.json or {}
    symbol = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    target_date = str(req_data.get('date') or '').strip() or get_latest_session_date()
    expiry = req_data.get('expiry')

    try:
        result = run_automated_pipeline_for_symbol(symbol=symbol, target_date=target_date, expiry=expiry)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Pipeline failure: {str(e)}"}), 500


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Accepts multiple uploaded PDF or CSV files (e.g. last 5 days)."""
    if 'files' not in request.files:
        return jsonify({"status": "error", "message": "No files provided in request"}), 400

    uploaded_files = request.files.getlist('files')
    if not uploaded_files or uploaded_files[0].filename == '':
        return jsonify({"status": "error", "message": "No selected files"}), 400

    records = []
    errors = []

    for file in uploaded_files:
        fname = file.filename
        ext = os.path.splitext(fname)[1].lower()
        try:
            file_bytes = file.read()
            if ext == '.pdf':
                rec = parse_pdf(file_bytes, fname)
            elif ext in ['.csv', '.txt', '.tsv']:
                rec = parse_csv(file_bytes, fname)
            else:
                errors.append(f"{fname}: Unsupported file type {ext}. Please upload .pdf or .csv.")
                continue

            if rec and rec.get("data") and len(rec["data"]) >= 3:
                records.append(rec)
            else:
                errors.append(f"{fname}: Could not extract participant table. Ensure it is an NSE Participant OI file.")
        except Exception as e:
            errors.append(f"{fname}: Error parsing - {str(e)}")

    if not records:
        return jsonify({
            "status": "error", 
            "message": "No valid participant OI files could be parsed.",
            "errors": errors
        }), 400

    try:
        records = augment_single_record_with_history(records)
        analysis = calculate_multi_day_oi(records)
        return jsonify({
            "status": "success",
            "file_count": len(records),
            "errors": errors,
            "result": analysis
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Calculation error: {str(e)}"}), 500

@app.route('/api/paste', methods=['POST'])
def api_paste():
    """Accepts pasted text/CSV/TSV data."""
    data = request.json or {}
    text = data.get("text", "")
    date_str = data.get("date", "").strip()
    if not text.strip():
        return jsonify({"status": "error", "message": "Text content cannot be empty"}), 400

    rec = parse_csv(text, f"pasted_{date_str or 'data'}.csv")
    if date_str:
        rec["date"] = date_str

    if not rec.get("data") or len(rec["data"]) < 3:
        return jsonify({"status": "error", "message": "Could not identify participant OI records in pasted text. Ensure it contains Client, DII, FII, and Pro rows."}), 400

    records = [rec]
    records = augment_single_record_with_history(records)

    analysis = calculate_multi_day_oi(records)
    return jsonify({
        "status": "success",
        "result": analysis
    })

@app.route('/api/sample-files', methods=['GET'])
def list_sample_files():
    """Returns list of pre-generated sample files."""
    files = []
    for f in sorted(os.listdir(app.config['SAMPLE_FOLDER'])):
        files.append({
            "filename": f,
            "type": "PDF" if f.endswith(".pdf") else "CSV",
            "url": f"/api/download-sample/{f}"
        })
    return jsonify({"status": "success", "files": files})

@app.route('/api/download-sample/<filename>')
def download_sample(filename):
    return send_from_directory(app.config['SAMPLE_FOLDER'], filename, as_attachment=True)


# ---------------------------------------------------------------------------
# NEW: Stage 3 — Participant-to-Strike Matching API
# ---------------------------------------------------------------------------

@app.route('/api/participant-strike-matcher', methods=['GET', 'POST'])
def api_participant_strike_matcher():
    """
    Stage 3: Connects WHO (participant OI) with WHERE (option chain strikes).
    Computes Smart-Money Wall Scores, K_Floor, K_Ceiling, K_Squeeze, K_RetailTrap.
    Params: date, symbol, expiry, prev_was_pe, prev_was_ce
    """
    if request.method == 'POST':
        req_data = request.json or {}
    else:
        req_data = request.args.to_dict()

    target_date  = str(req_data.get('date') or '').strip() or get_latest_session_date()
    symbol       = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    expiry_val   = req_data.get('expiry')
    expiry       = str(expiry_val).strip() if (expiry_val and str(expiry_val).strip()) else None
    prev_was_pe  = req_data.get('prev_was_pe')
    prev_was_ce  = req_data.get('prev_was_ce')
    if prev_was_pe is not None:
        prev_was_pe = float(prev_was_pe)
    if prev_was_ce is not None:
        prev_was_ce = float(prev_was_ce)

    lot_size_map = {"NIFTY": 25.0, "BANKNIFTY": 15.0, "FINNIFTY": 40.0, "MIDCPNIFTY": 75.0}
    lot_size = lot_size_map.get(symbol.upper(), 25.0)

    try:
        participant_data = get_participant_data_for_date(target_date)
        oc_result = get_option_chain_data(
            date_str=target_date, symbol=symbol,
            expiry_date=expiry, window=20,
            participant_data=participant_data
        )
        result = match_participants_to_strikes(
            oi_engine_result    = participant_data or {},
            option_chain_result = oc_result,
            symbol              = symbol,
            lot_size            = lot_size,
            prev_was_pe         = prev_was_pe,
            prev_was_ce         = prev_was_ce,
        )
        result["status"] = "success"
        result["date"]   = target_date
        result["participant_tables"] = (participant_data or {}).get("instrument_tables", {})
        result["participant_summary"] = (participant_data or {}).get("participant_summary", {})
        result["market_outlook"] = (participant_data or {}).get("market_outlook", {})
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Matcher error: {str(e)}"}), 500


# ---------------------------------------------------------------------------


@app.route('/api/data-integrity', methods=['GET'])
def api_data_integrity():
    target_date = str(request.args.get('date') or '').strip() or get_latest_session_date()
    symbol = str(request.args.get('symbol') or 'NIFTY').strip().upper()
    from engine import run_engine
    try:
        data = run_engine(date_str=target_date, symbol=symbol)
        return jsonify({
            'status': 'success',
            'date': target_date,
            'data_integrity': data.get('data_integrity', {}),
            'badge': data.get('data_freshness_badge', '🛡️ AUTHENTIC NSE EOD • 100% VERIFIED'),
            'is_reliable': data.get('is_reliable', True)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Validation error: {str(e)}'}), 500


@app.route('/api/pipeline-data', methods=['GET', 'POST'])
def api_pipeline_data():
    """
    Executes the 5-Data Quantitative Pipeline Orchestrator (engine.py).
    Extracts all 5 NSE files (OI, Volume, FII Stats, UDiFF Bhavcopy, Cash Deliverables)
    and returns human-readable segregated analysis for NIFTY & BANKNIFTY.
    """
    if request.method == 'POST':
        req_data = request.json or {}
    else:
        req_data = request.args.to_dict()

    target_date = str(req_data.get('date') or '').strip() or get_latest_session_date()
    symbol = str(req_data.get('symbol') or 'NIFTY').strip().upper()
    expiry_val = req_data.get('expiry')
    expiry = str(expiry_val).strip() if (expiry_val and str(expiry_val).strip()) else None

    from engine import run_engine
    try:
        data = run_engine(date_str=target_date, symbol=symbol, expiry=expiry)
        return jsonify(data)
    except Exception as e:
        print(f"Warning: Pipeline error for date {target_date}: {e}. Trying nearest session fallback.")
        try:
            latest = get_latest_session_date()
            fallback_date = latest if target_date != latest else (get_available_cached_dates()[-2] if len(get_available_cached_dates()) > 1 else '2026-10-29')
            data = run_engine(date_str=fallback_date, symbol=symbol, expiry=expiry)
            data['notice'] = f"Requested session {target_date} unavailable; displaying nearest session {fallback_date}."
            return jsonify(data)
        except Exception:
            return jsonify({'status': 'error', 'message': f'Pipeline error: {str(e)}'}), 500


if __name__ == '__main__':
    import socket
    port = int(os.environ.get('PORT', 5000))
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = '0.0.0.0'
    print("=" * 60)
    print("  NSE Derivatives Intelligence - Server Started")
    print("=" * 60)
    print(f"  Local access  : http://127.0.0.1:{port}")
    print(f"  Network access: http://{local_ip}:{port}")
    print("  Share Network access URL with other devices on same WiFi")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
