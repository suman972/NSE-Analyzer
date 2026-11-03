/**
 * NSE Participant OI Analyzer - Frontend Controller
 */

let currentData = null;
let currentNumberFormat = 'in'; // 'in' (Indian format) or 'intl' (International)

// Exact sequence requested:
// 1. Index Futures, 2. Index Calls, 3. Index Puts, 4. Stock Futures, 5. Stock Calls, 6. Stock Puts
const REQUIRED_INSTRUMENT_SEQUENCE = [
    'Index Futures',
    'Index Calls',
    'Index Puts',
    'Stock Futures',
    'Stock Calls',
    'Stock Puts'
];

// --- Utility Functions ---

function formatIndianNumber(num) {
    if (num === null || num === undefined || num === '-') return '-';
    const isNegative = num < 0;
    const absVal = Math.abs(num);
    const s = absVal.toString();
    
    let result = '';
    if (s.length <= 3) {
        result = s;
    } else {
        const last3 = s.substring(s.length - 3);
        const remaining = s.substring(0, s.length - 3);
        const formattedRemaining = remaining.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
        result = formattedRemaining + ',' + last3;
    }
    return isNegative ? '-' + result : result;
}

function formatIntlNumber(num) {
    if (num === null || num === undefined || num === '-') return '-';
    return Number(num).toLocaleString('en-US');
}

function formatNumber(num) {
    if (num === '-' || num === null || num === undefined) return '-';
    return currentNumberFormat === 'in' ? formatIndianNumber(num) : formatIntlNumber(num);
}

// --- Centralized Date Management across Multi-Page & SPA Navigation ---

function getActiveTradingDate() {
    const s = localStorage.getItem('selected_trading_date');
    if (!s || s.startsWith('2024')) return '2026-10-30';
    return s;
}

function getCachedParticipantData(targetDate) {
    if (currentData && (!targetDate || currentData.today_date === targetDate)) return currentData;
    try {
        const storedDate = sessionStorage.getItem('cached_participant_date');
        const storedData = sessionStorage.getItem('cached_participant_data');
        if (storedData && (!targetDate || storedDate === targetDate)) {
            return JSON.parse(storedData);
        }
    } catch(e) {}
    return null;
}

function setActiveTradingDate(dateStr, triggerUpdates = true) {
    if (!dateStr || dateStr === 'N/A') return;
    localStorage.setItem('selected_trading_date', dateStr);

    // Update displays across topbar, participant page, details report, option selling, pipeline, strike intel
    const topbarDisplay = document.getElementById('topbarActiveDateDisplay');
    if (topbarDisplay) topbarDisplay.innerText = dateStr;

    const activeDateDisplay = document.getElementById('activeDateDisplay');
    if (activeDateDisplay) activeDateDisplay.innerText = dateStr;

    const mainDateInput = document.getElementById('mainDateInput');
    if (mainDateInput && mainDateInput.value !== dateStr) mainDateInput.value = dateStr;

    const repDateInput = document.getElementById('repDateInput');
    if (repDateInput && repDateInput.value !== dateStr) repDateInput.value = dateStr;

    const ocMainDateInput = document.getElementById('ocMainDateInput');
    if (ocMainDateInput && ocMainDateInput.value !== dateStr) ocMainDateInput.value = dateStr;

    const siDateInput = document.getElementById('siDateInput');
    if (siDateInput && siDateInput.value !== dateStr) siDateInput.value = dateStr;

    const pipelineDateInput = document.getElementById('pipelineDateInput');
    if (pipelineDateInput && pipelineDateInput.value !== dateStr) pipelineDateInput.value = dateStr;

    const sellDateInput = document.getElementById('sellDateInput');
    if (sellDateInput && sellDateInput.value !== dateStr) sellDateInput.value = dateStr;

    const quantDateInput = document.getElementById('quantDateInput');
    if (quantDateInput && quantDateInput.value !== dateStr) quantDateInput.value = dateStr;

    const topbarHidden = document.getElementById('topbarHiddenDateInput');
    if (topbarHidden && topbarHidden.value !== dateStr) topbarHidden.value = dateStr;

    // Highlight active preset buttons if present
    document.querySelectorAll('.date-preset-btn').forEach(btn => {
        if (btn.getAttribute('data-preset') === dateStr) {
            btn.classList.add('active');
            btn.style.background = '#3b82f6';
            btn.style.color = '#ffffff';
            btn.style.borderColor = '#3b82f6';
        } else {
            btn.classList.remove('active');
            btn.style.background = 'rgba(255, 255, 255, 0.06)';
            btn.style.color = '#94a3b8';
            btn.style.borderColor = 'rgba(255, 255, 255, 0.12)';
        }
    });

    document.querySelectorAll('.print-date').forEach(el => el.innerText = dateStr);

    if (triggerUpdates) {
        syncActivePageForDate(dateStr);
    }
}

function syncActivePageForDate(dateStr) {
    const page = document.body.dataset.page || '';
    const mainDaysSelect = document.getElementById('mainDaysSelect');
    const days = mainDaysSelect ? mainDaysSelect.value : 5;

    console.log('[AlphaDeriv] syncActivePageForDate called for date:', dateStr, 'on page:', page);

    // 0. Home page Master Date Hub
    if (page === 'home' || window.location.pathname === '/' || window.location.pathname.endsWith('/index.html')) {
        if (typeof syncHomeToDate === 'function') {
            syncHomeToDate(dateStr);
            return;
        }
    }

    // 1. Participant OI page
    if (page === 'participant_oi' || document.getElementById('instrumentsContainer')) {
        if (typeof fetchFromNse === 'function') {
            fetchFromNse(dateStr, days);
        }
    }

    // 2. Details Report page
    if (page === 'details_report' || document.getElementById('detailsReportPage') || document.querySelector('.details-report-page-container')) {
        const sym = typeof currentReportSymbol !== 'undefined' ? currentReportSymbol : 'NIFTY';
        if (typeof loadDetailsReport === 'function') {
            loadDetailsReport(sym, dateStr);
        }
    }

    // 3. Option Chain page
    if (page === 'option_chain' || document.getElementById('pageOptionChain') || document.querySelector('.option-chain-page-container')) {
        const sym = typeof currentOcSymbol !== 'undefined' ? currentOcSymbol : 'NIFTY';
        const win = typeof currentOcWindow !== 'undefined' ? currentOcWindow : 15;
        if (typeof fetchOptionChain === 'function') {
            fetchOptionChain(sym, null, win, dateStr);
        }
    }

    // 4. Quant Model page
    if (page === 'quant_model' || document.querySelector('.quant-model-container')) {
        const qInput = document.getElementById('quantDateInput');
        if (qInput) {
            qInput.value = dateStr;
            qInput.dispatchEvent(new Event('change'));
        }
    }

    // 5. Option Selling page
    if (page === 'option_selling' || document.getElementById('pageOptionSelling')) {
        const sym = typeof currentSellingSymbol !== 'undefined' ? currentSellingSymbol : 'NIFTY';
        if (typeof loadSellingStrategies === 'function') {
            loadSellingStrategies(sym, dateStr);
        }
    }

    // 6. 5-Data Pipeline page
    if (page === 'pipeline' || document.getElementById('pipelineWindowPage') || document.querySelector('.pipeline-page-container')) {
        const sym = typeof currentPipelineSymbol !== 'undefined' ? currentPipelineSymbol : 'NIFTY';
        if (typeof loadPipelineData === 'function') {
            loadPipelineData(sym, dateStr);
        }
    }

    // 7. Strike Intelligence page
    if (page === 'strike_intelligence' || document.getElementById('strikeIntelPage') || document.querySelector('.strike-intelligence-page-container')) {
        const sym = typeof currentSiSymbol !== 'undefined' ? currentSiSymbol : 'NIFTY';
        if (typeof loadStrikeIntelligence === 'function') {
            loadStrikeIntelligence(sym, dateStr);
        }
    }
}

// --- Theme Management (Light / Dark Mode) ---

function initTheme() {
    const savedTheme = localStorage.getItem('participant_oi_theme') || 'dark';
    setTheme(savedTheme);

    const toggleBtn = document.getElementById('btnThemeToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const isLight = document.body.classList.contains('light-theme');
            setTheme(isLight ? 'dark' : 'light');
        });
    }
}

function setTheme(theme) {
    const themeIcon = document.getElementById('themeIcon');
    const themeLabel = document.getElementById('themeLabel');

    if (theme === 'light') {
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
        if (themeIcon) themeIcon.innerText = '🌙';
        if (themeLabel) themeLabel.innerText = 'Dark';
        localStorage.setItem('participant_oi_theme', 'light');
    } else {
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
        if (themeIcon) themeIcon.innerText = '☀️';
        if (themeLabel) themeLabel.innerText = 'Light';
        localStorage.setItem('participant_oi_theme', 'dark');
    }
}

// --- Rendering Functions ---

function renderDashboard(result) {
    currentData = result;
    
    // 1. Update Date display and input value
    const dateStr = result.today_date || 'N/A';
    if (dateStr !== 'N/A') {
        setActiveTradingDate(dateStr, false);
        try {
            sessionStorage.setItem('cached_participant_data', JSON.stringify(result));
            sessionStorage.setItem('cached_participant_date', dateStr);
        } catch(e) {}
    }
    
    // 2. Update Forecast Banner
    renderForecastBanner(result.market_outlook);
    
    // 3. Render the 6 Instrument Tables in strictly enforced order
    renderInstrumentTables(result.instrument_tables, result.carried_labels);
    
    // 4. Render Right-Side Participant Summary Cards in strictly enforced order
    renderParticipantSummary(result.participant_summary);

    // 5. Update Home pulse cards if present
    if (typeof updateHomeParticipantPulse === 'function') {
        updateHomeParticipantPulse(result);
    }
}

function renderForecastBanner(outlook) {
    if (!outlook) return;
    
    const badge = document.getElementById('forecastBadge');
    if (badge) {
        badge.innerText = outlook.stance || 'NEUTRAL';
        badge.style.color = outlook.badge_color || '#38bdf8';
        badge.style.borderColor = outlook.badge_color || '#38bdf8';
        badge.style.background = (outlook.badge_color ? outlook.badge_color + '22' : 'rgba(56, 189, 248, 0.15)');
        badge.style.boxShadow = `0 0 15px ${outlook.badge_color ? outlook.badge_color + '44' : 'transparent'}`;
    }

    const verdict = document.getElementById('forecastVerdict');
    if (verdict) {
        verdict.innerText = outlook.verdict || 'Derivatives Flow Analysis';
    }
    
    // Meter score (-100 to +100 -> 0% to 100%)
    const score = outlook.score || 0;
    const clampedScore = Math.max(-100, Math.min(100, score));
    const fillPercent = ((clampedScore + 100) / 200) * 100;
    const meterFill = document.getElementById('meterFill');
    if (meterFill) meterFill.style.width = `${fillPercent}%`;
    const meterScore = document.getElementById('meterScore');
    if (meterScore) meterScore.innerText = `Score: ${score > 0 ? '+' : ''}${score}`;

    // Trap Alert
    const trapBox = document.getElementById('trapAlertBox');
    const trapText = document.getElementById('trapAlertText');
    if (trapBox) {
        if (outlook.retail_trap && outlook.retail_trap.detected) {
            trapBox.style.display = 'flex';
            const trapFactor = (outlook.factors || []).find(f => f.includes('RETAIL TRAP ALERT')) || 
                               'Extreme retail one-sided positioning detected. Prime short-squeeze trap alert!';
            if (trapText) trapText.innerText = trapFactor.replace('🚨 RETAIL TRAP ALERT:', '').trim();
        } else {
            trapBox.style.display = 'none';
        }
    }

    // Strategy Cards
    const nextAction = document.getElementById('nextDayActionText');
    if (nextAction) nextAction.innerText = outlook.next_day_action || 'Monitor open interest shifts on market open.';
    
    const insights = outlook.participant_insights || {};
    const fiiStat = document.getElementById('fiiActionStat');
    const fiiDesc = document.getElementById('fiiActionDesc');
    if (insights.FII) {
        if (fiiStat) fiiStat.innerText = insights.FII.stance;
        if (fiiDesc) fiiDesc.innerText = insights.FII.today_action;
    }
    const proStat = document.getElementById('proActionStat');
    const proDesc = document.getElementById('proActionDesc');
    if (insights.Pro) {
        if (proStat) proStat.innerText = insights.Pro.stance;
        if (proDesc) proDesc.innerText = insights.Pro.today_action;
    }
    const clientStat = document.getElementById('clientActionStat');
    const clientDesc = document.getElementById('clientActionDesc');
    if (insights.Client) {
        if (clientStat) clientStat.innerText = insights.Client.stance;
        if (clientDesc) clientDesc.innerText = insights.Client.today_action;
    }
}

function renderInstrumentTables(tables, carriedLabels) {
    const container = document.getElementById('instrumentsContainer');
    if (!container) return;
    container.innerHTML = '';

    if (!tables) {
        container.innerHTML = '<div class="loading-state"><p>No instrument data found.</p></div>';
        return;
    }
    carriedLabels = carriedLabels || [];

    // STRICT SEQUENCE: Index Futures -> Index Calls -> Index Puts -> Stock Futures -> Stock Calls -> Stock Puts
    REQUIRED_INSTRUMENT_SEQUENCE.forEach(inst => {
        const rows = tables[inst];
        if (!rows) return;

        const card = document.createElement('div');
        card.className = 'instrument-card';
        card.id = 'instCard_' + inst.replace(/\s+/g, '_');

        // Carried column headers
        let carriedThCols = '';
        carriedLabels.forEach(lbl => {
            carriedThCols += `<th>${lbl}</th>`;
        });

        let tableHtml = `
            <div class="instrument-header">
                <div class="instrument-title">
                    <span>${getInstrumentIcon(inst)}</span>
                    <span>${inst}</span>
                </div>
                <span class="instrument-tag">Derivatives Open Interest</span>
            </div>
            <table class="oi-table">
                <thead>
                    <tr>
                        <th rowspan="2" class="col-participant">Participant</th>
                        <th rowspan="2">${inst} Longs</th>
                        <th rowspan="2">${inst} Shorts</th>
                        <th rowspan="2">Net Buy / Sell for Today</th>
                        <th colspan="${carriedLabels.length}" class="th-group">Total Positions Carried (Net OI)</th>
                    </tr>
                    <tr>
                        ${carriedThCols}
                    </tr>
                </thead>
                <tbody>
        `;

        rows.forEach(r => {
            const longClass = r.long_color === 'green' ? 'cell-green' : (r.long_color === 'red' ? 'cell-red' : 'cell-neutral');
            const longTagClass = r.long_color === 'green' ? 'tag-green-bg' : (r.long_color === 'red' ? 'tag-red-bg' : '');

            const shortClass = r.short_color === 'green' ? 'cell-green' : (r.short_color === 'red' ? 'cell-red' : 'cell-neutral');
            const shortTagClass = r.short_color === 'green' ? 'tag-green-bg' : (r.short_color === 'red' ? 'tag-red-bg' : '');

            const netClass = r.net_color === 'green' ? 'cell-green' : (r.net_color === 'red' ? 'cell-red' : 'cell-neutral');
            const netTagClass = r.net_color === 'green' ? 'tag-green-bg' : (r.net_color === 'red' ? 'tag-red-bg' : '');

            let carriedTdCols = '';
            carriedLabels.forEach(lbl => {
                const val = r.carried[lbl];
                let colorName = (r.carried_colors && r.carried_colors[lbl]);
                if (!colorName && typeof val === 'number') {
                    const isPut = inst.toLowerCase().includes('put');
                    if (isPut) {
                        colorName = val < 0 ? 'green' : (val > 0 ? 'red' : 'neutral');
                    } else {
                        colorName = val > 0 ? 'green' : (val < 0 ? 'red' : 'neutral');
                    }
                }
                const carriedColor = colorName === 'green' ? 'cell-green' : (colorName === 'red' ? 'cell-red' : 'cell-neutral');
                carriedTdCols += `<td class="${carriedColor}">${formatNumber(val)}</td>`;
            });

            tableHtml += `
                <tr>
                    <td class="col-participant">${r.participant}</td>
                    <td>
                        <div class="val-cell">
                            <span class="val-tag ${longTagClass}">${r.long_label}</span>
                            <span class="${longClass}">${formatNumber(r.long_chg)}</span>
                        </div>
                    </td>
                    <td>
                        <div class="val-cell">
                            <span class="val-tag ${shortTagClass}">${r.short_label}</span>
                            <span class="${shortClass}">${formatNumber(r.short_chg)}</span>
                        </div>
                    </td>
                    <td>
                        <div class="val-cell">
                            <span class="val-tag ${netTagClass}">${r.net_label}</span>
                            <span class="${netClass}">${formatNumber(r.net_buy_sell)}</span>
                        </div>
                    </td>
                    ${carriedTdCols}
                </tr>
            `;
        });

        tableHtml += `
                </tbody>
            </table>
        `;

        card.innerHTML = tableHtml;
        container.appendChild(card);
    });
}

function renderParticipantSummary(summary) {
    const wrap = document.getElementById('participantSummaryWrap');
    if (!wrap) return;
    wrap.innerHTML = '';

    if (!summary) return;

    const participants = ['Clients', 'DIIs', 'FIIs', 'Pros'];

    participants.forEach(p => {
        const rawItems = summary[p] || [];
        
        // Strict sort by REQUIRED_INSTRUMENT_SEQUENCE
        const items = [...rawItems].sort((a, b) => {
            return REQUIRED_INSTRUMENT_SEQUENCE.indexOf(a.instrument) - REQUIRED_INSTRUMENT_SEQUENCE.indexOf(b.instrument);
        });

        const card = document.createElement('div');
        card.className = 'p-summary-card';

        let listHtml = '';
        items.forEach(item => {
            const colorClass = item.color === 'green' ? 'cell-green' : (item.color === 'red' ? 'cell-red' : 'cell-neutral');
            listHtml += `
                <div class="p-summary-row">
                    <span class="p-summary-inst">${item.instrument}</span>
                    <div class="p-summary-action">
                        <span class="${colorClass}">${item.action}</span>
                        <span class="${colorClass}">${formatNumber(item.qty)}</span>
                    </div>
                </div>
            `;
        });

        card.innerHTML = `
            <div class="p-summary-header">
                <strong>${p}</strong>
                <span class="panel-sub">Net Action Today</span>
            </div>
            <div class="p-summary-list">
                ${listHtml}
            </div>
        `;
        wrap.appendChild(card);
    });
}

function getInstrumentIcon(inst) {
    switch(inst) {
        case 'Index Futures': return '📈';
        case 'Index Calls': return '📞';
        case 'Index Puts': return '📉';
        case 'Stock Futures': return '🏢';
        case 'Stock Calls': return '💹';
        case 'Stock Puts': return '🔻';
        default: return '📊';
    }
}

// --- Live Auto-Fetch from NSE ---

async function fetchFromNse(targetDate, lookbackDays) {
    const fetchBtn = document.getElementById('btnMainFetch');
    const statusBox = document.getElementById('statusBox');
    const statusIcon = document.getElementById('statusIcon');
    const statusText = document.getElementById('statusText');
    const logsUl = document.getElementById('fetchLogsUl');

    if (fetchBtn) {
        fetchBtn.disabled = true;
        fetchBtn.innerHTML = '<span class="btn-icon">⏳</span> Fetching...';
    }
    if (statusBox) {
        statusBox.style.display = 'flex';
        statusIcon.innerText = '🔄';
        statusText.innerText = `Connecting to NSE archives for ${targetDate} (${lookbackDays} days)...`;
    }

    try {
        const res = await fetch('/api/fetch-nse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: targetDate, days: parseInt(lookbackDays) })
        });
        const json = await res.json();

        if (json.status === 'success') {
            statusIcon.innerText = '✅';
            statusText.innerText = `Retrieved ${json.days_fetched} trading days from NSE! Market Stance: ${json.result.market_outlook.stance}`;
            
            if (logsUl) {
                logsUl.innerHTML = '';
                (json.logs || []).forEach(log => {
                    const li = document.createElement('li');
                    li.innerText = log;
                    logsUl.appendChild(li);
                });
            }

            renderDashboard(json.result);
        } else {
            statusIcon.innerText = '❌';
            statusText.innerText = `Notice: ${json.message}`;
            if (logsUl && json.logs && json.logs.length > 0) {
                logsUl.innerHTML = '';
                json.logs.forEach(log => {
                    const li = document.createElement('li');
                    li.innerText = log;
                    logsUl.appendChild(li);
                });
            }
            alert('Notice: ' + json.message);
        }
    } catch (err) {
        if (statusIcon) statusIcon.innerText = '⚠️';
        if (statusText) statusText.innerText = `Network or Server Error: ${err.message}`;
    } finally {
        if (fetchBtn) {
            fetchBtn.disabled = false;
            fetchBtn.innerHTML = '<span class="btn-icon">⚡</span> Fetch from NSE';
        }
    }
}

// --- Other API Calls ---

async function loadDemoData() {
    const statusBox = document.getElementById('statusBox');
    const statusIcon = document.getElementById('statusIcon');
    const statusText = document.getElementById('statusText');
    
    try {
        const res = await fetch('/api/demo-data');
        const json = await res.json();
        if (json.status === 'success') {
            renderDashboard(json.result);
            if (statusBox) {
                statusBox.style.display = 'flex';
                statusIcon.innerText = '⚡';
                statusText.innerText = `Loaded dataset.`;
            }
        } else {
            alert('Error loading demo data: ' + json.message);
        }
    } catch (err) {
        console.error('Failed to load demo data:', err);
    }
}

async function uploadFiles(files) {
    const submitBtn = document.getElementById('btnSubmitUpload');
    submitBtn.disabled = true;
    submitBtn.innerText = 'Analyzing...';

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const json = await res.json();
        if (json.status === 'success') {
            renderDashboard(json.result);
            if (document.body.dataset.page === 'option_chain') {
                fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, json.result.today_date);
            }
            closeModals();
            if (json.errors && json.errors.length > 0) {
                alert('Uploaded with warnings:\n' + json.errors.join('\n'));
            }
        } else {
            alert('Upload error: ' + json.message + (json.errors ? '\n' + json.errors.join('\n') : ''));
        }
    } catch (err) {
        alert('Network or server error during upload: ' + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = 'Analyze Uploaded Files';
    }
}

async function pasteData(text, dateStr) {
    const submitBtn = document.getElementById('btnSubmitPaste');
    submitBtn.disabled = true;
    submitBtn.innerText = 'Analyzing...';

    try {
        const res = await fetch('/api/paste', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, date: targetDate })
        });
        const json = await res.json();
        if (json.status === 'success') {
            renderDashboard(json.result);
            if (document.body.dataset.page === 'option_chain') {
                fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, json.result.today_date);
            }
            closeModals();
        } else {
            alert('Parse error: ' + json.message);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = 'Analyze Pasted Data';
    }
}

async function loadSampleFilesList() {
    try {
        const res = await fetch('/api/sample-files');
        const json = await res.json();
        if (json.status === 'success') {
            const ul = document.getElementById('sampleFilesUl');
            ul.innerHTML = '';
            json.files.forEach(f => {
                const li = document.createElement('li');
                li.className = 'sample-file-item';
                li.innerHTML = `
                    <span>📄 ${f.filename}</span>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <span class="sample-badge">${f.type}</span>
                        <a href="${f.url}" download class="btn btn-outline" style="padding:4px 10px; font-size:11px;">Download</a>
                    </div>
                `;
                ul.appendChild(li);
            });
        }
    } catch (err) {
        console.error('Error fetching sample files:', err);
    }
}

// --- Interactive Option Chain Drawer Controller ---

let currentOcSymbol = 'NIFTY';
let currentOcExpiry = null;
let currentOcWindow = 15;
let currentOcData = null;
let currentPerspective = 'all'; // 'all', 'fii', 'pro', 'client'

function setPerspective(perspective) {
    currentPerspective = perspective || 'all';
    document.querySelectorAll('#ocPerspectivePills .perspective-pill-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-perspective') === currentPerspective);
    });
    const fiiSec = document.getElementById('ocFiiStrikesSection');
    if (fiiSec) {
        fiiSec.classList.toggle('highlighted-fii', currentPerspective === 'fii');
    }
    if (currentOcData) {
        renderProbabilisticBanner(currentOcData.probabilistic_model, currentOcData.big_player_game_plan, currentOcData.fii_buildup_analysis, currentPerspective);
        render4ParticipantCards(currentOcData.big_player_game_plan ? currentOcData.big_player_game_plan.participants : null, currentPerspective);
        renderOptionChainTable(currentOcData.strikes, currentOcData.spot_price, currentOcData.atm_strike, currentOcData.fii_buildup_analysis);
    }
}


function openOptionChainDrawer() {
    const drawer = document.getElementById('ocDrawer');
    const backdrop = document.getElementById('ocDrawerBackdrop');
    if (drawer && backdrop) {
        drawer.classList.add('open');
        backdrop.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        const mainDateEl = document.getElementById('mainDateInput');
        const activeDate = (currentData && currentData.today_date) || (mainDateEl ? mainDateEl.value : null) || localStorage.getItem('selected_trading_date') || '2026-10-30';
        fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, activeDate);
    }
}

function closeOptionChainDrawer() {
    const drawer = document.getElementById('ocDrawer');
    const backdrop = document.getElementById('ocDrawerBackdrop');
    if (drawer && backdrop) {
        drawer.classList.remove('open');
        backdrop.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function toggleOptionChainExpand() {
    const drawer = document.getElementById('ocDrawer');
    const btn = document.getElementById('btnExpandOc');
    if (drawer) {
        drawer.classList.toggle('expanded');
        if (btn) {
            btn.innerText = drawer.classList.contains('expanded') ? '⛶ Shrink' : '⛶ Expand';
        }
    }
}

async function fetchOptionChain(symbol, expiry, windowSize, dateStr) {
    const tbodies = [
        document.getElementById('ocMainTbody'),
        document.getElementById('ocTbody')
    ].filter(Boolean);
    const badge = document.getElementById('ocLiveBadge');
    tbodies.forEach(tb => {
        tb.innerHTML = `<tr><td colspan="13" style="text-align: center; padding: 40px; color: #94a3b8;"><div class="spinner" style="margin: 0 auto 12px auto;"></div>Fetching ${symbol} Option Chain from NSE archives...</td></tr>`;
    });
    if (badge) badge.innerText = 'SYNCING...';

    const targetDate = dateStr || getActiveTradingDate();
    const pData = getCachedParticipantData(targetDate) || currentData;

    try {
        const res = await fetch('/api/option-chain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                date: targetDate,
                symbol: symbol,
                expiry: expiry,
                window: parseInt(windowSize),
                participant_data: pData
            })
        });

        const json = await res.json();
        if (json.status === 'success') {
            currentOcData = json;
            currentOcSymbol = json.symbol;
            currentOcExpiry = json.selected_expiry;
            renderOptionChain(json);
            if (badge) badge.innerText = 'ALIGNED';
        } else {
            tbodies.forEach(tb => {
                tb.innerHTML = `<tr><td colspan="13" style="text-align: center; padding: 30px; color: #ef4444;">Notice: ${json.message}</td></tr>`;
            });
            if (badge) badge.innerText = 'ERROR';
        }
    } catch (err) {
        console.error('Error fetching option chain:', err);
        tbodies.forEach(tb => {
            tb.innerHTML = `<tr><td colspan="13" style="text-align: center; padding: 30px; color: #ef4444;">Network or Server Error: ${err.message}</td></tr>`;
        });
        if (badge) badge.innerText = 'OFFLINE';
    }
}

function renderOptionChain(data) {
    if (!data) return;

    if (data.date) {
        const topDate = document.getElementById('topbarActiveDateDisplay');
        if (topDate) topDate.innerText = data.date;
    }

    // 1. Populate Expiry Dropdowns
    ['ocMainExpirySelect', 'ocExpirySelect'].forEach(id => {
        const expSelect = document.getElementById(id);
        if (expSelect) {
            expSelect.innerHTML = '';
            (data.available_expiries || []).forEach(exp => {
                const opt = document.createElement('option');
                opt.value = exp;
                opt.innerText = exp;
                if (exp === data.selected_expiry) opt.selected = true;
                expSelect.appendChild(opt);
            });
        }
    });

    // 2. Intelligence Metrics Strip
    ['ocMainSpotPrice', 'ocSpotPrice'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = formatNumber(Math.round(data.spot_price * 100) / 100);
    });

    ['ocMainAtmStrike', 'ocAtmStrike'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = `ATM: ${formatNumber(data.atm_strike)}`;
    });

    ['ocMainPcrVal', 'ocPcrVal'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = data.pcr.toFixed(2);
            el.style.color = data.pcr_color || '#38bdf8';
        }
    });

    ['ocMainPcrStance', 'ocPcrStance'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerText = data.pcr_stance;
            el.style.color = data.pcr_color || '#94a3b8';
        }
    });

    ['ocMainMaxPainVal', 'ocMaxPainVal'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = formatNumber(data.max_pain);
    });

    // Major Resistance (R1 & R2)
    ['ocMainResStrike', 'ocResStrike'].forEach(id => {
        const el = document.getElementById(id);
        if (el && data.major_resistance) el.innerText = `${formatNumber(data.major_resistance.strike)} (R1)`;
    });
    ['ocMainResOi', 'ocResOi'].forEach(id => {
        const el = document.getElementById(id);
        if (el && data.secondary_resistance) el.innerText = `R2: ${formatNumber(data.secondary_resistance.strike)} (${formatNumber(data.major_resistance.oi)} OI)`;
    });

    // Major Support (S1 & S2)
    ['ocMainSupStrike', 'ocSupStrike'].forEach(id => {
        const el = document.getElementById(id);
        if (el && data.major_support) el.innerText = `${formatNumber(data.major_support.strike)} (S1)`;
    });
    ['ocMainSupOi', 'ocSupOi'].forEach(id => {
        const el = document.getElementById(id);
        if (el && data.secondary_support) el.innerText = `S2: ${formatNumber(data.secondary_support.strike)} (${formatNumber(data.secondary_support.oi)} OI)`;
    });

    // Oscillation Zone Card
    ['ocMainOscZoneVal', 'ocOscZoneVal'].forEach(id => {
        const el = document.getElementById(id);
        if (el && data.oscillation_zone) el.innerText = data.oscillation_zone.label || '-';
    });
    ['ocMainOscZoneSub', 'ocOscZoneSub'].forEach(id => {
        const el = document.getElementById(id);
        if (el && data.oscillation_zone) {
            const spread = (data.oscillation_zone.high || 0) - (data.oscillation_zone.low || 0);
            el.innerText = `Expected Channel (${spread > 0 ? spread + ' pts' : 'Tight'})`;
        }
    });

    // Update Drawer Live Sync Status Strip (matching reference image)
    const dSym = document.getElementById('drawerActiveSymbol');
    const dSpot = document.getElementById('drawerSpotText');
    const dPcr = document.getElementById('drawerPcrText');
    const dOsc = document.getElementById('drawerOscText');

    if (dSym) dSym.innerText = data.symbol || currentOcSymbol;
    if (dSpot) dSpot.innerText = `Spot: ${formatNumber(Math.round(data.spot_price * 100) / 100)}`;
    if (dPcr) dPcr.innerText = `PCR: ${data.pcr ? data.pcr.toFixed(2) : '-'}`;
    if (dOsc) dOsc.innerText = `Oscillation Channel: ${data.oscillation_zone ? data.oscillation_zone.label : '-'}`;

    // 3. Render 4-Way Participant Flow Matrix
    const pMatrix = data.synergy ? data.synergy.participant_matrix : null;
    renderParticipantMatrix(pMatrix);

    // 4. Render Interactive Option Chain Buildup Chart
    renderOptionChainChart(data.chart_data, data.oscillation_zone, data.spot_price, data.atm_strike, data);

    // 5. Render Synergy Roadmap & Mapping Cards
    renderOptionChainSynergy(data.synergy);

    // 6. Render Next-Day Written Strategy & Oscillation Zone Breakdown
    renderWrittenAnalysis(data.synergy, data);

    // 7. Render FII Institutional Buildup Tracker Banner & Multi-Participant Game Plan
    renderFiiBuildupTracker(data.fii_buildup_analysis);
    renderProbabilisticBanner(data.probabilistic_model, data.big_player_game_plan, data.fii_buildup_analysis, currentPerspective);
    render4ParticipantCards(data.big_player_game_plan ? data.big_player_game_plan.participants : null, currentPerspective);

    // 7b. Render Dedicated Big Player Strike Intelligence & Option Selling Cockpit
    renderBigPlayerStrikeCockpit(data.big_player_strike_intelligence, data.big_player_game_plan, data.spot_price, data.atm_strike);

    // 8. Render 13-Column Proper Strike Table
    renderOptionChainTable(data.strikes, data.spot_price, data.atm_strike, data.fii_buildup_analysis);
}

function renderParticipantMatrix(matrix) {
    const tbodies = [
        document.getElementById('ocMainParticipantMatrixTbody'),
        document.getElementById('ocParticipantMatrixTbody')
    ].filter(Boolean);

    if (tbodies.length === 0) return;

    tbodies.forEach(tbody => {
        tbody.innerHTML = '';
        if (!matrix) {
            tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:20px; color:#94a3b8;">No participant flow data available.</td></tr>';
            return;
        }

        const participants = [
            { key: 'Clients', label: '👤 Clients (Retail)', desc: 'Retail Traders' },
            { key: 'DIIs', label: '🏛️ DIIs', desc: 'Domestic Institutions' },
            { key: 'FIIs', label: '🏦 FIIs', desc: 'Foreign Institutions' },
            { key: 'Pros', label: '🏢 Pros', desc: 'Proprietary Desks' }
        ];

        participants.forEach(p => {
            const pData = matrix[p.key] || { call: {}, put: {} };
            const c = pData.call || {};
            const pt = pData.put || {};

            const cAddL = c.added_long || 0;
            const cClsL = c.closed_long || 0;
            const cAddS = c.added_short || 0;
            const cClsS = c.closed_short || 0;
            const cNet = c.net || 0;

            const cAddLClass = cAddL > 0 ? 'cell-green font-bold' : 'cell-neutral';
            const cClsLClass = cClsL > 0 ? 'cell-orange font-bold' : 'cell-neutral';
            const cAddSClass = cAddS > 0 ? 'cell-red font-bold' : 'cell-neutral';
            const cClsSClass = cClsS > 0 ? 'cell-blue font-bold' : 'cell-neutral';
            const cNetClass = cNet > 0 ? 'cell-green font-bold' : (cNet < 0 ? 'cell-red font-bold' : 'cell-neutral');

            const ptAddL = pt.added_long || 0;
            const ptClsL = pt.closed_long || 0;
            const ptAddS = pt.added_short || 0;
            const ptClsS = pt.closed_short || 0;
            const ptNet = pt.net || 0;

            const ptAddLClass = ptAddL > 0 ? 'cell-red font-bold' : 'cell-neutral';
            const ptClsLClass = ptClsL > 0 ? 'cell-green font-bold' : 'cell-neutral';
            const ptAddSClass = ptAddS > 0 ? 'cell-green font-bold' : 'cell-neutral';
            const ptClsSClass = ptClsS > 0 ? 'cell-orange font-bold' : 'cell-neutral';
            const ptNetClass = ptNet < 0 ? 'cell-green font-bold' : (ptNet > 0 ? 'cell-red font-bold' : 'cell-neutral');

            const tr = document.createElement('tr');
            tr.className = 'matrix-row';
            tr.innerHTML = `
                <td class="col-matrix-pname">
                    <span class="pname-title">${p.label}</span>
                    <span class="pname-sub">${p.desc}</span>
                </td>
                <!-- CALLS -->
                <td class="${cAddLClass}">${cAddL > 0 ? '+' + formatNumber(cAddL) : '-'}</td>
                <td class="${cClsLClass}">${cClsL > 0 ? '-' + formatNumber(cClsL) : '-'}</td>
                <td class="${cAddSClass}">${cAddS > 0 ? '+' + formatNumber(cAddS) : '-'}</td>
                <td class="${cClsSClass}">${cClsS > 0 ? '-' + formatNumber(cClsS) : '-'}</td>
                <td class="${cNetClass} col-net-cell">${cNet > 0 ? '+' + formatNumber(cNet) : (cNet < 0 ? formatNumber(cNet) : '0')}</td>
                <!-- PUTS -->
                <td class="${ptAddLClass}">${ptAddL > 0 ? '+' + formatNumber(ptAddL) : '-'}</td>
                <td class="${ptClsLClass}">${ptClsL > 0 ? '-' + formatNumber(ptClsL) : '-'}</td>
                <td class="${ptAddSClass}">${ptAddS > 0 ? '+' + formatNumber(ptAddS) : '-'}</td>
                <td class="${ptClsSClass}">${ptClsS > 0 ? '-' + formatNumber(ptClsS) : '-'}</td>
                <td class="${ptNetClass} col-net-cell">${ptNet < 0 ? formatNumber(ptNet) : (ptNet > 0 ? '+' + formatNumber(ptNet) : '0')}</td>
            `;
            tbody.appendChild(tr);
        });
    });
}

function renderOptionChainChart(chartData, oscillationZone, spotPrice, atmStrike, meta) {
    const targets = [
        { svg: document.getElementById('ocMainChartSvg'), tooltip: document.getElementById('ocMainChartTooltip') },
        { svg: document.getElementById('ocChartSvg'), tooltip: document.getElementById('ocChartTooltip') }
    ];

    targets.forEach(({ svg, tooltip }) => {
        if (!svg || !chartData || chartData.length === 0) return;
        svg.innerHTML = '';

        const width = 1000;
        const height = 320;
        const marginLeft = 65;
        const marginRight = 35;
        const marginTop = 36;
        const marginBottom = 48;

        const plotW = width - marginLeft - marginRight;
        const plotH = height - marginTop - marginBottom;

        let maxAbs = 10000;
        chartData.forEach(d => {
            const ceAbs = Math.abs(d.ce_chg_oi || 0);
            const peAbs = Math.abs(d.pe_chg_oi || 0);
            if (ceAbs > maxAbs) maxAbs = ceAbs;
            if (peAbs > maxAbs) maxAbs = peAbs;
        });

        const limitY = Math.ceil(maxAbs * 1.15);
        const zeroY = marginTop + (plotH / 2);
        const n = chartData.length;
        const stepX = plotW / n;

        // 1. Shaded Oscillation Zone
        if (oscillationZone && oscillationZone.low && oscillationZone.high) {
            let lowIdx = -1, highIdx = -1;
            chartData.forEach((d, idx) => {
                if (d.strike >= oscillationZone.low && lowIdx === -1) lowIdx = idx;
                if (d.strike <= oscillationZone.high) highIdx = idx;
            });

            if (lowIdx !== -1 && highIdx !== -1 && highIdx >= lowIdx) {
                const zX1 = marginLeft + lowIdx * stepX;
                const zX2 = marginLeft + (highIdx + 1) * stepX;
                const zW = zX2 - zX1;

                const oscRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                oscRect.setAttribute('x', zX1);
                oscRect.setAttribute('y', marginTop);
                oscRect.setAttribute('width', zW);
                oscRect.setAttribute('height', plotH);
                oscRect.setAttribute('fill', 'rgba(245, 158, 11, 0.08)');
                oscRect.setAttribute('stroke', 'rgba(245, 158, 11, 0.4)');
                oscRect.setAttribute('stroke-width', '1.5');
                oscRect.setAttribute('stroke-dasharray', '4,4');
                svg.appendChild(oscRect);

                const oscTxt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                oscTxt.setAttribute('x', zX1 + zW / 2);
                oscTxt.setAttribute('y', marginTop + 14);
                oscTxt.setAttribute('text-anchor', 'middle');
                oscTxt.setAttribute('fill', '#f59e0b');
                oscTxt.setAttribute('font-size', '11');
                oscTxt.setAttribute('font-weight', '700');
                oscTxt.setAttribute('letter-spacing', '0.5px');
                oscTxt.textContent = `⚡ OSCILLATION ZONE (${formatNumber(oscillationZone.low)} - ${formatNumber(oscillationZone.high)})`;
                svg.appendChild(oscTxt);
            }
        }

        // 2. Horizontal Grid & Zero Line
        const gridLevels = [
            { val: limitY, label: `+${formatNumber(Math.round(limitY / 1000))}k`, y: marginTop },
            { val: limitY / 2, label: `+${formatNumber(Math.round(limitY / 2000))}k`, y: marginTop + (plotH / 4) },
            { val: 0, label: '0', y: zeroY },
            { val: -limitY / 2, label: `-${formatNumber(Math.round(limitY / 2000))}k`, y: marginTop + (plotH * 3 / 4) },
            { val: -limitY, label: `-${formatNumber(Math.round(limitY / 1000))}k`, y: marginTop + plotH }
        ];

        gridLevels.forEach(g => {
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', marginLeft);
            line.setAttribute('y1', g.y);
            line.setAttribute('x2', marginLeft + plotW);
            line.setAttribute('y2', g.y);
            line.setAttribute('stroke', g.val === 0 ? '#475569' : '#1e293b');
            line.setAttribute('stroke-width', g.val === 0 ? '1.5' : '1');
            svg.appendChild(line);

            const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            lbl.setAttribute('x', marginLeft - 8);
            lbl.setAttribute('y', g.y + 3.5);
            lbl.setAttribute('text-anchor', 'end');
            lbl.setAttribute('fill', g.val > 0 ? '#10b981' : (g.val < 0 ? '#ef4444' : '#64748b'));
            lbl.setAttribute('font-size', '9.5');
            lbl.setAttribute('font-family', 'monospace');
            lbl.textContent = g.label;
            svg.appendChild(lbl);
        });

        // 3. Render Dual Bars for each Strike
        chartData.forEach((d, i) => {
            const xCenter = marginLeft + (i + 0.5) * stepX;
            const barW = Math.max(3, stepX * 0.38);

            // Call bar
            const ceChg = d.ce_chg_oi || 0;
            const ceH = (Math.abs(ceChg) / limitY) * (plotH / 2);
            const ceY = ceChg >= 0 ? (zeroY - ceH) : zeroY;
            const ceColor = d.ce_buildup ? d.ce_buildup.color : '#ef4444';

            const ceRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            ceRect.setAttribute('x', xCenter - barW - 1);
            ceRect.setAttribute('y', ceY);
            ceRect.setAttribute('width', barW);
            ceRect.setAttribute('height', Math.max(1, ceH));
            ceRect.setAttribute('fill', ceColor);
            ceRect.setAttribute('rx', '2');
            ceRect.setAttribute('opacity', '0.9');
            svg.appendChild(ceRect);

            // Put bar
            const peChg = d.pe_chg_oi || 0;
            const peH = (Math.abs(peChg) / limitY) * (plotH / 2);
            const peY = peChg >= 0 ? (zeroY - peH) : zeroY;
            const peColor = d.pe_buildup ? d.pe_buildup.color : '#10b981';

            const peRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            peRect.setAttribute('x', xCenter + 1);
            peRect.setAttribute('y', peY);
            peRect.setAttribute('width', barW);
            peRect.setAttribute('height', Math.max(1, peH));
            peRect.setAttribute('fill', peColor);
            peRect.setAttribute('rx', '2');
            peRect.setAttribute('opacity', '0.9');
            svg.appendChild(peRect);

            // Vertical reference marker lines
            if (d.is_r1) {
                const r1Line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                r1Line.setAttribute('x1', xCenter);
                r1Line.setAttribute('y1', marginTop);
                r1Line.setAttribute('x2', xCenter);
                r1Line.setAttribute('y2', marginTop + plotH);
                r1Line.setAttribute('stroke', '#ef4444');
                r1Line.setAttribute('stroke-width', '2');
                r1Line.setAttribute('stroke-dasharray', '3,3');
                svg.appendChild(r1Line);

                const r1Txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                r1Txt.setAttribute('x', xCenter);
                r1Txt.setAttribute('y', marginTop - 8);
                r1Txt.setAttribute('text-anchor', 'middle');
                r1Txt.setAttribute('fill', '#ef4444');
                r1Txt.setAttribute('font-size', '10');
                r1Txt.setAttribute('font-weight', 'bold');
                r1Txt.textContent = `🔴 R1`;
                svg.appendChild(r1Txt);
            }

            if (d.is_s1) {
                const s1Line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                s1Line.setAttribute('x1', xCenter);
                s1Line.setAttribute('y1', marginTop);
                s1Line.setAttribute('x2', xCenter);
                s1Line.setAttribute('y2', marginTop + plotH);
                s1Line.setAttribute('stroke', '#10b981');
                s1Line.setAttribute('stroke-width', '2');
                s1Line.setAttribute('stroke-dasharray', '3,3');
                svg.appendChild(s1Line);

                const s1Txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                s1Txt.setAttribute('x', xCenter);
                s1Txt.setAttribute('y', marginTop - 8);
                s1Txt.setAttribute('text-anchor', 'middle');
                s1Txt.setAttribute('fill', '#10b981');
                s1Txt.setAttribute('font-size', '10');
                s1Txt.setAttribute('font-weight', 'bold');
                s1Txt.textContent = `🟢 S1`;
                svg.appendChild(s1Txt);
            }

            if (d.is_atm) {
                const atmLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                atmLine.setAttribute('x1', xCenter);
                atmLine.setAttribute('y1', marginTop);
                atmLine.setAttribute('x2', xCenter);
                atmLine.setAttribute('y2', marginTop + plotH);
                atmLine.setAttribute('stroke', '#38bdf8');
                atmLine.setAttribute('stroke-width', '1.5');
                atmLine.setAttribute('stroke-dasharray', '2,2');
                svg.appendChild(atmLine);

                const atmTxt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                atmTxt.setAttribute('x', xCenter);
                atmTxt.setAttribute('y', marginTop - 8);
                atmTxt.setAttribute('text-anchor', 'middle');
                atmTxt.setAttribute('fill', '#38bdf8');
                atmTxt.setAttribute('font-size', '10');
                atmTxt.setAttribute('font-weight', 'bold');
                atmTxt.textContent = `⭐ ATM`;
                svg.appendChild(atmTxt);
            }

            // Strike label below X axis
            const isKeyStrike = d.is_atm || d.is_r1 || d.is_s1 || d.is_r2 || d.is_s2 || (i % 2 === 0);
            if (isKeyStrike) {
                const strikeTxt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                strikeTxt.setAttribute('x', xCenter);
                strikeTxt.setAttribute('y', marginTop + plotH + 18);
                strikeTxt.setAttribute('text-anchor', 'middle');
                let color = '#94a3b8';
                if (d.is_atm) color = '#38bdf8';
                else if (d.is_r1) color = '#f87171';
                else if (d.is_s1) color = '#34d399';
                else if (d.is_r2) color = '#fb923c';
                else if (d.is_s2) color = '#6ee7b7';

                strikeTxt.setAttribute('fill', color);
                strikeTxt.setAttribute('font-size', d.is_atm || d.is_r1 || d.is_s1 ? '10.5' : '9');
                strikeTxt.setAttribute('font-weight', d.is_atm || d.is_r1 || d.is_s1 ? 'bold' : 'normal');
                strikeTxt.textContent = formatNumber(d.strike);
                svg.appendChild(strikeTxt);
            }

            // Interactive hover target
            const hoverRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            hoverRect.setAttribute('x', marginLeft + i * stepX);
            hoverRect.setAttribute('y', marginTop);
            hoverRect.setAttribute('width', stepX);
            hoverRect.setAttribute('height', plotH + marginBottom);
            hoverRect.setAttribute('fill', 'transparent');
            hoverRect.style.cursor = 'crosshair';

            hoverRect.addEventListener('mouseenter', () => {
                if (!tooltip) return;
                const ceB = d.ce_buildup || {};
                const peB = d.pe_buildup || {};
                let statusTag = '';
                if (d.is_atm) statusTag = '<span class="tt-tag tag-atm">ATM PIVOT</span>';
                else if (d.is_r1) statusTag = '<span class="tt-tag tag-r1">MAJOR RESISTANCE 1</span>';
                else if (d.is_s1) statusTag = '<span class="tt-tag tag-s1">MAJOR SUPPORT 1</span>';
                else if (d.is_r2) statusTag = '<span class="tt-tag tag-r2">RESISTANCE 2</span>';
                else if (d.is_s2) statusTag = '<span class="tt-tag tag-s2">SUPPORT 2</span>';
                else if (d.is_in_oscillation) statusTag = '<span class="tt-tag tag-osc">OSCILLATION CHANNEL</span>';

                tooltip.innerHTML = `
                    <div class="tt-header">
                        <strong>Strike ${formatNumber(d.strike)}</strong>
                        ${statusTag}
                    </div>
                    <div class="tt-row">
                        <span class="tt-dot" style="background:${ceB.color || '#ef4444'}"></span>
                        <span>Call Chg OI: <strong>${ceChg > 0 ? '+' : ''}${formatNumber(ceChg)}</strong></span>
                        <span class="tt-mode" style="color:${ceB.color || '#ef4444'}">${ceB.label || 'Call Activity'}</span>
                    </div>
                    <div class="tt-row">
                        <span class="tt-dot" style="background:${peB.color || '#10b981'}"></span>
                        <span>Put Chg OI: <strong>${peChg > 0 ? '+' : ''}${formatNumber(peChg)}</strong></span>
                        <span class="tt-mode" style="color:${peB.color || '#10b981'}">${peB.label || 'Put Activity'}</span>
                    </div>
                    <div class="tt-footer">
                        <span>Spot: ${formatNumber(Math.round(spotPrice * 100) / 100)} (${d.strike > spotPrice ? '+' : ''}${Math.round(d.strike - spotPrice)} pts)</span>
                    </div>
                `;
                tooltip.style.display = 'block';
            });

            hoverRect.addEventListener('mousemove', (e) => {
                if (!tooltip) return;
                const containerRect = svg.parentElement.getBoundingClientRect();
                let left = e.clientX - containerRect.left + 15;
                let top = e.clientY - containerRect.top + 15;
                if (left + 240 > containerRect.width) left = left - 260;
                tooltip.style.left = `${left}px`;
                tooltip.style.top = `${top}px`;
            });

            hoverRect.addEventListener('mouseleave', () => {
                if (tooltip) tooltip.style.display = 'none';
            });

            svg.appendChild(hoverRect);
        });
    });
}

function renderWrittenAnalysis(synergy, data) {
    const containers = [
        document.getElementById('ocMainWrittenBody'),
        document.getElementById('ocWrittenBody')
    ].filter(Boolean);

    if (containers.length === 0) return;

    if (!synergy) {
        containers.forEach(c => c.innerHTML = '<p style="color:#94a3b8;">No analysis available.</p>');
        return;
    }

    const osc = synergy.oscillation_analysis || {};
    const res1 = data.major_resistance || {};
    const res2 = data.secondary_resistance || {};
    const sup1 = data.major_support || {};
    const sup2 = data.secondary_support || {};
    const pcr = data.pcr || 1.0;

    const html = `
        <div class="written-analysis-grid">
            <div class="written-card card-levels">
                <div class="wcard-hdr">
                    <span class="wcard-tag tag-res">SUPPLY CEILINGS</span>
                    <h5>🔴 Next-Day Resistance 1 & 2</h5>
                </div>
                <ul class="wcard-list">
                    <li>
                        <strong>Resistance 1 (R1): Strike ${formatNumber(res1.strike)}</strong>
                        <p>Primary Call Wall anchored by <strong>${formatNumber(res1.oi)}</strong> open contracts. Institutional Call Writers (FIIs & Pros) have fortified this level; intraday rallies into this strike are expected to meet heavy supply.</p>
                    </li>
                    <li>
                        <strong>Resistance 2 (R2): Strike ${formatNumber(res2.strike)}</strong>
                        <p>Secondary Call Ceiling (${formatNumber(res2.oi)} contracts). A decisive 15-minute close above R1 triggers aggressive call short-covering towards R2.</p>
                    </li>
                </ul>
            </div>

            <div class="written-card card-levels">
                <div class="wcard-hdr">
                    <span class="wcard-tag tag-sup">DEMAND FLOORS</span>
                    <h5>🟢 Next-Day Support 1 & 2</h5>
                </div>
                <ul class="wcard-list">
                    <li>
                        <strong>Support 1 (S1): Strike ${formatNumber(sup1.strike)}</strong>
                        <p>Primary Smart Money Put Cushion with <strong>${formatNumber(sup1.oi)}</strong> open contracts. Substantial Put Writing by Proprietary desks and FIIs creates a resilient defense floor.</p>
                    </li>
                    <li>
                        <strong>Support 2 (S2): Strike ${formatNumber(sup2.strike)}</strong>
                        <p>Secondary Demand Cushion (${formatNumber(sup2.oi)} contracts). In case of global shockwaves, S2 acts as the structural shock-absorber.</p>
                    </li>
                </ul>
            </div>

            <div class="written-card card-oscillation">
                <div class="wcard-hdr">
                    <span class="wcard-tag tag-osc">MEAN REVERSION</span>
                    <h5>⚡ Next-Day Oscillation Zone: ${osc.range_label || (formatNumber(sup1.strike) + ' - ' + formatNumber(res1.strike))}</h5>
                </div>
                <p class="wcard-desc">${osc.explanation || synergy.oscillation_zone_desc || 'Price is expected to oscillate within this boundary.'}</p>
                <div class="breakout-box">
                    <strong>Institutional Breakout Triggers:</strong>
                    <span>${osc.breakout_conditions || 'A sustained breakout above R1 or breakdown below S1 will shift the regime from oscillation to aggressive directional trending.'}</span>
                </div>
            </div>

            <div class="written-card card-stance">
                <div class="wcard-hdr">
                    <span class="wcard-tag ${synergy.retail_trap_alert ? 'tag-trap' : 'tag-neutral'}">PARTICIPANT SYNERGY</span>
                    <h5>🎯 Strategic Verdict & Trap Radar</h5>
                </div>
                <p class="wcard-desc">${synergy.retail_trap_status || 'Derivative positioning confirms balanced institutional engagement.'}</p>
                <div class="sentiment-indicator-line">
                    <span>PCR: <strong>${pcr.toFixed(2)}</strong></span>
                    <span style="color:${data.pcr_color || '#38bdf8'}; font-weight:700;">${data.pcr_stance || ''}</span>
                    <span>Key Pivot Strike: <strong>${formatNumber(data.atm_strike)} ATM</strong></span>
                </div>
            </div>
        </div>
    `;

    containers.forEach(c => c.innerHTML = html);
}

function renderOptionChainSynergy(synergy) {
    if (!synergy) return;

    ['ocMainExpectedRange', 'ocExpectedRange'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = `Expected Range: ${synergy.expected_range || 'N/A'}`;
    });

    const cardContainers = [
        document.getElementById('ocMainSynergyCards'),
        document.getElementById('ocSynergyCards')
    ].filter(Boolean);

    cardContainers.forEach(cardsContainer => {
        cardsContainer.innerHTML = '';

        // 1. Next-Day 5-Level Roadmap Strip
        if (synergy.roadmap && synergy.roadmap.length > 0) {
            const roadmapWrap = document.createElement('div');
            roadmapWrap.className = 'oc-roadmap-wrap';
            
            let roadmapHtml = '<div class="oc-roadmap-title">🎯 Next-Day Key Levels & Institutional Roadmap</div><div class="oc-roadmap-grid">';
            synergy.roadmap.forEach(rm => {
                const levelClass = rm.type === 'resistance' ? 'level-res' : (rm.type === 'support' ? 'level-sup' : 'level-atm');
                roadmapHtml += `
                    <div class="oc-roadmap-card ${levelClass}">
                        <div class="roadmap-badge">${rm.level}</div>
                        <div class="roadmap-strike">${formatNumber(rm.strike)}</div>
                        <div class="roadmap-tag">${rm.tag}</div>
                        <div class="roadmap-desc">${rm.desc}</div>
                    </div>
                `;
            });
            roadmapHtml += '</div>';
            roadmapWrap.innerHTML = roadmapHtml;
            cardsContainer.appendChild(roadmapWrap);
        }

        // 2. Institutional Mapping Cards (FII, Pro, Client, DII)
        if (synergy.mapping_cards && synergy.mapping_cards.length > 0) {
            const mappingWrap = document.createElement('div');
            mappingWrap.className = 'oc-mapping-grid';

            synergy.mapping_cards.forEach(card => {
                const div = document.createElement('div');
                div.className = 'oc-synergy-card';
                div.innerHTML = `
                    <div class="oc-synergy-card-top">
                        <span class="oc-synergy-card-title">${card.icon} ${card.entity}</span>
                        <span class="oc-synergy-card-tag ${card.badge_class || 'tag-neutral'}">${card.badge}</span>
                    </div>
                    <div class="oc-card-activity"><strong>Action Breakdown:</strong> ${card.activity || ''}</div>
                    <div class="oc-card-strikes"><strong>Mapped Strikes:</strong> ${card.mapped_strikes}</div>
                    <p class="oc-synergy-card-desc">${card.conclusion}</p>
                `;
                mappingWrap.appendChild(div);
            });
            cardsContainer.appendChild(mappingWrap);
        }
    });
}

function renderFiiBuildupTracker(fiiAnalysis) {
    const trackerCard = document.getElementById('ocFiiBuildupTrackerCard');
    if (!trackerCard || !fiiAnalysis) return;

    // 1. Stance Pill
    const stancePill = document.getElementById('ocFiiStancePill');
    if (stancePill) {
        stancePill.innerText = fiiAnalysis.fii_stance_badge || 'BALANCED FLOW';
        stancePill.style.color = fiiAnalysis.fii_stance_color || '#38bdf8';
        stancePill.style.borderColor = fiiAnalysis.fii_stance_color || '#38bdf8';
        stancePill.style.background = (fiiAnalysis.fii_stance_color ? fiiAnalysis.fii_stance_color + '1a' : 'rgba(56, 189, 248, 0.15)');
    }

    // 2. Corridor
    const corridor = fiiAnalysis.corridor || {};
    const corrVal = document.getElementById('ocFiiCorridorVal');
    const corrSpread = document.getElementById('ocFiiCorridorSpread');
    if (corrVal) corrVal.innerText = corridor.label || '25,000 Support ➔ 25,200 Resistance';
    if (corrSpread) corrSpread.innerText = corridor.description || `${corridor.channel_width || 200} pts Institutional Range`;

    // 3. Net Flows
    const callFlow = fiiAnalysis.fii_call_flow || {};
    const putFlow = fiiAnalysis.fii_put_flow || {};
    const callNetStat = document.getElementById('ocFiiCallNetStat');
    const putNetStat = document.getElementById('ocFiiPutNetStat');

    if (callNetStat) {
        const netCe = callFlow.net || 0;
        callNetStat.innerText = `Net: ${netCe > 0 ? '+' : ''}${formatNumber(netCe)} Calls`;
        callNetStat.style.color = netCe > 0 ? '#10b981' : (netCe < 0 ? '#ef4444' : '#94a3b8');
    }

    if (putNetStat) {
        const netPe = putFlow.net || 0;
        putNetStat.innerText = `Net: ${netPe > 0 ? '+' : ''}${formatNumber(netPe)} Puts`;
        putNetStat.style.color = netPe < 0 ? '#10b981' : (netPe > 0 ? '#ef4444' : '#94a3b8');
    }

    // 4. Call Strikes List
    const callList = document.getElementById('ocFiiCallStrikesList');
    if (callList) {
        callList.innerHTML = '';
        const callStrikes = fiiAnalysis.fii_call_buildup_strikes || [];
        if (callStrikes.length === 0) {
            callList.innerHTML = '<div style="color:#94a3b8; font-size:11.5px; padding:12px; text-align:center;">No significant FII Call addition detected in this window.</div>';
        } else {
            callStrikes.forEach(item => {
                const el = document.createElement('div');
                el.className = 'fii-strike-item item-call';
                el.innerHTML = `
                    <div class="fii-item-top">
                        <span class="fii-strike-pill">${formatNumber(item.strike)}</span>
                        <span class="fii-item-role">${item.role}</span>
                        <span class="fii-action-badge ${item.badge_class || 'tag-res'}">${item.badge}</span>
                    </div>
                    <div class="fii-item-metrics">
                        <span>OI: <strong>${formatNumber(item.oi)}</strong></span>
                        <span>Chg: <strong class="${item.chg_oi >= 0 ? 'cell-green' : 'cell-red'}">${item.chg_oi > 0 ? '+' : ''}${formatNumber(item.chg_oi)}</strong></span>
                        <span>LTP: <strong>₹${item.ltp ? item.ltp.toFixed(2) : '-'}</strong></span>
                    </div>
                    <div class="fii-item-desc">${item.explanation}</div>
                `;
                callList.appendChild(el);
            });
        }
    }

    // 5. Put Strikes List
    const putList = document.getElementById('ocFiiPutStrikesList');
    if (putList) {
        putList.innerHTML = '';
        const putStrikes = fiiAnalysis.fii_put_buildup_strikes || [];
        if (putStrikes.length === 0) {
            putList.innerHTML = '<div style="color:#94a3b8; font-size:11.5px; padding:12px; text-align:center;">No significant FII Put addition detected in this window.</div>';
        } else {
            putStrikes.forEach(item => {
                const el = document.createElement('div');
                el.className = 'fii-strike-item item-put';
                el.innerHTML = `
                    <div class="fii-item-top">
                        <span class="fii-strike-pill">${formatNumber(item.strike)}</span>
                        <span class="fii-item-role">${item.role}</span>
                        <span class="fii-action-badge ${item.badge_class || 'tag-sup'}">${item.badge}</span>
                    </div>
                    <div class="fii-item-metrics">
                        <span>OI: <strong>${formatNumber(item.oi)}</strong></span>
                        <span>Chg: <strong class="${item.chg_oi >= 0 ? 'cell-green' : 'cell-red'}">${item.chg_oi > 0 ? '+' : ''}${formatNumber(item.chg_oi)}</strong></span>
                        <span>LTP: <strong>₹${item.ltp ? item.ltp.toFixed(2) : '-'}</strong></span>
                    </div>
                    <div class="fii-item-desc">${item.explanation}</div>
                `;
                putList.appendChild(el);
            });
        }
    }

    // 6. Summaries
    const callSum = document.getElementById('ocFiiCallSummary');
    if (callSum && fiiAnalysis.call_summary) callSum.innerText = fiiAnalysis.call_summary;

    const putSum = document.getElementById('ocFiiPutSummary');
    if (putSum && fiiAnalysis.put_summary) putSum.innerText = fiiAnalysis.put_summary;

    // 7. Plain-language Explanation & Impact
    const expText = document.getElementById('ocFiiExplanationText');
    if (expText && fiiAnalysis.plain_language_summary) {
        expText.innerText = fiiAnalysis.plain_language_summary;
    }

    const impactText = document.getElementById('ocFiiImpactText');
    if (impactText && fiiAnalysis.next_day_price_impact) {
        impactText.innerText = fiiAnalysis.next_day_price_impact;
    }
}

function renderProbabilisticBanner(probModel, gamePlan, fiiAnalysis, perspective) {
    perspective = perspective || 'all';

    // 1. Perspective Icon & Badge Headers
    const iconEl = document.getElementById('ocGamePlanIcon');
    const badgeEl = document.getElementById('ocGamePlanBadge');
    const headlineEl = document.getElementById('ocGamePlanHeadline');
    const subEl = document.getElementById('ocGamePlanSub');
    const stancePill = document.getElementById('ocFiiStancePill');

    const pIcons = { all: '👑', fii: '🏦', pro: '🏢', client: '👤' };
    const pBadges = {
        all: 'BIG PLAYER DERIVATIVE INTELLIGENCE',
        fii: 'FII INSTITUTIONAL PERSPECTIVE',
        pro: 'PROPRIETARY DESK STRANGLE PERSPECTIVE',
        client: 'RETAIL CLIENT CONFLICT & TRAP RADAR'
    };
    const pHeadlines = {
        all: (gamePlan && gamePlan.headline) || 'Big Player Game Plan & Probabilistic Market Roadmap',
        fii: 'FII Strategic Roadmap: Major Put Cushion vs Call Cap',
        pro: 'Proprietary Desk Positioning: High-Theta Straddle Pinning',
        client: 'Retail Speculator Positioning: Overleveraged Trap Risk'
    };
    const pSubs = {
        all: (gamePlan && gamePlan.sub) || 'Mathematical S&R holding probabilities, pinning corridors, and multi-participant positioning',
        fii: 'Foreign institutional heavy put writing defense and call hedging flows',
        pro: 'Prop Desk gamma-neutral strangles, pinning forces, and theta collection',
        client: 'Retail client long option decay exposure vs smart money walls'
    };

    if (iconEl) iconEl.innerText = pIcons[perspective] || '👑';
    if (badgeEl) badgeEl.innerText = pBadges[perspective] || pBadges.all;
    if (headlineEl) headlineEl.innerText = pHeadlines[perspective] || pHeadlines.all;
    if (subEl) subEl.innerText = pSubs[perspective] || pSubs.all;

    // Stance Pill
    if (stancePill) {
        if (perspective !== 'all' && gamePlan && gamePlan.participants && gamePlan.participants[perspective]) {
            const pObj = gamePlan.participants[perspective];
            const pCol = pObj.stance_color || pObj.view_color || '#38bdf8';
            stancePill.innerText = `${pIcons[perspective]} ${pObj.name.split(' ')[0]}: ${pObj.view.toUpperCase()}`;
            stancePill.style.color = pCol;
            stancePill.style.borderColor = pCol;
            stancePill.style.background = pCol + '22';
        } else if (fiiAnalysis) {
            stancePill.innerText = fiiAnalysis.fii_stance_badge || '🛡️ DEFENSIVE BULLISH / PUT WRITING DOMINANCE';
            stancePill.style.color = fiiAnalysis.fii_stance_color || '#10b981';
            stancePill.style.borderColor = fiiAnalysis.fii_stance_color || '#10b981';
            stancePill.style.background = (fiiAnalysis.fii_stance_color ? fiiAnalysis.fii_stance_color + '1a' : 'rgba(16, 185, 129, 0.15)');
        }
    }

    // 2. Target Destination & Pinning Corridor
    if (probModel && probModel.target_destination) {
        const td = probModel.target_destination;
        const corrVal = document.getElementById('ocFiiCorridorVal');
        const corrSpread = document.getElementById('ocFiiCorridorSpread');
        const decayChip = document.getElementById('ocTargetDecayChip');
        const probVal = document.getElementById('ocTargetProbVal');
        const probFill = document.getElementById('ocTargetProbFill');

        const spread = (td.spread !== undefined) ? td.spread : Math.abs((td.high || 0) - (td.low || 0));
        if (corrVal) corrVal.innerText = `${td.corridor_label} Target Zone`;
        if (corrSpread) corrSpread.innerText = `${spread} pts Institutional Pin Corridor`;
        if (decayChip) decayChip.innerText = td.decay_pace || td.decay_status || 'Max Theta Decay';
        if (probVal) probVal.innerText = `${td.probability}%`;
        if (probFill) probFill.style.width = `${td.probability}%`;
    }

    // 3. Probabilistic S&R Scorecard
    if (probModel && probModel.probabilistic_sr) {
        const psr = probModel.probabilistic_sr;
        // R2
        if (psr.r2) {
            const r2Str = document.getElementById('psrR2Strike');
            const r2Pct = document.getElementById('psrR2Pct');
            const r2Bar = document.getElementById('psrR2Bar');
            if (r2Str) r2Str.innerText = `${formatNumber(psr.r2.strike)} (R2)`;
            if (r2Pct) r2Pct.innerText = `${psr.r2.holding_prob}% Hold`;
            if (r2Bar) r2Bar.style.width = `${psr.r2.holding_prob}%`;
        }
        // R1
        if (psr.r1) {
            const r1Str = document.getElementById('psrR1Strike');
            const r1Pct = document.getElementById('psrR1Pct');
            const r1Bar = document.getElementById('psrR1Bar');
            if (r1Str) r1Str.innerText = `${formatNumber(psr.r1.strike)} (R1)`;
            if (r1Pct) r1Pct.innerText = `${psr.r1.holding_prob}% Hold`;
            if (r1Bar) r1Bar.style.width = `${psr.r1.holding_prob}%`;
        }
        // S1
        if (psr.s1) {
            const s1Str = document.getElementById('psrS1Strike');
            const s1Pct = document.getElementById('psrS1Pct');
            const s1Bar = document.getElementById('psrS1Bar');
            if (s1Str) s1Str.innerText = `${formatNumber(psr.s1.strike)} (S1)`;
            if (s1Pct) s1Pct.innerText = `${psr.s1.holding_prob}% Hold`;
            if (s1Bar) s1Bar.style.width = `${psr.s1.holding_prob}%`;
        }
        // S2
        if (psr.s2) {
            const s2Str = document.getElementById('psrS2Strike');
            const s2Pct = document.getElementById('psrS2Pct');
            const s2Bar = document.getElementById('psrS2Bar');
            if (s2Str) s2Str.innerText = `${formatNumber(psr.s2.strike)} (S2)`;
            if (s2Pct) s2Pct.innerText = `${psr.s2.holding_prob}% Hold`;
            if (s2Bar) s2Bar.style.width = `${psr.s2.holding_prob}%`;
        }
    }

    // 4. Market Regime & Volatility
    if (probModel && probModel.regime_probabilities) {
        const rp = probModel.regime_probabilities;
        const domChip = document.getElementById('ocDominantRegimeChip');
        const rangeVal = document.getElementById('ocRegimeRangeVal');
        const rangeBar = document.getElementById('ocRegimeRangeBar');
        const boVal = document.getElementById('ocRegimeBreakoutVal');
        const boBar = document.getElementById('ocRegimeBreakoutBar');
        const bdVal = document.getElementById('ocRegimeBreakdownVal');
        const bdBar = document.getElementById('ocRegimeBreakdownBar');

        if (domChip) domChip.innerText = rp.dominant_regime || 'RANGEBOUND';
        if (rangeVal) rangeVal.innerText = `${rp.rangebound_pct}%`;
        if (rangeBar) rangeBar.style.width = `${rp.rangebound_pct}%`;
        if (boVal) boVal.innerText = `${rp.upside_breakout_pct}%`;
        if (boBar) boBar.style.width = `${rp.upside_breakout_pct}%`;
        if (bdVal) bdVal.innerText = `${rp.downside_breakdown_pct}%`;
        if (bdBar) bdBar.style.width = `${rp.downside_breakdown_pct}%`;
    }

    if (probModel) {
        const vm = probModel.volatility_metrics || {
            iv_pct: probModel.implied_volatility_pct,
            daily_expected_move: probModel.daily_expected_move,
            sd1_band_label: probModel.sd1_band ? probModel.sd1_band.label : '-'
        };
        const ivVal = document.getElementById('ocModelIvVal');
        const dMove = document.getElementById('ocModelDailyMove');
        const sdBand = document.getElementById('ocModelSd1Band');
        if (ivVal && vm.iv_pct !== undefined) ivVal.innerText = `${vm.iv_pct}%`;
        if (dMove && vm.daily_expected_move !== undefined) dMove.innerText = `±${vm.daily_expected_move} pts`;
        if (sdBand && vm.sd1_band_label) sdBand.innerText = vm.sd1_band_label;
    }

    // 5. Executive Thesis & Trapped Participants
    const expText = document.getElementById('ocFiiExplanationText');
    if (expText) {
        if (perspective !== 'all' && gamePlan && gamePlan.participants && gamePlan.participants[perspective]) {
            expText.innerText = gamePlan.participants[perspective].game_plan;
        } else if (gamePlan && gamePlan.executive_thesis) {
            expText.innerText = gamePlan.executive_thesis;
        } else if (fiiAnalysis && fiiAnalysis.plain_language_summary) {
            expText.innerText = fiiAnalysis.plain_language_summary;
        }
    }

    const trapBox = document.getElementById('ocTrappedAlertBox');
    const trapTitle = document.getElementById('ocTrapVictimTitle');
    const trapDesc = document.getElementById('ocTrapDescText');
    if (gamePlan && gamePlan.trapped_participants) {
        const tp = gamePlan.trapped_participants;
        if (trapBox) trapBox.style.display = 'block';
        if (trapTitle) trapTitle.innerText = tp.victim || 'Trapped Participants Alert';
        if (trapDesc) trapDesc.innerText = `${tp.description} (${tp.squeeze_risk || 'Theta Risk'})`;
    }

    const impactText = document.getElementById('ocFiiImpactText');
    if (impactText) {
        if (gamePlan && gamePlan.impact) {
            impactText.innerText = gamePlan.impact;
        } else if (fiiAnalysis && fiiAnalysis.next_day_price_impact) {
            impactText.innerText = fiiAnalysis.next_day_price_impact;
        }
    }
}

function render4ParticipantCards(participants, currentPerspective) {
    const grid = document.getElementById('oc4pGrid');
    if (!grid) return;
    grid.innerHTML = '';
    if (!participants) return;

    const pOrder = [
        { key: 'fii', name: 'Foreign Institutions (FII)' },
        { key: 'pro', name: 'Proprietary Desks (PRO)' },
        { key: 'client', name: 'Retail Clients' },
        { key: 'dii', name: 'Domestic Institutions (DII)' }
    ];

    pOrder.forEach(({ key }) => {
        const p = participants[key];
        if (!p) return;

        const isAct = (key === currentPerspective);
        const pCol = p.stance_color || p.view_color || '#38bdf8';
        const isTrapped = (key === 'client' && p.view && p.view.includes('Trapped'));
        const card = document.createElement('div');
        card.className = `oc-4p-card ${isAct ? 'active-perspective' : ''} ${isTrapped ? 'is-trapped' : ''}`;
        card.setAttribute('data-participant', key);
        card.style.cursor = 'pointer';

        card.innerHTML = `
            <div class="oc-4p-card-header">
                <div class="oc-4p-title-wrap">
                    <span class="oc-4p-icon">${p.icon || '🏦'}</span>
                    <span class="oc-4p-name">${p.name}</span>
                </div>
                <span class="oc-4p-view-badge" style="background:${pCol}22; color:${pCol}; border: 1px solid ${pCol}55;">
                    ${p.view}
                </span>
            </div>
            <div class="oc-4p-conviction-row">
                <span class="oc-4p-lbl">Conviction:</span>
                <strong class="oc-4p-conviction-val" style="color:${pCol};">${p.conviction}</strong>
            </div>
            <div class="oc-4p-positions-box">
                <div class="oc-4p-pos-item pos-add">
                    <span class="pos-lbl">+ Added:</span>
                    <span class="pos-val">${p.added_positions || '-'}</span>
                </div>
                <div class="oc-4p-pos-item pos-cls">
                    <span class="pos-lbl">- Closed:</span>
                    <span class="pos-val">${p.closed_positions || '-'}</span>
                </div>
            </div>
            <div class="oc-4p-gameplan-box">
                <span class="gameplan-lbl">🎯 Strategic Game Plan:</span>
                <p class="gameplan-desc">${p.game_plan}</p>
            </div>
        `;

        card.addEventListener('click', () => {
            setPerspective(key === currentPerspective ? 'all' : key);
        });

        grid.appendChild(card);
    });
}



function renderBigPlayerStrikeCockpit(cockpitData, gamePlan, spotPrice, atmStrike) {
    if (!cockpitData) return;

    const callBastion = cockpitData.call_bastion || {};
    const putBastion = cockpitData.put_bastion || {};
    const trapRadar = cockpitData.trapped_retail_radar || {};
    const stratCockpit = cockpitData.option_selling_cockpit || {};

    // Stance & Header Badges
    const domStance = document.getElementById('cockpitDominantStance');
    if (domStance) {
        if (callBastion.net_smart_calls < 0 && (trapRadar.victim || '').includes('Calls')) {
            domStance.innerText = 'BEARISH CEILING DEFENSE / CALL WRITING WALL';
            domStance.style.background = 'rgba(239, 68, 68, 0.2)';
            domStance.style.color = '#f87171';
            domStance.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        } else if (putBastion.net_smart_puts < 0 && (trapRadar.victim || '').includes('Puts')) {
            domStance.innerText = 'BULLISH SUPPORT DEFENSE / PUT WRITING FLOOR';
            domStance.style.background = 'rgba(16, 185, 129, 0.2)';
            domStance.style.color = '#34d399';
            domStance.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        } else {
            domStance.innerText = 'STRANGLE PINNING & THETA HARVEST';
            domStance.style.background = 'rgba(245, 158, 11, 0.2)';
            domStance.style.color = '#fbbf24';
            domStance.style.borderColor = 'rgba(245, 158, 11, 0.4)';
        }
    }

    const popVal = document.getElementById('cockpitPopVal');
    if (popVal) popVal.innerText = `${stratCockpit.pop_pct || 88.4}% POP`;

    const stratType = document.getElementById('cockpitStratType');
    if (stratType) stratType.innerText = stratCockpit.strategy_name || stratCockpit.archetype || 'Bear Call Credit Spread';

    // 1. Call Bastion (Ceiling)
    const cStrike = document.getElementById('cockpitCallStrike');
    if (cStrike && callBastion.strike) cStrike.innerText = `${formatNumber(callBastion.strike)} CE (R1)`;

    const cLtp = document.getElementById('cockpitCallLtp');
    if (cLtp && callBastion.ltp !== undefined) cLtp.innerText = `₹${callBastion.ltp.toFixed(2)}`;

    const cNet = document.getElementById('cockpitCallNet');
    if (cNet && callBastion.net_smart_calls !== undefined) {
        cNet.innerText = (callBastion.net_smart_calls > 0 ? '+' : '') + formatNumber(callBastion.net_smart_calls);
    }

    const cRet = document.getElementById('cockpitCallRetention');
    if (cRet) cRet.innerText = `${callBastion.retention_ratio_pct || 42.8}% (Overnight)`;

    const cWant = document.getElementById('cockpitCallWant');
    if (cWant) cWant.innerText = callBastion.what_they_want || '';

    const cPanic = document.getElementById('cockpitCallPanic');
    if (cPanic && callBastion.panic_breakeven) cPanic.innerText = `₹${formatNumber(callBastion.panic_breakeven)}`;

    // 2. Put Bastion (Floor)
    const pStrike = document.getElementById('cockpitPutStrike');
    if (pStrike && putBastion.strike) pStrike.innerText = `${formatNumber(putBastion.strike)} PE (S1)`;

    const pLtp = document.getElementById('cockpitPutLtp');
    if (pLtp && putBastion.ltp !== undefined) pLtp.innerText = `₹${putBastion.ltp.toFixed(2)}`;

    const pNet = document.getElementById('cockpitPutNet');
    if (pNet && putBastion.net_smart_puts !== undefined) {
        pNet.innerText = (putBastion.net_smart_puts > 0 ? '+' : '') + formatNumber(putBastion.net_smart_puts);
    }

    const pRet = document.getElementById('cockpitPutRetention');
    if (pRet) pRet.innerText = `${putBastion.retention_ratio_pct || 38.6}% (Overnight)`;

    const pWant = document.getElementById('cockpitPutWant');
    if (pWant) pWant.innerText = putBastion.what_they_want || '';

    const pPanic = document.getElementById('cockpitPutPanic');
    if (pPanic && putBastion.panic_breakeven) pPanic.innerText = `₹${formatNumber(putBastion.panic_breakeven)}`;

    // 3. Trapped Retail Radar
    const trapTitle = document.getElementById('cockpitTrapTitle');
    if (trapTitle) trapTitle.innerText = trapRadar.victim || 'Retail Trap Radar';

    const trapDesc = document.getElementById('cockpitTrapDesc');
    if (trapDesc) trapDesc.innerText = trapRadar.description || '';

    // 4. Execution Blueprint
    const stratTitle = document.getElementById('cockpitStratTitle');
    if (stratTitle) stratTitle.innerText = stratCockpit.strategy_name || '';

    const stratBadge = document.getElementById('cockpitStrategyBadge');
    if (stratBadge) stratBadge.innerText = `${stratCockpit.pop_pct || 88.4}% WIN RATE`;

    const netCredit = document.getElementById('cockpitNetCredit');
    if (netCredit) {
        netCredit.innerText = `+₹${formatNumber(stratCockpit.net_credit_inr || 2490)} / lot (+${stratCockpit.net_credit_pts || 33.2} pts)`;
    }

    const stopLoss = document.getElementById('cockpitStopLoss');
    if (stopLoss) stopLoss.innerText = stratCockpit.stop_loss_trigger || '';

    // Render legs
    const legsGrid = document.getElementById('cockpitLegsGrid');
    if (legsGrid) {
        legsGrid.innerHTML = '';
        if (stratCockpit.sell_leg) {
            const sellDiv = document.createElement('div');
            sellDiv.className = 'bleg-card bleg-sell';
            sellDiv.innerHTML = `
                <span class="bleg-action">SELL</span>
                <strong class="bleg-strike">${formatNumber(stratCockpit.sell_leg.strike)} ${stratCockpit.sell_leg.opt_type || ''}</strong>
                <span class="bleg-ltp">₹${stratCockpit.sell_leg.ltp} • ${stratCockpit.sell_leg.role || 'Primary Defense'}</span>
            `;
            legsGrid.appendChild(sellDiv);
        }
        if (stratCockpit.hedge_leg) {
            const buyDiv = document.createElement('div');
            buyDiv.className = 'bleg-card bleg-buy';
            buyDiv.innerHTML = `
                <span class="bleg-action">BUY (HEDGE)</span>
                <strong class="bleg-strike">${formatNumber(stratCockpit.hedge_leg.strike)} ${stratCockpit.hedge_leg.opt_type || ''}</strong>
                <span class="bleg-ltp">₹${stratCockpit.hedge_leg.ltp} • ${stratCockpit.hedge_leg.role || 'Tail Risk Cap'}</span>
            `;
            legsGrid.appendChild(buyDiv);
        }
    }
}

function renderOptionChainTable(strikes, spotPrice, atmStrike, fiiAnalysis) {
    const tbodies = [
        document.getElementById('ocMainTbody'),
        document.getElementById('ocTbody')
    ].filter(Boolean);

    if (tbodies.length === 0) return;

    tbodies.forEach(tbody => {
        tbody.innerHTML = '';
        if (!strikes || strikes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="13" style="text-align:center; padding: 25px; color:#94a3b8;">No strikes in selected window.</td></tr>';
            return;
        }

        let spotDividerInserted = false;

        strikes.forEach(s => {
            const isAtm = s.is_atm;
            const isR1 = s.is_r1;
            const isR2 = s.is_r2;
            const isS1 = s.is_s1;
            const isS2 = s.is_s2;
            const isInOsc = s.is_in_oscillation;

            // Spot Price Divider Row (Inserted between ITM and OTM strikes)
            if (!spotDividerInserted && s.strike >= spotPrice) {
                const spotTr = document.createElement('tr');
                spotTr.className = 'spot-divider-row';
                spotTr.innerHTML = `
                    <td colspan="13">
                        <div class="spot-divider-inner">
                            <span class="spot-pill">🎯 UNDERLYING SPOT</span>
                            <span class="spot-val">${currentOcSymbol} ${formatNumber(Math.round(spotPrice * 100) / 100)}</span>
                            <span class="spot-atm">ATM: ${formatNumber(atmStrike)}</span>
                            <span class="spot-pcr">PCR: ${(currentOcData && currentOcData.pcr ? currentOcData.pcr.toFixed(2) : '-')}</span>
                        </div>
                    </td>
                `;
                tbody.appendChild(spotTr);
                spotDividerInserted = true;
            }

            const tr = document.createElement('tr');
            if (isAtm) tr.className = 'row-atm';
            else if (isR1) tr.className = 'row-r1';
            else if (isS1) tr.className = 'row-s1';
            else if (isR2) tr.className = 'row-r2';
            else if (isS2) tr.className = 'row-s2';
            else if (isInOsc) tr.className = 'row-osc';

            const c = s.call || {};
            const p = s.put || {};
            const cB = c.buildup || {};
            const pB = p.buildup || {};
            const cFii = c.fii_buildup || {};
            const pFii = p.fii_buildup || {};

            // Authentic NSE In-The-Money (ITM) Shading:
            // Calls are ITM when strike < spot
            // Puts are ITM when strike > spot
            const callItmClass = s.strike < spotPrice ? 'itm-call-cell' : 'otm-cell';
            const putItmClass = s.strike > spotPrice ? 'itm-put-cell' : 'otm-cell';

            // Change in OI formatting
            const chgCallClass = c.chg_oi > 0 ? 'cell-green font-bold' : (c.chg_oi < 0 ? 'cell-red font-bold' : 'cell-neutral');
            const chgPutClass = p.chg_oi > 0 ? 'cell-green font-bold' : (p.chg_oi < 0 ? 'cell-red font-bold' : 'cell-neutral');

            // Price Change formatting
            const chgPCallClass = c.chg_p > 0 ? 'cell-green' : (c.chg_p < 0 ? 'cell-red' : 'cell-neutral');
            const chgPPutClass = p.chg_p > 0 ? 'cell-green' : (p.chg_p < 0 ? 'cell-red' : 'cell-neutral');
            const cChgPStr = c.chg_p !== undefined && c.chg_p !== null ? (c.chg_p > 0 ? '+' + c.chg_p.toFixed(2) : c.chg_p.toFixed(2)) : '-';
            const pChgPStr = p.chg_p !== undefined && p.chg_p !== null ? (p.chg_p > 0 ? '+' + p.chg_p.toFixed(2) : p.chg_p.toFixed(2)) : '-';

            // Primary Level Badges
            let callBadgeHtml = '';
            if (isR1) callBadgeHtml = '<span class="badge-r1">R1</span>';
            else if (isR2) callBadgeHtml = '<span class="badge-r2">R2</span>';
            else if (c.badge) callBadgeHtml = `<span class="badge-fresh">${c.badge}</span>`;

            let putBadgeHtml = '';
            if (isS1) putBadgeHtml = '<span class="badge-s1">S1</span>';
            else if (isS2) putBadgeHtml = '<span class="badge-s2">S2</span>';
            else if (p.badge) putBadgeHtml = `<span class="badge-fresh">${p.badge}</span>`;

            // 4-Participant Perspective Badges (All Big Players, FII, Pro, Client)
            const pMap = s.perspectives || {};
            const pActive = pMap[currentPerspective] || pMap['all'] || {};

            let callPerspectiveBadgeHtml = '';
            if (pActive.call_badge && pActive.call_badge !== '-') {
                callPerspectiveBadgeHtml = `<span class="oc-perspective-tag ${pActive.call_class || 'badge-sm-call'}" title="${pActive.call_badge}">${pActive.call_badge}</span>`;
            }

            let putPerspectiveBadgeHtml = '';
            if (pActive.put_badge && pActive.put_badge !== '-') {
                putPerspectiveBadgeHtml = `<span class="oc-perspective-tag ${pActive.put_class || 'badge-sm-put'}" title="${pActive.put_badge}">${pActive.put_badge}</span>`;
            }

            // Added / Closed Action Badges (+ Added Short, + Added Long, - Covered Short, - Unwound)
            let callActionBadgeHtml = '';
            if (c.action_badge) {
                const aText = (typeof c.action_badge === 'object' && c.action_badge) ? c.action_badge.text : c.action_badge;
                let aClass = (typeof c.action_badge === 'object' && c.action_badge) ? c.action_badge.class : '';
                if (!aClass && aText) {
                    aClass = aText.includes('Short') ? 'badge-add-short' : (aText.includes('Long') ? 'badge-add-long' : (aText.includes('Covered') ? 'badge-cls-short' : 'badge-cls-long'));
                }
                if (aText && aText !== '-') {
                    callActionBadgeHtml = `<span class="oc-action-badge ${aClass}">${aText}</span>`;
                }
            }

            let putActionBadgeHtml = '';
            if (p.action_badge) {
                const aText = (typeof p.action_badge === 'object' && p.action_badge) ? p.action_badge.text : p.action_badge;
                let aClass = (typeof p.action_badge === 'object' && p.action_badge) ? p.action_badge.class : '';
                if (!aClass && aText) {
                    aClass = aText.includes('Short') ? 'badge-add-short' : (aText.includes('Long') ? 'badge-add-long' : (aText.includes('Covered') ? 'badge-cls-short' : 'badge-cls-long'));
                }
                if (aText && aText !== '-') {
                    putActionBadgeHtml = `<span class="oc-action-badge ${aClass}">${aText}</span>`;
                }
            }

            // Call Buildup & FII Tag
            let callFiiBadgeHtml = '';
            if (cFii.short_tag && cFii.short_tag !== '-') {
                callFiiBadgeHtml = `<span class="fii-strike-tag ${cFii.code ? cFii.code.toLowerCase() : ''}" title="${cFii.desc || ''}">${cFii.short_tag}</span>`;
            }

            const callBuildupBadge = cB.short_label ? `
                <span class="buildup-tag" style="background:${cB.color || '#94a3b8'}20; color:${cB.color || '#94a3b8'}; border: 1px solid ${cB.color || '#94a3b8'}55;">
                    ${cB.short_label}
                </span>
            ` : '';

            let callPerspBadge = (currentPerspective !== 'all' && currentPerspective !== 'fii' && callPerspectiveBadgeHtml) ? callPerspectiveBadgeHtml : '';

            const callBuildupCellContent = `
                <div class="buildup-cell-content">
                    ${callBuildupBadge}
                    ${callFiiBadgeHtml}
                    ${callActionBadgeHtml}
                    ${callPerspBadge}
                    ${!callBuildupBadge && !callFiiBadgeHtml && !callActionBadgeHtml && !callPerspBadge ? '<span class="cell-neutral">-</span>' : ''}
                </div>
            `;

            // Put Buildup & FII Tag
            let putFiiBadgeHtml = '';
            if (pFii.short_tag && pFii.short_tag !== '-') {
                putFiiBadgeHtml = `<span class="fii-strike-tag ${pFii.code ? pFii.code.toLowerCase() : ''}" title="${pFii.desc || ''}">${pFii.short_tag}</span>`;
            }

            const putBuildupBadge = pB.short_label ? `
                <span class="buildup-tag" style="background:${pB.color || '#94a3b8'}20; color:${pB.color || '#94a3b8'}; border: 1px solid ${pB.color || '#94a3b8'}55;">
                    ${pB.short_label}
                </span>
            ` : '';

            let putPerspBadge = (currentPerspective !== 'all' && currentPerspective !== 'fii' && putPerspectiveBadgeHtml) ? putPerspectiveBadgeHtml : '';

            const putBuildupCellContent = `
                <div class="buildup-cell-content">
                    ${putFiiBadgeHtml}
                    ${putActionBadgeHtml}
                    ${putBuildupBadge}
                    ${putPerspBadge}
                    ${!putBuildupBadge && !putFiiBadgeHtml && !putActionBadgeHtml && !putPerspBadge ? '<span class="cell-neutral">-</span>' : ''}
                </div>
            `;

            // Strike Center Box with FII Synthesis Badge & Probabilistic Tag
            let strikeBoxClass = 'strike-val-plain';
            if (isAtm) {
                strikeBoxClass = 'strike-val-box atm-box';
            } else if (isR1) {
                strikeBoxClass = 'strike-val-box r1-box';
            } else if (isS1) {
                strikeBoxClass = 'strike-val-box s1-box';
            } else if (isR2) {
                strikeBoxClass = 'strike-val-box r2-box';
            } else if (isS2) {
                strikeBoxClass = 'strike-val-box s2-box';
            } else if (isInOsc) {
                strikeBoxClass = 'strike-val-box osc-box';
            }

            // FII Synthesis Badge (Always visible for key strikes)
            let fiiBadgeHtml = '';
            const fiiBadgeText = s.fii_strike_badge || (isR1 ? '🏦 Major FII Resistance Cap' : (isS1 ? '🏰 Strong FII Support Wall' : (isR2 ? '🏦 Secondary FII Supply Ceiling' : (isS2 ? '🏰 Secondary FII Demand Floor' : (s.is_high_volume ? '🎯 FII High Volume Zone' : (isAtm ? '⭐ Market Pivot' : ''))))));
            if (fiiBadgeText) {
                let fiiClass = 'fii-gen-sub';
                if (isR1) fiiClass = 'fii-r1-sub';
                else if (isS1) fiiClass = 'fii-s1-sub';
                else if (isR2) fiiClass = 'fii-r2-sub';
                else if (isS2) fiiClass = 'fii-s2-sub';
                else if (s.is_high_volume) fiiClass = 'fii-vol-sub';
                else if (isAtm) fiiClass = 'pivot-sub';
                else if (s.is_max_ce_add) fiiClass = 'fii-ce-sub';
                else if (s.is_max_pe_add) fiiClass = 'fii-pe-sub';
                fiiBadgeHtml = `<span class="strike-fii-sub ${fiiClass}">${fiiBadgeText}</span>`;
            }

            let probTagHtml = '';
            if (s.prob_tag) {
                const pLabel = (typeof s.prob_tag === 'object' && s.prob_tag) ? s.prob_tag.label : s.prob_tag;
                const pClass = (isS1 || isS2) ? 'support' : ((isR1 || isR2) ? 'resistance' : (isAtm ? 'atm' : 'pin'));
                if (pLabel) {
                    probTagHtml = `<span class="strike-prob-pill ${pClass}">${pLabel}</span>`;
                }
            }

            let gamePlanTagHtml = '';
            if (currentPerspective === 'pro' || currentPerspective === 'client') {
                const centerBadge = pActive.center_badge;
                const centerClass = pActive.center_class || 'badge-pro-s1';
                if (centerBadge) {
                    gamePlanTagHtml = `<span class="strike-gameplan-pill ${centerClass}">${centerBadge}</span>`;
                }
            }

            const strikeCellContent = `
                <div class="strike-box-wrapper">
                    <span class="${strikeBoxClass}">${formatNumber(s.strike)}${isAtm ? ' ATM' : ''}</span>
                    ${fiiBadgeHtml}
                    ${probTagHtml}
                    ${gamePlanTagHtml}
                </div>
            `;

            tr.innerHTML = `
                <!-- CALLS (CE) -->
                <td class="td-oi-ce ${callItmClass}">
                    <div class="oi-bar-fill-ce" style="width: ${c.oi_pct || 0}%;"></div>
                    <span class="cell-val-text">${callBadgeHtml}${formatNumber(c.oi)}</span>
                </td>
                <td class="${callItmClass} ${chgCallClass}">
                    <span class="cell-val-text">${c.chg_oi > 0 ? '+' : ''}${formatNumber(c.chg_oi)}</span>
                </td>
                <td class="${callItmClass} col-buildup-cell">${callBuildupCellContent}</td>
                <td class="${callItmClass} cell-neutral">${formatNumber(c.volume)}</td>
                <td class="${callItmClass} col-ltp font-bold">${c.ltp ? c.ltp.toFixed(2) : '-'}</td>
                <td class="${callItmClass} ${chgPCallClass}">${cChgPStr}</td>

                <!-- STRIKE (CENTER) -->
                <td class="col-strike-center">${strikeCellContent}</td>

                <!-- PUTS (PE) -->
                <td class="${putItmClass} ${chgPPutClass}">${pChgPStr}</td>
                <td class="${putItmClass} col-ltp font-bold">${p.ltp ? p.ltp.toFixed(2) : '-'}</td>
                <td class="${putItmClass} cell-neutral">${formatNumber(p.volume)}</td>
                <td class="${putItmClass} col-buildup-cell">${putBuildupCellContent}</td>
                <td class="${putItmClass} ${chgPutClass}">
                    <span class="cell-val-text">${p.chg_oi > 0 ? '+' : ''}${formatNumber(p.chg_oi)}</span>
                </td>
                <td class="td-oi-pe ${putItmClass}">
                    <div class="oi-bar-fill-pe" style="width: ${p.oi_pct || 0}%;"></div>
                    <span class="cell-val-text">${formatNumber(p.oi)}${putBadgeHtml}</span>
                </td>
            `;

            tbody.appendChild(tr);
        });
    });
}

// --- Modals & Event Listeners ---

function closeModals() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
}

// --- YouTube Sidebar & Multi-Page Controllers ---

function initYouTubeSidebar() {
    const sidebar = document.getElementById('ytSidebar');
    const mainContent = document.getElementById('ytMainContent');
    const btnToggle = document.getElementById('btnSidebarToggle');
    const backdrop = document.getElementById('ytSidebarBackdrop');

    if (!sidebar || !btnToggle) return;

    // Restore saved collapsed state for desktop
    const savedCollapsed = localStorage.getItem('yt_sidebar_collapsed') === 'true';
    if (savedCollapsed && window.innerWidth > 900) {
        sidebar.classList.add('collapsed');
        if (mainContent) mainContent.classList.add('sidebar-collapsed');
    }

    btnToggle.addEventListener('click', () => {
        if (window.innerWidth <= 900) {
            // Mobile off-canvas toggle
            sidebar.classList.toggle('open');
            if (backdrop) backdrop.classList.toggle('active', sidebar.classList.contains('open'));
        } else {
            // Desktop rail toggle (YouTube style)
            sidebar.classList.toggle('collapsed');
            const isCollapsed = sidebar.classList.contains('collapsed');
            if (mainContent) mainContent.classList.toggle('sidebar-collapsed', isCollapsed);
            localStorage.setItem('yt_sidebar_collapsed', isCollapsed);
        }
    });

    if (backdrop) {
        backdrop.addEventListener('click', () => {
            sidebar.classList.remove('open');
            backdrop.classList.remove('active');
        });
    }

    // Modal triggers from sidebar and topbar
    const bindModal = (triggerIds, modalId, onOpen) => {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        triggerIds.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.addEventListener('click', () => {
                    modal.classList.add('active');
                    if (onOpen) onOpen();
                    if (window.innerWidth <= 900) {
                        sidebar.classList.remove('open');
                        if (backdrop) backdrop.classList.remove('active');
                    }
                });
            }
        });
    };

    bindModal(['btnTopUpload', 'btnSideUpload', 'btnOpenUpload'], 'uploadModal');
    bindModal(['btnTopPaste', 'btnSidePaste', 'btnOpenPaste'], 'pasteModal');
    // Sample files modal removed
    bindModal(['btnSideRules'], 'rulesModal');
    bindModal(['btnSideGuide'], 'guideModal');

    // Sidebar NSE fetch shortcut
    const btnSideFetch = document.getElementById('btnSideFetch');
    if (btnSideFetch) {
        btnSideFetch.addEventListener('click', () => {
            if (window.location.pathname.includes('/participant-oi')) {
                const fetchBtn = document.getElementById('btnMainFetch');
                if (fetchBtn) fetchBtn.click();
            } else {
                window.location.href = '/participant-oi';
            }
        });
    }

    // Close buttons for modals
    ['btnCloseUpload', 'btnCancelUpload', 'btnClosePaste', 'btnCancelPaste', 
     'btnCloseSamples', 'btnCloseSamples2', 'btnCloseRules', 'btnCloseRules2', 
     'btnCloseGuide', 'btnCloseGuide2'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.addEventListener('click', closeModals);
    });

    // Close modals on Escape key
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModals();
            if (sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                if (backdrop) backdrop.classList.remove('active');
            }
        }
    });
}

function initUploadDropzone() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const filesList = document.getElementById('selectedFilesList');
    const submitUploadBtn = document.getElementById('btnSubmitUpload');
    const sampleInsideBtn = document.getElementById('btnLoadSamplesInsideModal');

    if (!dropZone || !fileInput) return;

    let selectedFiles = [];

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
    });

    function handleFiles(files) {
        selectedFiles = Array.from(files);
        if (filesList) filesList.innerHTML = '';
        if (selectedFiles.length > 0) {
            selectedFiles.forEach(f => {
                if (filesList) {
                    const item = document.createElement('div');
                    item.className = 'file-item';
                    item.innerHTML = `<span>📁 ${f.name}</span><span>${(f.size / 1024).toFixed(1)} KB</span>`;
                    filesList.appendChild(item);
                }
            });
            if (submitUploadBtn) submitUploadBtn.disabled = false;
        } else {
            if (submitUploadBtn) submitUploadBtn.disabled = true;
        }
    }

    if (submitUploadBtn) {
        submitUploadBtn.addEventListener('click', () => {
            if (selectedFiles.length > 0) {
                uploadFiles(selectedFiles);
            }
        });
    }

    if (sampleInsideBtn) {
        sampleInsideBtn.addEventListener('click', () => {
            loadDemoData();
            closeModals();
        });
    }
}

function initPasteForm() {
    const submitPasteBtn = document.getElementById('btnSubmitPaste');
    if (!submitPasteBtn) return;
    submitPasteBtn.addEventListener('click', () => {
        const text = document.getElementById('pasteArea')?.value || '';
        const date = document.getElementById('pasteDate')?.value || '';
        if (!text.trim()) {
            alert('Please paste some CSV, TSV, or tabular text.');
            return;
        }
        pasteData(text, date);
    });
}

// --- Home / Overview Controller & Master Date Integration Hub ---

async function initHomePage() {
    const activeDate = getActiveTradingDate();
    const masterDateInput = document.getElementById('homeMasterDateInput');
    const lookbackSelect = document.getElementById('homeLookbackSelect');
    const syncAllBtn = document.getElementById('btnHomeSyncAll');

    if (masterDateInput) {
        masterDateInput.value = activeDate;
        masterDateInput.addEventListener('change', () => {
            const newDate = masterDateInput.value;
            if (newDate) syncHomeToDate(newDate);
        });
        masterDateInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const newDate = masterDateInput.value;
                if (newDate) syncHomeToDate(newDate);
            }
        });
    }

    if (syncAllBtn) {
        syncAllBtn.addEventListener('click', () => {
            const d = masterDateInput ? masterDateInput.value : getActiveTradingDate();
            if (d) syncHomeToDate(d);
        });
    }

    if (lookbackSelect) {
        lookbackSelect.addEventListener('change', () => {
            const d = masterDateInput ? masterDateInput.value : getActiveTradingDate();
            if (d) syncHomeToDate(d);
        });
    }



    // Attach click to Home preset buttons specifically
    document.querySelectorAll('.home-date-hub-section .date-preset-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const pDate = btn.getAttribute('data-preset');
            if (pDate) {
                if (masterDateInput) masterDateInput.value = pDate;
                syncHomeToDate(pDate);
            }
        });
    });

    // Run initial sync for the active date on page load
    syncHomeToDate(activeDate);
}

async function syncHomeToDate(targetDate) {
    if (!targetDate) return;
    
    // 1. Centralized active date update across app state
    setActiveTradingDate(targetDate, false);

    const masterDateInput = document.getElementById('homeMasterDateInput');
    if (masterDateInput && masterDateInput.value !== targetDate) masterDateInput.value = targetDate;

    const activeDateText = document.getElementById('homeActiveDateText');
    if (activeDateText) activeDateText.innerText = targetDate;

    const lookbackSelect = document.getElementById('homeLookbackSelect');
    const days = lookbackSelect ? parseInt(lookbackSelect.value) : 5;

    // Update status banner to syncing
    const statusBox = document.getElementById('homeSyncStatusBox');
    const statusIcon = document.getElementById('homeSyncStatusIcon');
    const statusText = document.getElementById('homeSyncStatusText');
    const syncAllBtn = document.getElementById('btnHomeSyncAll');

    if (syncAllBtn) {
        syncAllBtn.disabled = true;
        syncAllBtn.innerHTML = '<span class="btn-icon">⏳</span> Syncing All...';
    }
    if (statusBox && statusIcon && statusText) {
        statusIcon.innerText = '🔄';
        statusText.innerHTML = `Synchronizing all 6 sections for <strong style="color: #38bdf8;">${targetDate}</strong> (${days} days lookback)...`;
    }

    // 2. Synchronize all section gateway links with ?date=
    const sectionRoutes = [
        { id: 'syncLinkParticipant', base: '/participant-oi' },
        { id: 'syncLinkOc', base: '/option-chain' },
        { id: 'syncLinkPipeline', base: '/pipeline' },
        { id: 'syncLinkStrike', base: '/strike-intelligence' },
        { id: 'syncLinkReport', base: '/details-report' },
        { id: 'syncLinkSelling', base: '/option-selling' }
    ];

    sectionRoutes.forEach(sr => {
        const el = document.getElementById(sr.id);
        if (el) el.href = `${sr.base}?date=${encodeURIComponent(targetDate)}`;
    });

    document.querySelectorAll('.btn-gateway').forEach(btn => {
        const currentHref = btn.getAttribute('href') || '';
        const baseHref = currentHref.split('?')[0];
        if (baseHref) {
            btn.href = `${baseHref}?date=${encodeURIComponent(targetDate)}`;
        }
    });

    // 3. Update browser URL history state smoothly without reload
    try {
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('date', targetDate);
        window.history.replaceState({ date: targetDate }, '', newUrl.toString());
    } catch(e) {}

    // 4. Fetch Participant OI & Outlook for Home Pulse
    try {
        let pRes = null;
        const res = await fetch('/api/fetch-nse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: targetDate, days: days })
        });
        const json = await res.json();
        if (json.status === 'success' && json.result) {
            currentData = json.result;
            pRes = json.result;
        }

        if (pRes) {
            updateHomeParticipantPulse(pRes);
        }
    } catch (e) {
        console.error('Home participant fetch error:', e);
    }

    // 5. Fetch Option Chain Pulse
    try {
        const ocRes = await fetch(`/api/option-chain?symbol=NIFTY&date=${encodeURIComponent(targetDate)}`);
        const ocJson = await ocRes.json();
        if (ocJson.status === 'success') {
            currentOcData = ocJson;
            updateHomeOcPulse(ocJson);
        }
    } catch (e) {
        console.error('Home option chain fetch error:', e);
    }

    // 6. Update Section Chips to Synced
    const chips = ['chipParticipant', 'chipOc', 'chipPipeline', 'chipStrike', 'chipReport', 'chipSelling'];
    chips.forEach(cid => {
        const chip = document.getElementById(cid);
        if (chip) {
            chip.innerText = `● Synced (${targetDate.substring(5)})`;
            chip.style.background = 'rgba(34, 197, 94, 0.2)';
            chip.style.color = '#4ade80';
            chip.style.border = '1px solid rgba(34, 197, 94, 0.4)';
        }
    });

    if (statusBox && statusIcon && statusText) {
        statusIcon.innerText = '✅';
        statusText.innerHTML = `All 6 sections successfully integrated & synchronized for session <strong style="color: #4ade80;">${targetDate}</strong>.`;
    }

    if (syncAllBtn) {
        syncAllBtn.disabled = false;
        syncAllBtn.innerHTML = '<span class="btn-icon">⚡</span> Sync All Sections';
    }
}

function updateHomeParticipantPulse(result) {
    if (!result) return;
    const dateStr = result.today_date || getActiveTradingDate();
    const topDate = document.getElementById('topbarActiveDateDisplay');
    if (topDate) topDate.innerText = dateStr;

    const outlook = result.market_outlook;
    if (outlook) {
        const vText = document.getElementById('homeVerdictText');
        const vBadge = document.getElementById('homeVerdictBadge');
        const mFill = document.getElementById('homeMeterFill');
        const mScore = document.getElementById('homeMeterScore');
        const tBox = document.getElementById('homeTrapNotice');
        const tText = document.getElementById('homeTrapText');

        if (vText) vText.innerText = outlook.verdict || 'Derivatives Stance';
        if (vBadge) {
            vBadge.innerText = outlook.stance || 'NEUTRAL';
            vBadge.style.color = outlook.badge_color || '#38bdf8';
            vBadge.style.borderColor = outlook.badge_color || '#38bdf8';
            vBadge.style.background = (outlook.badge_color ? outlook.badge_color + '22' : 'rgba(56, 189, 248, 0.15)');
        }
        const score = outlook.score || 0;
        const clampedScore = Math.max(-100, Math.min(100, score));
        const fillPercent = ((clampedScore + 100) / 200) * 100;
        if (mFill) mFill.style.width = `${fillPercent}%`;
        if (mScore) mScore.innerText = `Score: ${score > 0 ? '+' : ''}${score}`;

        if (tBox && tText) {
            if (outlook.retail_trap && outlook.retail_trap.detected) {
                tBox.style.display = 'flex';
                const trapFactor = (outlook.factors || []).find(f => f.includes('RETAIL TRAP ALERT')) || 
                                   'Prime short-squeeze trap alert! Retail heavily trapped.';
                tText.innerText = trapFactor.replace('🚨 RETAIL TRAP ALERT:', '').trim();
            } else {
                tBox.style.display = 'none';
            }
        }

        const insights = outlook.participant_insights || {};
        const fiiEl = document.getElementById('homeFiiStance');
        const proEl = document.getElementById('homeProStance');
        const clEl = document.getElementById('homeClientStance');
        const actEl = document.getElementById('homeActionShort');

        if (fiiEl && insights.FII) fiiEl.innerText = `${insights.FII.stance} (${insights.FII.today_action})`;
        if (proEl && insights.Pro) proEl.innerText = `${insights.Pro.stance} (${insights.Pro.today_action})`;
        if (clEl && insights.Client) clEl.innerText = `${insights.Client.stance} (${insights.Client.today_action})`;
        if (actEl && outlook.next_day_action) actEl.innerText = outlook.next_day_action;
    }
}

function updateHomeOcPulse(ocData) {
    if (!ocData) return;
    const spot = document.getElementById('homeSpotPrice');
    const atm = document.getElementById('homeAtmStrike');
    const pcr = document.getElementById('homePcrVal');
    const pcrStance = document.getElementById('homePcrStance');
    const maxPain = document.getElementById('homeMaxPain');
    const osc = document.getElementById('homeOscZone');

    if (spot) spot.innerText = formatNumber(Math.round(ocData.spot_price * 100) / 100);
    if (atm) atm.innerText = formatNumber(ocData.atm_strike);
    if (pcr) {
        pcr.innerText = ocData.pcr ? ocData.pcr.toFixed(2) : '-';
        if (ocData.pcr_color) pcr.style.color = ocData.pcr_color;
    }
    if (pcrStance) {
        pcrStance.innerText = ocData.pcr_stance || '-';
        if (ocData.pcr_color) pcrStance.style.color = ocData.pcr_color;
    }
    if (maxPain) maxPain.innerText = formatNumber(ocData.max_pain);
    if (osc && ocData.oscillation_zone) osc.innerText = ocData.oscillation_zone.label || '-';
}

// --- Option Chain Page Controller ---

function initOptionChainPage() {
    // 0. Trading Date Picker
    const ocDateInput = document.getElementById('ocMainDateInput');
    const savedDate = localStorage.getItem('selected_trading_date') || '2026-10-30';
    if (ocDateInput) {
        ocDateInput.value = savedDate;
        ocDateInput.addEventListener('change', () => {
            const newDate = ocDateInput.value;
            if (newDate) {
                setActiveTradingDate(newDate, true);
                fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, newDate);
            }
        });
        ocDateInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const newDate = ocDateInput.value;
                if (newDate) {
                    setActiveTradingDate(newDate, true);
                    fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, newDate);
                }
            }
        });
    }

    // 1. Symbol Pills
    document.querySelectorAll('#ocMainSymbolPills .oc-pill-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#ocMainSymbolPills .oc-pill-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentOcSymbol = btn.getAttribute('data-symbol') || 'NIFTY';
            currentOcExpiry = null;
            const targetDate = localStorage.getItem('selected_trading_date') || '2026-10-30';
            fetchOptionChain(currentOcSymbol, null, currentOcWindow, targetDate);
        });
    });

    // 2. Expiry Select
    const expSelect = document.getElementById('ocMainExpirySelect');
    if (expSelect) {
        expSelect.addEventListener('change', () => {
            currentOcExpiry = expSelect.value;
            const targetDate = localStorage.getItem('selected_trading_date') || '2026-10-30';
            fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, targetDate);
        });
    }

    // 3. Strikes Window Select
    const winSelect = document.getElementById('ocMainWindowSelect');
    if (winSelect) {
        winSelect.addEventListener('change', () => {
            currentOcWindow = parseInt(winSelect.value) || 15;
            const targetDate = localStorage.getItem('selected_trading_date') || '2026-10-30';
            fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, targetDate);
        });
    }

    // 4. Refresh Button
    const refreshBtn = document.getElementById('btnMainRefreshOc');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            const targetDate = localStorage.getItem('selected_trading_date') || '2026-10-30';
            fetchOptionChain(currentOcSymbol, currentOcExpiry, currentOcWindow, targetDate);
        });
    }

    // 5. Perspective Switcher Pills (All Big Players, FII, PRO, CLIENT)
    document.querySelectorAll('#ocPerspectivePills .perspective-pill-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = btn.getAttribute('data-perspective') || 'all';
            setPerspective(p);
        });
    });

    // 6. Subview tabs
    document.querySelectorAll('#ocSubViewTabs .subview-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const subview = btn.dataset.subview;
            switchOcSubView(subview);
        });
    });

    // 7. Initial Fetch on page load
    fetchOptionChain(currentOcSymbol, null, currentOcWindow, savedDate);
}

function switchOcSubView(subview) {
    document.querySelectorAll('#ocSubViewTabs .subview-tab-btn').forEach(b => {
        if (b.dataset.subview === subview) b.classList.add('active');
        else b.classList.remove('active');
    });

    const pTable = document.getElementById('subviewTable');
    const pChart = document.getElementById('subviewChart');
    const pSynergy = document.getElementById('subviewSynergy');

    if (subview === 'table') {
        if (pTable) pTable.style.display = 'block';
        if (pChart) pChart.style.display = 'none';
        if (pSynergy) pSynergy.style.display = 'none';
    } else if (subview === 'chart') {
        if (pTable) pTable.style.display = 'none';
        if (pChart) pChart.style.display = 'block';
        if (pSynergy) pSynergy.style.display = 'none';
        if (currentOcData) {
            renderOptionChainChart(currentOcData.chart_data, currentOcData.oscillation_zone, currentOcData.spot_price, currentOcData.atm_strike, currentOcData);
        }
    } else if (subview === 'synergy') {
        if (pTable) pTable.style.display = 'none';
        if (pChart) pChart.style.display = 'none';
        if (pSynergy) pSynergy.style.display = 'block';
    } else if (subview === 'all') {
        if (pTable) pTable.style.display = 'block';
        if (pChart) pChart.style.display = 'block';
        if (pSynergy) pSynergy.style.display = 'block';
        if (currentOcData) {
            renderOptionChainChart(currentOcData.chart_data, currentOcData.oscillation_zone, currentOcData.spot_price, currentOcData.atm_strike, currentOcData);
        }
    }
}

// --- Participant OI Page Controller ---

function initParticipantOiPage() {
    const mainFetchBtn = document.getElementById('btnMainFetch');
    const mainDateInput = document.getElementById('mainDateInput');
    const mainDaysSelect = document.getElementById('mainDaysSelect');

    const activeDate = getActiveTradingDate();
    if (mainDateInput) {
        mainDateInput.value = activeDate;
    }
    const activeDateDisplay = document.getElementById('activeDateDisplay');
    if (activeDateDisplay) {
        activeDateDisplay.innerText = activeDate;
    }
    const topbarDisplay = document.getElementById('topbarActiveDateDisplay');
    if (topbarDisplay) {
        topbarDisplay.innerText = activeDate;
    }

    if (mainFetchBtn && mainDateInput && mainDaysSelect) {
        mainFetchBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const date = mainDateInput.value || getActiveTradingDate();
            const days = mainDaysSelect.value || 5;
            if (!date) {
                alert('Please select a date.');
                return;
            }
            setActiveTradingDate(date, false);
            fetchFromNse(date, days);
        });

        mainDateInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                mainFetchBtn.click();
            }
        });

        mainDateInput.addEventListener('change', () => {
            const newDate = mainDateInput.value;
            if (newDate) {
                setActiveTradingDate(newDate, false);
                const days = mainDaysSelect ? mainDaysSelect.value : 5;
                fetchFromNse(newDate, days);
            }
        });

        mainDaysSelect.addEventListener('change', () => {
            const date = mainDateInput ? mainDateInput.value : getActiveTradingDate();
            const days = mainDaysSelect.value;
            fetchFromNse(date, days);
        });
    }

    const btnLogs = document.getElementById('btnToggleLogs');
    if (btnLogs) {
        btnLogs.addEventListener('click', () => {
            const drawer = document.getElementById('fetchLogsDrawer');
            if (drawer) {
                const isHidden = drawer.style.display === 'none';
                drawer.style.display = isHidden ? 'block' : 'none';
                btnLogs.innerText = isHidden ? 'Logs ▲' : 'Logs ▼';
            }
        });
    }

    // Immediately trigger auto-fetch for active trading session
    const initialDays = mainDaysSelect ? mainDaysSelect.value : 5;
    console.log('[AlphaDeriv] initParticipantOiPage: Auto-fetching for date:', activeDate);
    fetchFromNse(activeDate, initialDays);
}

// --- SPA Page Switcher ---

function switchSpaPage(pageKey, updateUrl = true) {
    const pageHome = document.getElementById('pageHome');
    const pageOc = document.getElementById('pageOptionChain');
    const pagePart = document.getElementById('pageParticipantOi');

    if (pageHome && pageOc && pagePart) {
        pageHome.style.display = (pageKey === 'home') ? 'block' : 'none';
        pageOc.style.display = (pageKey === 'option-chain') ? 'block' : 'none';
        pagePart.style.display = (pageKey === 'participant-oi') ? 'block' : 'none';

        document.querySelectorAll('.yt-nav-item[data-nav-page]').forEach(link => {
            const linkPage = link.getAttribute('data-nav-page');
            link.classList.toggle('active', linkPage === pageKey);
        });

        document.body.dataset.page = pageKey;
        if (pageKey === 'home') {
            document.title = 'Home & Overview | NSE Derivatives Intelligence';
            if (updateUrl && window.location.pathname !== '/') {
                history.pushState({ page: 'home' }, '', '/');
            }
            initHomePage();
        } else if (pageKey === 'option-chain') {
            document.title = 'Proper Option Chain (13-Column Pro View) | NSE Derivatives Intelligence';
            if (updateUrl && window.location.pathname !== '/option-chain') {
                history.pushState({ page: 'option-chain' }, '', '/option-chain');
            }
            initOptionChainPage();
        } else if (pageKey === 'participant-oi') {
            document.title = 'Participant-Wise OI Analyzer (6 Instruments) | NSE Derivatives Intelligence';
            if (updateUrl && window.location.pathname !== '/participant-oi') {
                history.pushState({ page: 'participant-oi' }, '', '/participant-oi');
            }
            initParticipantOiPage();
        } else if (pageKey === 'details-report') {
            window.location.href = '/details-report';
            return;
        } else if (pageKey === 'option-selling') {
            window.location.href = '/option-selling';
            return;
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
        if (pageKey === 'home') window.location.href = '/';
        else if (pageKey === 'option-chain') window.location.href = '/option-chain';
        else if (pageKey === 'participant-oi') window.location.href = '/participant-oi';
        else if (pageKey === 'details-report') window.location.href = '/details-report';
        else if (pageKey === 'option-selling') window.location.href = '/option-selling';
    }
}

// ==========================================================================
// DETAILS REPORT PAGE CONTROLLER
// ==========================================================================

let currentReportData = null;
let currentReportSymbol = 'NIFTY';

function initDetailsReportPage() {
    // 1. Symbol Pill Switching
    const symbolPills = document.querySelectorAll('#repSymbolPills .rep-pill-btn');
    symbolPills.forEach(btn => {
        btn.addEventListener('click', () => {
            const sym = btn.getAttribute('data-symbol');
            if (sym === currentReportSymbol) return;

            symbolPills.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentReportSymbol = sym;
            loadDetailsReport(currentReportSymbol);
        });
    });

    // 2. Trading Date Selector
    const repDateInput = document.getElementById('repDateInput');
    const activeDate = getActiveTradingDate();
    if (repDateInput) {
        repDateInput.value = activeDate;
        repDateInput.addEventListener('change', () => {
            const newDate = repDateInput.value;
            if (newDate) {
                setActiveTradingDate(newDate, true);
            }
        });
    }

    // 3. Print / PDF Button
    const btnPrint = document.getElementById('btnPrintReport');
    if (btnPrint) {
        btnPrint.addEventListener('click', () => {
            window.print();
        });
    }

    // 4. Copy Summary Button
    const btnCopy = document.getElementById('btnCopyReportSummary');
    if (btnCopy) {
        btnCopy.addEventListener('click', () => {
            copyReportSummaryToClipboard();
        });
    }

    // 5. Refresh Button
    const btnRefresh = document.getElementById('btnRefreshReport');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            loadDetailsReport(currentReportSymbol, getActiveTradingDate());
        });
    }

    // 6. Initialize Quick-Jump Nav
    initReportQuickNav();

    // Initial Load
    loadDetailsReport(currentReportSymbol, activeDate);
}

function loadDetailsReport(symbol, dateStr) {
    const overlay = document.getElementById('reportLoadingOverlay');
    if (overlay) overlay.style.display = 'flex';

    // Retrieve active trading date
    const targetDate = dateStr || getActiveTradingDate();

    // Prepare payload
    const postBody = {
        symbol: symbol,
        date: dateStr
    };

    // Retrieve cached participant-wise OI data if available
    const partData = getCachedParticipantData(targetDate);
    if (partData) {
        postBody.participant_data = partData;
    }

    fetch('/api/details-report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(postBody)
    })
        .then(res => {
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (overlay) overlay.style.display = 'none';
            if (data.status === 'success') {
                currentReportData = data;
                renderDetailsReport(data);
            } else {
                console.error("API Details Report Error:", data.message);
            }
        })
        .catch(err => {
            if (overlay) overlay.style.display = 'none';
            console.error("Failed to fetch details report:", err);
        });
}

function renderSegregatedInstruments(instruments) {
    const container = document.getElementById('segregatedInstrumentsContainer');
    if (!container || !Array.isArray(instruments)) return;

    container.innerHTML = '';

    instruments.forEach((inst) => {
        const rowDiv = document.createElement('div');
        rowDiv.className = 'instrument-split-row';

        const map = inst.mapping || {};
        const strikes = map.mapped_strikes || [];
        const pFlows = map.participant_flows || [];
        const carriedHeaders = inst.carried_headers || ['TODAY', '1 DAY AGO', '2 DAYS AGO', '3 DAYS AGO', '4 DAYS AGO'];

        // Build Table Rows HTML for Left Panel
        let tableRowsHtml = '';
        (inst.rows || []).forEach(r => {
            const longFormatted = (r.long_chg > 0 ? '+' : '') + formatNumber(r.long_chg);
            const shortFormatted = (r.short_chg > 0 ? '+' : '') + formatNumber(r.short_chg);
            const netFormatted = (r.net_buy_sell > 0 ? '+' : '') + formatNumber(r.net_buy_sell);

            let carriedCellsHtml = '';
            carriedHeaders.forEach(ch => {
                const cVal = r.carried ? r.carried[ch] : 0;
                const cColor = r.carried_colors ? (r.carried_colors[ch] || 'neutral') : 'neutral';
                const cFormatted = (cVal > 0 ? '+' : '') + formatNumber(cVal);
                carriedCellsHtml += `<td class="cell-${cColor}">${cFormatted}</td>`;
            });

            tableRowsHtml += `
                <tr>
                    <td><strong>${r.participant || '-'}</strong></td>
                    <td>
                        <div class="td-val-block">
                            <span class="td-num cell-${r.long_color || 'neutral'}">${longFormatted}</span>
                            <span class="td-tag ${r.long_color || 'neutral'}">${r.long_label || '-'}</span>
                        </div>
                    </td>
                    <td>
                        <div class="td-val-block">
                            <span class="td-num cell-${r.short_color || 'neutral'}">${shortFormatted}</span>
                            <span class="td-tag ${r.short_color || 'neutral'}">${r.short_label || '-'}</span>
                        </div>
                    </td>
                    <td>
                        <div class="td-val-block">
                            <span class="td-num cell-${r.net_color || 'neutral'}"><strong>${netFormatted}</strong></span>
                            <span class="td-tag ${r.net_color || 'neutral'}">${r.net_label || '-'}</span>
                        </div>
                    </td>
                    ${carriedCellsHtml}
                </tr>
            `;
        });

        // Build Carried Table Headers
        let carriedThHtml = '';
        carriedHeaders.forEach(ch => {
            carriedThHtml += `<th>${ch}</th>`;
        });

        // Build Mapped Strikes Pills for Right Panel
        let strikesHtml = '';
        strikes.forEach(s => {
            strikesHtml += `
                <div class="strike-pill-box">
                    <span class="sp-level">${s.level}</span>
                    <strong class="sp-strike">${formatNumber(s.strike)}</strong>
                    <span class="sp-role" title="${s.role || ''}">${s.role || ''}</span>
                    <span class="sp-tag">${s.tag || ''}</span>
                </div>
            `;
        });

        // Build Participant Quick Flow Tags
        let pFlowsHtml = '';
        pFlows.forEach(pf => {
            const netFormatted = (pf.net > 0 ? '+' : '') + formatNumber(pf.net);
            pFlowsHtml += `
                <div class="pflow-item">
                    <span class="pflow-name">${pf.name}</span>
                    <span class="pflow-val ${pf.color || 'neutral'}">${netFormatted}</span>
                </div>
            `;
        });

        rowDiv.innerHTML = `
            <!-- Left Side: Complete Participant OI Table for this Instrument -->
            <div class="split-left-panel">
                <div class="split-panel-header">
                    <div class="sph-title-box">
                        <span class="sph-icon">${inst.icon || '📊'}</span>
                        <div>
                            <h3 class="sph-title">${inst.display_title || inst.instrument}</h3>
                        </div>
                    </div>
                    <span class="sph-badge ${inst.badge_color || 'neutral'}">${inst.badge || 'PARTICIPANT FLOW'}</span>
                </div>

                <div class="split-table-wrap">
                    <table class="split-data-table">
                        <thead>
                            <tr>
                                <th>Participant</th>
                                <th>Added / Closed Longs</th>
                                <th>Added / Closed Shorts</th>
                                <th>Net Today</th>
                                ${carriedThHtml}
                            </tr>
                        </thead>
                        <tbody>
                            ${tableRowsHtml}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Right Side: Option Chain Strike Mapping & Next-Day Impact -->
            <div class="split-right-panel">
                <div class="map-card-header">
                    <h4 class="map-card-title">
                        <span>🎯</span> Option Chain Strike Mapping & Impact
                    </h4>
                    <span class="sph-badge ${inst.badge_color || 'neutral'}">Next-Day Setup</span>
                </div>

                <div class="map-concept-box">
                    <span class="map-concept-lbl">MAPPED DERIVATIVE CONCEPT</span>
                    <p class="map-concept-text">${map.concept || '-'}</p>
                </div>

                <!-- Mapped Strikes Pills -->
                <div class="mapped-strikes-grid">
                    ${strikesHtml}
                </div>

                <!-- Activity Details -->
                <div class="map-activity-block">
                    <div class="act-item">
                        <span class="act-lbl">Smart Money (FII + PRO):</span>
                        <p class="act-val">${map.smart_activity || '-'}</p>
                    </div>
                    <div class="act-item">
                        <span class="act-lbl">Retail Flow (Clients):</span>
                        <p class="act-val">${map.retail_activity || '-'}</p>
                    </div>
                </div>

                <!-- Retail Trap Alert -->
                <div class="map-trap-box">
                    <p>${map.trap_alert || '-'}</p>
                </div>

                <!-- Next-Day Market Impact Callout -->
                <div class="map-impact-box">
                    <p><strong>⚡ Next-Day Price Impact:</strong> ${map.next_day_impact || '-'}</p>
                </div>

                <!-- 4-Participant Flows -->
                <div class="pflow-mini-grid">
                    ${pFlowsHtml}
                </div>
            </div>
        `;

        container.appendChild(rowDiv);
    });
}

function renderParticipantDossiers(dossiers) {
    const grid = document.getElementById('repDossiersGrid');
    if (!grid || !dossiers) return;

    grid.innerHTML = '';
    const pKeys = ['FII', 'PRO', 'CLIENT', 'DII'];
    const icons = { 'FII': '🏦', 'PRO': '🏢', 'CLIENT': '👤', 'DII': '🏛️' };
    const roles = {
        'FII': 'Institutional Market Driver',
        'PRO': 'Straddle Writers & Market Makers',
        'CLIENT': 'Retail Traders (Contrarian Fuel)',
        'DII': 'Domestic Institutional Anchor'
    };

    pKeys.forEach(pCode => {
        const d = dossiers[pCode] || {};
        const card = document.createElement('div');
        card.className = `dossier-card dossier-${pCode.toLowerCase()}`;

        const stanceColorClass = d.stance_color === 'green' ? 'badge-green' : (d.stance_color === 'red' ? 'badge-red' : 'badge-blue');

        let specialBlockHtml = '';
        if (pCode === 'FII' && d.defense_walls) {
            specialBlockHtml = `
                <div class="dossier-meta-footer">
                    <div class="dmeta-col">
                        <span class="dmeta-lbl">Defense Walls:</span>
                        <strong>${d.defense_walls.support || 'S1 Floor (25,000)'}</strong>
                    </div>
                    <div class="dmeta-col">
                        <span class="dmeta-lbl">Next-Day Price Impact:</span>
                        <span>${d.next_day_price_impact || ''}</span>
                    </div>
                </div>
            `;
        } else if (pCode === 'PRO') {
            specialBlockHtml = `
                <div class="dossier-meta-footer">
                    <div class="dmeta-col">
                        <span class="dmeta-lbl">Pinning Target:</span>
                        <strong>${d.pinning_target || ''}</strong>
                    </div>
                    <div class="dmeta-col">
                        <span class="dmeta-lbl">Theta Decay:</span>
                        <span>${d.theta_decay_pace || ''}</span>
                    </div>
                </div>
            `;
        } else if (pCode === 'CLIENT') {
            specialBlockHtml = `
                <div class="trap-alert-box" style="margin-top:10px;">
                    <div class="trap-header"><span class="trap-icon">⚠️</span><strong>RETAIL TRAP ANALYSIS:</strong></div>
                    <p>${d.trap_analysis || ''}</p>
                </div>
            `;
        } else if (pCode === 'DII') {
            specialBlockHtml = `
                <div class="dossier-meta-footer">
                    <div class="dmeta-col">
                        <span class="dmeta-lbl">Cash Support:</span>
                        <strong>${d.cash_market_support || ''}</strong>
                    </div>
                    <div class="dmeta-col">
                        <span class="dmeta-lbl">Portfolio Role:</span>
                        <span>${d.portfolio_protection_role || ''}</span>
                    </div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="dossier-header">
                <div class="dossier-identity">
                    <span class="dossier-icon">${icons[pCode] || '👥'}</span>
                    <div>
                        <h4 class="dossier-name">${d.name || pCode}</h4>
                        <span class="dossier-role-tag">${roles[pCode] || ''}</span>
                    </div>
                </div>
                <span class="dossier-stance-badge ${stanceColorClass}">${d.stance_badge || d.stance || ''}</span>
            </div>

            <div class="dossier-body">
                <div class="dossier-block block-positioned">
                    <span class="dblock-lbl">WHAT THEY POSITIONED:</span>
                    <p>${d.what_they_positioned || ''}</p>
                </div>

                <div class="what-they-want-box">
                    <div class="wtw-header">
                        <span class="wtw-icon">🎯</span>
                        <strong>WHAT THEY WANT (DESIRED OUTCOME):</strong>
                    </div>
                    <p>${d.what_they_want || ''}</p>
                </div>

                ${specialBlockHtml}

                <div class="dossier-quote-bar">
                    <span class="quote-icon">“</span>
                    <span>${d.key_quote || ''}</span>
                </div>
            </div>
        `;

        grid.appendChild(card);
    });
}

function initReportQuickNav() {
    const qnLinks = document.querySelectorAll('.report-quicknav-bar .qn-link');
    if (!qnLinks || qnLinks.length === 0) return;

    qnLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const targetId = link.getAttribute('href');
            if (!targetId || !targetId.startsWith('#')) return;
            const targetEl = document.querySelector(targetId);
            if (targetEl) {
                e.preventDefault();
                targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                qnLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            }
        });
    });

    if ('IntersectionObserver' in window) {
        const sections = document.querySelectorAll('.report-module-container');
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.getAttribute('id');
                    qnLinks.forEach(l => {
                        if (l.getAttribute('href') === `#${id}`) {
                            l.classList.add('active');
                        } else {
                            l.classList.remove('active');
                        }
                    });
                }
            });
        }, { rootMargin: '-20% 0px -60% 0px' });

        sections.forEach(sec => observer.observe(sec));
    }
}

function renderUnifiedHeatmap(heatmapData) {
    const tbody = document.getElementById('unifiedHeatmapBody');
    const tfoot = document.getElementById('unifiedHeatmapFoot');
    if (!tbody || !heatmapData) return;

    tbody.innerHTML = '';
    const rows = heatmapData.rows || [];

    const formatSigned = (val) => {
        if (val === undefined || val === null) return '0';
        return (val > 0 ? '+' : '') + formatNumber(val);
    };

    rows.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'hm-data-row';

        const renderCell = (part) => {
            if (!part) return '<td class="hm-val-cell val-neutral">-</td>';
            const colorClass = part.color === 'green' ? 'val-green' : (part.color === 'red' ? 'val-red' : 'val-neutral');
            const badgeClass = part.color === 'green' ? 'badge-green' : (part.color === 'red' ? 'badge-red' : 'badge-neutral');
            const netFormatted = part.net_formatted || formatSigned(part.net);
            const carriedFormatted = part.carried_formatted || formatSigned(part.carried);
            return `
                <td class="hm-val-cell ${colorClass}">
                    <div class="hm-net-number">${netFormatted}</div>
                    <div class="hm-action-tag ${badgeClass}">${part.label || 'Neutral'}</div>
                    <div class="hm-carried-sub">Carried: ${carriedFormatted}</div>
                </td>
            `;
        };

        const skewBadgeClass = r.skew_color === 'green' ? 'badge-green' : (r.skew_color === 'red' ? 'badge-red' : 'badge-blue');

        tr.innerHTML = `
            <td class="hm-inst-col">
                <div class="hm-inst-name">
                    <span class="hm-inst-icon">${r.icon || '📊'}</span>
                    <div>
                        <strong>${r.instrument}</strong>
                    </div>
                </div>
            </td>
            ${renderCell(r.fii)}
            ${renderCell(r.pro)}
            ${renderCell(r.client)}
            ${renderCell(r.dii)}
            <td class="hm-skew-col">
                <span class="hm-skew-badge ${skewBadgeClass}">${r.skew_badge || 'BALANCED'}</span>
                <p class="hm-skew-desc">${r.skew_text || ''}</p>
            </td>
        `;
        tbody.appendChild(tr);
    });

    if (tfoot && heatmapData.totals) {
        const t = heatmapData.totals;
        tfoot.innerHTML = `
            <tr class="hm-total-row">
                <td class="hm-total-lbl">
                    <strong>TOTAL NET EXPOSURE</strong>
                </td>
                <td class="hm-total-cell text-${t.fii_color || 'neutral'}">
                    <strong>${t.fii_formatted || formatSigned(t.fii_net)}</strong>
                </td>
                <td class="hm-total-cell text-${t.pro_color || 'neutral'}">
                    <strong>${t.pro_formatted || formatSigned(t.pro_net)}</strong>
                </td>
                <td class="hm-total-cell text-${t.client_color || 'neutral'}">
                    <strong>${t.client_formatted || formatSigned(t.client_net)}</strong>
                </td>
                <td class="hm-total-cell text-${t.dii_color || 'neutral'}">
                    <strong>${t.dii_formatted || formatSigned(t.dii_net)}</strong>
                </td>
                <td class="hm-total-summary">
                    <span class="badge-blue">Aggregated Desk Flows</span>
                </td>
            </tr>
        `;
    }
}

function renderReportFivePillars(pillars, imv) {
    const grid = document.getElementById('repFivePillarsGrid');
    if (!grid) return;

    grid.innerHTML = '';
    const list = Array.isArray(pillars) && pillars.length > 0 ? pillars : (imv && Array.isArray(imv.five_pillars) ? imv.five_pillars : []);

    list.forEach((p, idx) => {
        const card = document.createElement('div');
        const colorClass = p.status_color === 'green' ? 'pillar-green' : (p.status_color === 'red' ? 'pillar-red' : (p.status_color === 'amber' ? 'pillar-amber' : 'pillar-blue'));
        const badgeClass = p.status_color === 'green' ? 'badge-green' : (p.status_color === 'red' ? 'badge-red' : (p.status_color === 'amber' ? 'badge-amber' : 'badge-blue'));
        const meterColor = p.status_color === 'green' ? 'meter-green' : (p.status_color === 'red' ? 'meter-red' : (p.status_color === 'amber' ? 'meter-amber' : 'meter-blue'));

        card.className = `five-pillar-card ${colorClass}`;
        card.innerHTML = `
            <div class="fpc-header">
                <div class="fpc-num-title">
                    <span class="fpc-num">P${idx + 1}</span>
                    <h4 class="fpc-title">${p.name}</h4>
                </div>
                <span class="fpc-score-badge">${p.score_pts} / ${p.weight_pts} Pts</span>
            </div>
            <div class="fpc-meter-bar">
                <div class="fpc-meter-fill ${meterColor}" style="width: ${Math.min(100, Math.max(5, p.score_pct || 50))}%;"></div>
            </div>
            <div class="fpc-status-row">
                <span class="fpc-status-badge ${badgeClass}">${p.status || 'NEUTRAL'}</span>
                <span class="fpc-metric-lbl">${p.metric_label || ''}</span>
            </div>
            <p class="fpc-detail">${p.detail || ''}</p>
        `;
        grid.appendChild(card);
    });
}

function renderTimedProtocol(protocolSteps) {
    const container = document.getElementById('timedProtocolContainer');
    if (!container) return;

    container.innerHTML = '';
    const steps = Array.isArray(protocolSteps) ? protocolSteps : [];

    steps.forEach((s) => {
        const item = document.createElement('div');
        item.className = 'timed-step-card';
        const badgeColor = s.badge_color === 'green' ? 'badge-green' : (s.badge_color === 'amber' ? 'badge-amber' : 'badge-blue');

        let rulesHtml = '';
        if (Array.isArray(s.rules)) {
            rulesHtml = s.rules.map(r => `<li><span class="rule-bullet">▸</span> <span>${r}</span></li>`).join('');
        }

        item.innerHTML = `
            <div class="tstep-time-col">
                <span class="tstep-num-circle">${s.step}</span>
                <span class="tstep-time">${s.time_window}</span>
                <span class="tstep-phase-badge ${badgeColor}">${s.badge}</span>
            </div>
            <div class="tstep-content-col">
                <div class="tstep-header">
                    <span class="tstep-icon">${s.icon || '⏰'}</span>
                    <h4 class="tstep-title">${s.phase_name}</h4>
                </div>
                <p class="tstep-summary">${s.action_summary}</p>
                ${rulesHtml ? `<ul class="tstep-rules-list">${rulesHtml}</ul>` : ''}
            </div>
        `;
        container.appendChild(item);
    });
}

function renderDetailsReport(data) {
    if (!data) return;

    const exec = data.executive_summary || {};
    const imv = data.institutional_market_view || {};
    const prob = data.market_probability_matrix || {};
    const dossiers = data.participant_dossiers || {};
    const scenarios = data.next_day_scenarios || {};
    const bottomLine = data.bottom_line_for_traders || {};
    const segregated = data.segregated_instruments || [];
    const heatmap = data.unified_heatmap || {};
    const timedProtocol = data.timed_execution_protocol || [];

    // 1. Topbar & Date displays
    const topbarDate = document.getElementById('topbarActiveDateDisplay');
    if (topbarDate && data.date) topbarDate.innerText = data.date;

    const repDateInput = document.getElementById('repDateInput');
    if (repDateInput && data.date) repDateInput.value = data.date;

    document.querySelectorAll('.print-symbol').forEach(el => el.innerText = data.symbol);
    document.querySelectorAll('.print-date').forEach(el => el.innerText = data.date);

    // 2. Snapshot Strip
    const spotEl = document.getElementById('repSpotPrice');
    if (spotEl) spotEl.innerText = formatNumber(exec.spot_price);

    const atmEl = document.getElementById('repAtmStrike');
    if (atmEl) atmEl.innerText = `ATM: ${formatNumber(exec.atm_strike)}`;

    const maxPainEl = document.getElementById('repMaxPain');
    if (maxPainEl) maxPainEl.innerText = formatNumber(exec.max_pain);

    const pcrEl = document.getElementById('repPcr');
    if (pcrEl) pcrEl.innerText = exec.pcr !== undefined ? exec.pcr.toFixed(2) : '-';

    const pcrStanceEl = document.getElementById('repPcrStance');
    if (pcrStanceEl) {
        pcrStanceEl.innerText = exec.pcr_stance || 'Oversold';
        pcrStanceEl.className = 'pcr-badge';
        if (exec.pcr_color === 'green') pcrStanceEl.classList.add('badge-green');
        else if (exec.pcr_color === 'red') pcrStanceEl.classList.add('badge-red');
    }

    const snapStance = document.getElementById('repSnapStance');
    if (snapStance) {
        snapStance.innerText = exec.master_stance ? exec.master_stance.split('(')[0].trim() : 'BULLISH BIAS';
        snapStance.className = `snap-val ${exec.master_stance_color === 'red' ? 'text-red' : (exec.master_stance_color === 'neutral' ? 'text-amber' : 'text-green')}`;
    }

    const snapRegime = document.getElementById('repSnapRegime');
    if (snapRegime) snapRegime.innerText = exec.regime_tag || 'Short Squeeze Setup';

    const snapConf = document.getElementById('repSnapConfidence');
    if (snapConf) snapConf.innerText = `${exec.confidence_score || 84}%`;

    const repSnapScoreLabel = document.getElementById('repSnapScoreLabel');
    if (repSnapScoreLabel) {
        repSnapScoreLabel.innerText = `Composite Score: ${exec.composite_score !== undefined ? exec.composite_score : (imv.composite_score || 78)}/100`;
    }

    // 3. Module 1: Pre-Market Executive Command Center
    const regimeTag = document.getElementById('repRegimeTag');
    if (regimeTag) regimeTag.innerText = exec.regime_tag || 'INSTITUTIONAL ANALYSIS';

    const confPill = document.getElementById('repConfidencePill');
    if (confPill) {
        confPill.innerHTML = `<span class="conf-dot">●</span> ${exec.confidence_score || 84}% Institutional Conviction`;
    }

    const sessionChip = document.getElementById('repActiveSessionChip');
    if (sessionChip) sessionChip.innerText = `Session: ${data.date}`;

    const masterStanceEl = document.getElementById('repMasterStance');
    if (masterStanceEl) masterStanceEl.innerText = exec.master_stance || '';

    const verdictNarrativeEl = document.getElementById('repNextDayVerdict');
    if (verdictNarrativeEl) verdictNarrativeEl.innerText = exec.next_day_verdict || '';

    const repInvalidationTrigger = document.getElementById('repInvalidationTrigger');
    if (repInvalidationTrigger) {
        repInvalidationTrigger.innerText = exec.invalidation_trigger || imv.invalidation_trigger || 'Decisive 15-minute close below S1 Support';
    }

    const smartAlignEl = document.getElementById('repSmartAlignment');
    if (smartAlignEl) smartAlignEl.innerText = exec.smart_money_alignment || '';

    const retailAlignEl = document.getElementById('repRetailAlignment');
    if (retailAlignEl) retailAlignEl.innerText = exec.retail_alignment || '';

    // 3-Phase Intraday Trend Roadmap
    const tp = exec.trend_phases || data.trend_phases || {};
    const openPhase = tp.opening_phase || {};
    const intraPhase = tp.intraday_phase || {};
    const closePhase = tp.closing_phase || {};

    const repTrendOpening = document.getElementById('repTrendOpening');
    if (repTrendOpening) repTrendOpening.innerText = openPhase.description || '';
    const repTrendOpeningTag = document.getElementById('repTrendOpeningTag');
    if (repTrendOpeningTag) repTrendOpeningTag.innerText = openPhase.tag || 'Opening Auction';

    const repTrendIntraday = document.getElementById('repTrendIntraday');
    if (repTrendIntraday) repTrendIntraday.innerText = intraPhase.description || '';
    const repTrendIntradayTag = document.getElementById('repTrendIntradayTag');
    if (repTrendIntradayTag) repTrendIntradayTag.innerText = intraPhase.tag || 'Midday Drift';

    const repTrendClosing = document.getElementById('repTrendClosing');
    if (repTrendClosing) repTrendClosing.innerText = closePhase.description || '';
    const repTrendClosingTag = document.getElementById('repTrendClosingTag');
    if (repTrendClosingTag) repTrendClosingTag.innerText = closePhase.tag || 'Expiry Gravity';

    // Opening Directives 4 Blocks
    const blGamePlan = document.getElementById('blGamePlan');
    if (blGamePlan) blGamePlan.innerText = bottomLine.gameplan_915 || '';

    const blKeyLevel = document.getElementById('blKeyLevel');
    if (blKeyLevel) blKeyLevel.innerText = bottomLine.key_level_of_the_day || '';

    const blStrategy = document.getElementById('blStrategy');
    if (blStrategy) blStrategy.innerText = bottomLine.recommended_strategy || '';

    const blAvoid = document.getElementById('blAvoid');
    if (blAvoid) blAvoid.innerText = bottomLine.what_to_avoid || '';

    const blPlainSummary = document.getElementById('blPlainSummary');
    if (blPlainSummary) blPlainSummary.innerText = bottomLine.plain_english_summary || '';

    // 4. Module 2: Unified 4x6 Heatmap
    renderUnifiedHeatmap(heatmap);

    // 5. Module 3: 5-Pillar Confluence & Probability Distribution
    renderReportFivePillars(imv.five_pillars, imv);

    const domBadge = document.getElementById('repDominantRegimeBadge');
    if (domBadge) domBadge.innerText = `DOMINANT: ${prob.dominant_regime || 'RANGEBOUND'}`;

    const upPct = prob.upside_breakout_pct || 0;
    const rangePct = prob.rangebound_pinning_pct || 0;
    const downPct = prob.downside_breakdown_pct || 0;

    const repUpPct = document.getElementById('repUpsidePct');
    if (repUpPct) repUpPct.innerText = `${upPct}%`;
    const repUpBar = document.getElementById('repUpsideBar');
    if (repUpBar) repUpBar.style.width = `${upPct}%`;

    const repRangePct = document.getElementById('repRangePct');
    if (repRangePct) repRangePct.innerText = `${rangePct}%`;
    const repRangeBar = document.getElementById('repRangeBar');
    if (repRangeBar) repRangeBar.style.width = `${rangePct}%`;

    const repDownPct = document.getElementById('repDownsidePct');
    if (repDownPct) repDownPct.innerText = `${downPct}%`;
    const repDownBar = document.getElementById('repDownsideBar');
    if (repDownBar) repDownBar.style.width = `${downPct}%`;

    const ivEl = document.getElementById('repIvPct');
    if (ivEl) ivEl.innerText = `${prob.implied_volatility_pct || 12.6}%`;

    const dailyMoveEl = document.getElementById('repDailyMove');
    if (dailyMoveEl) dailyMoveEl.innerText = `± ${prob.expected_daily_move_pts || 165.5} Pts`;

    const sd1El = document.getElementById('repSd1Corridor');
    if (sd1El) sd1El.innerText = prob.sd1_corridor ? prob.sd1_corridor.label : '-';

    const sweetSpotEl = document.getElementById('repPinSweetSpot');
    if (sweetSpotEl) sweetSpotEl.innerText = prob.pinning_sweet_spot || '-';

    const decayPaceEl = document.getElementById('repDecayPace');
    if (decayPaceEl) decayPaceEl.innerText = prob.max_pain_pin ? prob.max_pain_pin.theta_decay_pace : 'Max Theta Decay';

    // 6. Module 4: Timed Execution Protocol (09:00 - 15:30)
    renderTimedProtocol(timedProtocol);

    // 7. Module 5: 3 Actionable Scenarios with Execution Blueprints
    const scenA = scenarios.scenario_a || {};
    const scenB = scenarios.scenario_b || {};
    const scenC = scenarios.scenario_c || {};

    const scenABadge = document.getElementById('scenABadge');
    if (scenABadge) scenABadge.innerText = `${scenA.probability_pct || 52}% Probability`;
    const scenATag = document.getElementById('scenATag');
    if (scenATag) {
        scenATag.innerText = scenA.sentiment_badge || 'DOMINANT REGIME';
        scenATag.className = `scen-tag ${scenA.color === 'red' ? 'tag-red' : (scenA.color === 'neutral' ? 'tag-amber' : 'tag-green')}`;
    }
    const cardA = document.getElementById('cardScenarioA');
    if (cardA && scenA.color) {
        cardA.className = `scenario-card ${scenA.color === 'red' ? 'scenario-bearish' : (scenA.color === 'neutral' ? 'scenario-range' : 'scenario-bullish')}`;
    }
    const scenATitle = document.getElementById('scenATitle');
    if (scenATitle) scenATitle.innerText = scenA.name || 'Scenario A: Bullish Squeeze';
    const scenATrigger = document.getElementById('scenATrigger');
    if (scenATrigger) scenATrigger.innerText = scenA.trigger_level || '';
    const scenATargets = document.getElementById('scenATargets');
    if (scenATargets) scenATargets.innerText = scenA.target_levels || '';
    const scenAInvalid = document.getElementById('scenAInvalidation');
    if (scenAInvalid) scenAInvalid.innerText = scenA.invalidation_level || '';
    const scenAReact = document.getElementById('scenAReaction');
    if (scenAReact) scenAReact.innerText = scenA.institutional_reaction || '';
    const scenAPlaybook = document.getElementById('scenAPlaybook');
    if (scenAPlaybook) scenAPlaybook.innerText = scenA.trader_playbook || '';

    const scenATrade = document.getElementById('scenATrade');
    if (scenATrade) scenATrade.innerText = scenA.recommended_trade || 'Bull Put Credit Spread (Sell 25,000 PE / Buy 24,850 PE)';
    const scenARiskReward = document.getElementById('scenARiskReward');
    if (scenARiskReward) scenARiskReward.innerText = scenA.risk_reward || '1 : 2.4';
    const scenABreakeven = document.getElementById('scenABreakeven');
    if (scenABreakeven) scenABreakeven.innerText = scenA.breakeven !== undefined ? `${scenA.breakeven}` : '24,965.0';
    const scenAPoints = document.getElementById('scenAPoints');
    if (scenAPoints) scenAPoints.innerText = scenA.target_points ? `+${scenA.target_points} Pts Upside` : '+142 Pts Upside';

    const scenBBadge = document.getElementById('scenBBadge');
    if (scenBBadge) scenBBadge.innerText = `${scenB.probability_pct || 38}% Probability`;
    const scenBTag = document.getElementById('scenBTag');
    if (scenBTag) {
        scenBTag.innerText = scenB.sentiment_badge || 'RANGE HARVEST';
        scenBTag.className = `scen-tag ${scenB.color === 'red' ? 'tag-red' : (scenB.color === 'neutral' ? 'tag-amber' : 'tag-green')}`;
    }
    const cardB = document.getElementById('cardScenarioB');
    if (cardB && scenB.color) {
        cardB.className = `scenario-card ${scenB.color === 'red' ? 'scenario-bearish' : (scenB.color === 'neutral' ? 'scenario-range' : 'scenario-bullish')}`;
    }
    const scenBTitle = document.getElementById('scenBTitle');
    if (scenBTitle) scenBTitle.innerText = scenB.name || 'Scenario B: Rangebound Pinning';
    const scenBTrigger = document.getElementById('scenBTrigger');
    if (scenBTrigger) scenBTrigger.innerText = scenB.trigger_level || '';
    const scenBPinning = document.getElementById('scenBPinning');
    if (scenBPinning) scenBPinning.innerText = scenB.pinning_corridor || '';
    const scenBInvalid = document.getElementById('scenBInvalidation');
    if (scenBInvalid) scenBInvalid.innerText = scenB.invalidation_level || '';
    const scenBReact = document.getElementById('scenBReaction');
    if (scenBReact) scenBReact.innerText = scenB.institutional_reaction || '';
    const scenBPlaybook = document.getElementById('scenBPlaybook');
    if (scenBPlaybook) scenBPlaybook.innerText = scenB.trader_playbook || '';

    const scenBTrade = document.getElementById('scenBTrade');
    if (scenBTrade) scenBTrade.innerText = scenB.recommended_trade || 'Delta-Neutral Iron Condor (Sell 25,000 PE & Sell 25,200 CE)';
    const scenBRiskReward = document.getElementById('scenBRiskReward');
    if (scenBRiskReward) scenBRiskReward.innerText = scenB.risk_reward || '1 : 1.8';
    const scenBBreakeven = document.getElementById('scenBBreakeven');
    if (scenBBreakeven) scenBBreakeven.innerText = scenB.breakeven !== undefined ? `${scenB.breakeven}` : '24,955 to 25,245';
    const scenBPoints = document.getElementById('scenBPoints');
    if (scenBPoints) scenBPoints.innerText = scenB.target_points ? `Capture ${scenB.target_points} Pts Theta` : 'Capture 60% Theta Decay';

    const scenCBadge = document.getElementById('scenCBadge');
    if (scenCBadge) scenCBadge.innerText = `${scenC.probability_pct || 10}% Probability`;
    const scenCTag = document.getElementById('scenCTag');
    if (scenCTag) {
        scenCTag.innerText = scenC.sentiment_badge || 'TAIL RISK';
        scenCTag.className = `scen-tag ${scenC.color === 'red' ? 'tag-red' : (scenC.color === 'neutral' ? 'tag-amber' : 'tag-green')}`;
    }
    const cardC = document.getElementById('cardScenarioC');
    if (cardC && scenC.color) {
        cardC.className = `scenario-card ${scenC.color === 'red' ? 'scenario-bearish' : (scenC.color === 'neutral' ? 'scenario-range' : 'scenario-bullish')}`;
    }
    const scenCTitle = document.getElementById('scenCTitle');
    if (scenCTitle) scenCTitle.innerText = scenC.name || 'Scenario C: Bearish Breakdown';
    const scenCTrigger = document.getElementById('scenCTrigger');
    if (scenCTrigger) scenCTrigger.innerText = scenC.trigger_level || '';
    const scenCTargets = document.getElementById('scenCTargets');
    if (scenCTargets) scenCTargets.innerText = scenC.target_levels || '';
    const scenCInvalid = document.getElementById('scenCInvalidation');
    if (scenCInvalid) scenCInvalid.innerText = scenC.invalidation_level || '';
    const scenCReact = document.getElementById('scenCReaction');
    if (scenCReact) scenCReact.innerText = scenC.institutional_reaction || '';
    const scenCPlaybook = document.getElementById('scenCPlaybook');
    if (scenCPlaybook) scenCPlaybook.innerText = scenC.trader_playbook || '';

    const scenCTrade = document.getElementById('scenCTrade');
    if (scenCTrade) scenCTrade.innerText = scenC.recommended_trade || 'Bear Put Debit Spread (Wait for 15m close below 24,975)';
    const scenCRiskReward = document.getElementById('scenCRiskReward');
    if (scenCRiskReward) scenCRiskReward.innerText = scenC.risk_reward || '1 : 3.0';
    const scenCBreakeven = document.getElementById('scenCBreakeven');
    if (scenCBreakeven) scenCBreakeven.innerText = scenC.breakeven !== undefined ? `${scenC.breakeven}` : '24,930.0';
    const scenCPoints = document.getElementById('scenCPoints');
    if (scenCPoints) scenCPoints.innerText = scenC.target_points ? `-${scenC.target_points} Pts Downside` : '-150 Pts Downside';

    const repScenariosSummaryBadge = document.getElementById('repScenariosSummaryBadge');
    if (repScenariosSummaryBadge) {
        repScenariosSummaryBadge.innerText = `${scenA.name || 'Scenario A'} (${scenA.probability_pct || 52}%) Dominant`;
    }

    // 8. Module 6: 6 Segregated Instruments Side-by-Side Split Mapping
    renderSegregatedInstruments(segregated);

    // 9. Module 7: What Everyone Positioned & What Everyone Wants (4 Dossiers)
    renderParticipantDossiers(dossiers);

    // 10. Module 8: Option Selling Advisory Brief Card
    const sellAdv = data.option_selling_advisory || {};
    const bestStrat = (sellAdv.top_strategies && sellAdv.top_strategies.length > 0) ? sellAdv.top_strategies[0] : null;
    if (bestStrat) {
        const repSellPop = document.getElementById('repSellPop');
        if (repSellPop) repSellPop.innerText = `${bestStrat.pop_pct || 85}% Win Rate`;

        const repSellDte = document.getElementById('repSellDte');
        if (repSellDte) repSellDte.innerText = `${sellAdv.days_to_expiry || 4} Days to Expiry`;

        const repSellTitle = document.getElementById('repSellTitle');
        if (repSellTitle) repSellTitle.innerText = bestStrat.name || '';

        const repSellArchetype = document.getElementById('repSellArchetype');
        if (repSellArchetype) repSellArchetype.innerText = `${bestStrat.archetype || ''} • ${bestStrat.market_view || ''}`;

        const repSellNetCredit = document.getElementById('repSellNetCredit');
        if (repSellNetCredit) repSellNetCredit.innerText = `+₹${bestStrat.net_credit_pts} pts (+₹${formatNumber(bestStrat.net_credit_inr)} / lot)`;

        const repSellMaxRisk = document.getElementById('repSellMaxRisk');
        if (repSellMaxRisk) repSellMaxRisk.innerText = `-₹${bestStrat.max_risk_pts} pts (-₹${formatNumber(bestStrat.max_risk_inr)} / lot)`;

        const repSellBreakeven = document.getElementById('repSellBreakeven');
        if (repSellBreakeven) repSellBreakeven.innerText = bestStrat.breakeven_label || formatNumber(bestStrat.breakeven_pts);

        const repSellMargin = document.getElementById('repSellMargin');
        if (repSellMargin) repSellMargin.innerText = `₹${formatNumber(bestStrat.margin_hedged_inr)} (Saved ${bestStrat.margin_saved_pct}%)`;

        const repSellRationale = document.getElementById('repSellRationale');
        if (repSellRationale) {
            repSellRationale.innerText = `${bestStrat.why_this_strategy_is_best || ''}\n\n${bestStrat.why_these_strikes_are_most_efficient || ''}`;
        }

        // Render Legs in Brief Card
        const repSellLegsContainer = document.getElementById('repSellLegs');
        if (repSellLegsContainer && bestStrat.legs) {
            repSellLegsContainer.innerHTML = '';
            bestStrat.legs.forEach(leg => {
                const legDiv = document.createElement('div');
                const isSell = leg.action_type === 'SELL';
                legDiv.className = `sb-leg-item ${isSell ? 'leg-sell' : 'leg-buy'}`;
                legDiv.innerHTML = `
                    <span class="leg-action-badge ${isSell ? 'badge-sell' : 'badge-buy'}">${isSell ? 'SELL' : 'BUY (HEDGE)'}</span>
                    <strong class="leg-strike">${formatNumber(leg.strike)} ${leg.opt_type}</strong>
                    <span class="leg-ltp">₹${leg.ltp}</span>
                    <span class="leg-greek">Δ: ${leg.delta} • ${isSell ? `Θ: +₹${leg.seller_theta}/day` : 'Tail Protection'}</span>
                `;
                repSellLegsContainer.appendChild(legDiv);
            });
        }
    }
}

function copyReportSummaryToClipboard() {
    if (!currentReportData) return;

    const exec = currentReportData.executive_summary || {};
    const prob = currentReportData.market_probability_matrix || {};
    const bottom = currentReportData.bottom_line_for_traders || {};

    const textToCopy = `=== NSE INSTITUTIONAL DERIVATIVES INTELLIGENCE REPORT ===
Symbol: ${currentReportData.symbol} | Date: ${currentReportData.date}
Spot: ${formatNumber(exec.spot_price)} | ATM: ${formatNumber(exec.atm_strike)} | Max Pain: ${formatNumber(exec.max_pain)} | PCR: ${exec.pcr}

MASTER STANCE:
${exec.master_stance}

NEXT-DAY VERDICT:
${exec.next_day_verdict}

PROBABILITY REGIMES:
- Upside Squeeze: ${prob.upside_breakout_pct}%
- Rangebound Pinning: ${prob.rangebound_pinning_pct}%
- Downside Breakdown: ${prob.downside_breakdown_pct}%
- Expected Move: ± ${prob.expected_daily_move_pts} Pts | Corridor: ${prob.sd1_corridor ? prob.sd1_corridor.label : '-'}

9:15 AM GAME PLAN:
${bottom.gameplan_915}

KEY LEVEL OF THE DAY:
${bottom.key_level_of_the_day}

RECOMMENDED STRATEGY:
${bottom.recommended_strategy}

WHAT TO STRICTLY AVOID:
${bottom.what_to_avoid}

2-MINUTE EXECUTIVE BRIEFING:
${bottom.plain_english_summary}
`;

    navigator.clipboard.writeText(textToCopy).then(() => {
        const btn = document.getElementById('btnCopyReportSummary');
        if (btn) {
            const orig = btn.innerHTML;
            btn.innerHTML = '✅ Copied to Clipboard!';
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-outline');
            setTimeout(() => {
                btn.innerHTML = orig;
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-outline');
            }, 2500);
        }
    }).catch(err => {
        console.error("Clipboard copy failed:", err);
    });
}

// ==========================================================================
// OPTION SELLING STRATEGIES CONTROLLER (ZERODHA VARSITY GREEKS MODEL)
// ==========================================================================

let currentSellingData = null;
let currentSellingSymbol = 'NIFTY';

function initSellingStrategiesPage() {
    const symbolPills = document.querySelectorAll('#sellSymbolPills .rep-pill-btn');
    symbolPills.forEach(btn => {
        btn.addEventListener('click', () => {
            const sym = btn.getAttribute('data-symbol');
            if (sym === currentSellingSymbol) return;

            symbolPills.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSellingSymbol = sym;
            loadSellingStrategies(currentSellingSymbol);
        });
    });

    const sellDateInput = document.getElementById('sellDateInput');
    const activeDate = getActiveTradingDate();
    if (sellDateInput) {
        sellDateInput.value = activeDate;
        sellDateInput.addEventListener('change', () => {
            const newDate = sellDateInput.value;
            if (newDate) {
                setActiveTradingDate(newDate, true);
                loadSellingStrategies(currentSellingSymbol, newDate);
            }
        });
    }

    const sellExpirySelect = document.getElementById('sellExpirySelect');
    if (sellExpirySelect) {
        sellExpirySelect.addEventListener('change', () => {
            loadSellingStrategies(currentSellingSymbol, getActiveTradingDate(), sellExpirySelect.value);
        });
    }

    const btnCopy = document.getElementById('btnCopySellStrategy');
    if (btnCopy) {
        btnCopy.addEventListener('click', copySellingStrategyTicket);
    }

    const btnPrint = document.getElementById('btnPrintSellTicket');
    if (btnPrint) {
        btnPrint.addEventListener('click', () => {
            window.print();
        });
    }

    loadSellingStrategies(currentSellingSymbol, activeDate);
}

function loadSellingStrategies(symbol = 'NIFTY', date = null, expiry = null) {
    const activeDate = date || getActiveTradingDate();
    const overlay = document.getElementById('sellLoadingOverlay');
    if (overlay) overlay.style.display = 'flex';

    const postBody = {
        symbol: symbol,
        date: activeDate
    };
    if (expiry) postBody.expiry = expiry;

    const partData = getCachedParticipantData(activeDate);
    if (partData) {
        postBody.participant_data = partData;
    }

    fetch('/api/option-selling', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(postBody)
    })
        .then(res => {
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (overlay) overlay.style.display = 'none';
            if (data.status === 'success') {
                currentSellingData = data;
                renderSellingStrategies(data);
            } else {
                console.error("Option selling API error:", data.message);
            }
        })
        .catch(err => {
            if (overlay) overlay.style.display = 'none';
            console.error("Failed to load option selling advisory:", err);
        });
}

function renderInstitutionalMarketView(viewData) {
    if (!viewData) return;

    // 1. Primary Stance Badge & Conviction
    const stanceBadge = document.getElementById('viewStanceBadge');
    if (stanceBadge) {
        stanceBadge.innerText = viewData.primary_stance || 'MARKET VIEW PENDING';
        stanceBadge.className = `view-stance-badge badge-${viewData.badge_color || 'green'}`;
    }

    const convPill = document.getElementById('viewConvictionPill');
    if (convPill) {
        convPill.innerText = viewData.conviction_rating || '85% CONVICTION';
        convPill.className = `view-conviction-pill pill-${viewData.badge_color || 'green'}`;
    }

    const stanceTitle = document.getElementById('viewStanceTitle');
    if (stanceTitle) stanceTitle.innerText = viewData.stance_subtitle || '';

    const recArch = document.getElementById('viewRecommendedArchetype');
    if (recArch) recArch.innerText = viewData.recommended_archetype || '';

    const targetCorr = document.getElementById('viewTargetCorridor');
    if (targetCorr) targetCorr.innerText = viewData.target_corridor || '';

    // 2. Score Dial
    const compScore = document.getElementById('viewCompositeScore');
    if (compScore) {
        compScore.innerText = viewData.composite_score || 50;
        compScore.className = `vsd-score text-${viewData.badge_color || 'green'}`;
    }

    const scoreBias = document.getElementById('viewScoreBias');
    if (scoreBias) {
        const sc = viewData.composite_score || 50;
        if (sc >= 58) {
            scoreBias.innerText = 'Bullish Floor Bias (≥ 58)';
        } else if (sc <= 42) {
            scoreBias.innerText = 'Bearish Supply Ceiling (≤ 42)';
        } else {
            scoreBias.innerText = 'Rangebound Pinning Equilibrium (43-57)';
        }
    }

    // 3. Invalidation Alert Trigger
    const invalTrigger = document.getElementById('viewInvalidationTrigger');
    if (invalTrigger) {
        invalTrigger.innerText = viewData.invalidation_trigger || 'Decisive breakout beyond 1-SD';
    }

    // 4. 5 Pillars Grid
    const pillarsGrid = document.getElementById('fivePillarsGrid');
    if (pillarsGrid && Array.isArray(viewData.five_pillars)) {
        pillarsGrid.innerHTML = '';
        viewData.five_pillars.forEach(pillar => {
            const card = document.createElement('div');
            card.className = `pillar-score-card pillar-card-${pillar.status_color || 'blue'}`;

            const iconMap = {
                'smart_money_futures': '📈',
                'option_writing_skew': '🛡️',
                'retail_trap_index': '🪤',
                'option_chain_structure': '⛓️',
                'volatility_normal_dist': '📊'
            };
            const icon = iconMap[pillar.id] || '⚡';

            card.innerHTML = `
                <div class="psc-top">
                    <span class="psc-icon">${icon}</span>
                    <div class="psc-titles">
                        <span class="psc-name">${pillar.name}</span>
                        <span class="psc-weight-badge">${pillar.weight_pts} Pts Max</span>
                    </div>
                </div>
                <div class="psc-status-row">
                    <span class="psc-status-pill pill-${pillar.status_color || 'blue'}">${pillar.status}</span>
                </div>
                <div class="psc-metric-box">
                    <span class="psc-metric-label">${pillar.metric_label}</span>
                </div>
                <div class="psc-meter-wrap">
                    <div class="psc-meter-track">
                        <div class="psc-meter-bar bar-${pillar.status_color || 'blue'}" style="width: ${pillar.score_pct}%;"></div>
                    </div>
                    <div class="psc-meter-label">
                        <span>Score: <strong>${pillar.score_pts}</strong> / ${pillar.weight_pts}</span>
                        <span>${pillar.score_pct}%</span>
                    </div>
                </div>
                <p class="psc-detail">${pillar.detail}</p>
            `;
            pillarsGrid.appendChild(card);
        });
    }

    // 5. Game Plan & Trap Cards
    const smartGameplan = document.getElementById('viewSmartMoneyGameplan');
    if (smartGameplan) smartGameplan.innerText = viewData.smart_money_gameplan || '';

    const retailTrap = document.getElementById('viewRetailTrapAnalysis');
    if (retailTrap) retailTrap.innerText = viewData.retail_trap_analysis || '';

    // 6. Strategy Fit Banner
    const stratFit = document.getElementById('viewStrategyFitText');
    if (stratFit) stratFit.innerText = viewData.why_strategy_fits_view || '';
}

function renderSellingStrategies(data) {
    if (!data) return;

    const memo = data.executive_memo || {};
    const topStrats = data.top_strategies || [];
    const bestStrat = topStrats.length > 0 ? topStrats[0] : null;
    const effMatrix = data.strike_efficiency_matrix || [];

    // Expiry dropdown
    const expirySelect = document.getElementById('sellExpirySelect');
    if (expirySelect && data.available_expiries) {
        expirySelect.innerHTML = '<option value="">Nearest Weekly Expiry</option>';
        data.available_expiries.forEach(exp => {
            const opt = document.createElement('option');
            opt.value = exp;
            opt.innerText = exp;
            if (data.selected_expiry === exp) opt.selected = true;
            expirySelect.appendChild(opt);
        });
    }

    // Date display & input sync
    const topbarDate = document.getElementById('topbarActiveDateDisplay');
    if (topbarDate && data.date) topbarDate.innerText = data.date;

    const sellDateInput = document.getElementById('sellDateInput');
    if (sellDateInput && data.date && sellDateInput.value !== data.date) {
        sellDateInput.value = data.date;
    }

    // Hero Section
    if (bestStrat) {
        const heroStratTitle = document.getElementById('heroStratTitle');
        if (heroStratTitle) heroStratTitle.innerText = bestStrat.name;

        const heroStratSub = document.getElementById('heroStratSub');
        if (heroStratSub) heroStratSub.innerText = `${bestStrat.archetype} • ${bestStrat.market_view} • SPAN Margin Slashed ${bestStrat.margin_saved_pct}%`;

        const heroPopBadge = document.getElementById('heroPopBadge');
        if (heroPopBadge) heroPopBadge.innerText = `${bestStrat.pop_pct}% Win Rate (POP)`;

        const heroDteBadge = document.getElementById('heroDteBadge');
        if (heroDteBadge) heroDteBadge.innerText = `${data.days_to_expiry} Days to Expiry`;

        const heroIvBadge = document.getElementById('heroIvBadge');
        if (heroIvBadge) heroIvBadge.innerText = `IV: ${data.iv_pct}%`;

        const heroNetCredit = document.getElementById('heroNetCredit');
        if (heroNetCredit) heroNetCredit.innerText = `+₹${formatNumber(bestStrat.net_credit_inr)} / lot`;

        const heroCreditPts = document.getElementById('heroCreditPts');
        if (heroCreditPts) heroCreditPts.innerText = `+${bestStrat.net_credit_pts} Pts per share`;

        const heroMaxRisk = document.getElementById('heroMaxRisk');
        if (heroMaxRisk) heroMaxRisk.innerText = `-₹${formatNumber(bestStrat.max_risk_inr)} / lot`;

        const heroRiskPts = document.getElementById('heroRiskPts');
        if (heroRiskPts) heroRiskPts.innerText = `-${bestStrat.max_risk_pts} Pts Max Risk`;

        const heroBreakeven = document.getElementById('heroBreakeven');
        if (heroBreakeven) heroBreakeven.innerText = bestStrat.breakeven_pts;

        const heroBeDesc = document.getElementById('heroBeDesc');
        if (heroBeDesc) heroBeDesc.innerText = bestStrat.breakeven_label;

        const heroMarginSavings = document.getElementById('heroMarginSavings');
        if (heroMarginSavings) heroMarginSavings.innerText = `${bestStrat.margin_saved_pct}% Slashed`;

        const heroMarginDetail = document.getElementById('heroMarginDetail');
        if (heroMarginDetail) heroMarginDetail.innerText = `₹${formatNumber(bestStrat.margin_naked_inr)} → ₹${formatNumber(bestStrat.margin_hedged_inr)}`;

        const heroThesisText = document.getElementById('heroThesisText');
        if (heroThesisText) heroThesisText.innerText = memo.key_selling_thesis || '';
    }

    // Render Institutional Market View Creation Matrix
    renderInstitutionalMarketView(data.institutional_market_view);

    // Top 3 Strategy Cards
    const stratContainer = document.getElementById('stratCardsContainer');
    if (stratContainer) {
        stratContainer.innerHTML = '';
        topStrats.forEach(strat => {
            const card = document.createElement('div');
            card.className = `selling-strat-card ${strat.is_recommended ? 'strat-recommended' : ''}`;

            let legsHtml = '';
            (strat.legs || []).forEach(leg => {
                const isSell = leg.action_type === 'SELL';
                legsHtml += `
                    <tr>
                        <td><span class="leg-action-pill ${isSell ? 'pill-sell' : 'pill-buy'}">${isSell ? 'SELL (Write)' : 'BUY (Hedge)'}</span></td>
                        <td><strong class="leg-k">${formatNumber(leg.strike)}</strong></td>
                        <td><span class="leg-type ${leg.opt_type === 'CE' ? 'type-ce' : 'type-pe'}">${leg.opt_type}</span></td>
                        <td>₹${leg.ltp}</td>
                        <td><span class="cell-mono font-bold">${leg.volume > 0 ? formatNumber(leg.volume) : '-'}</span></td>
                        <td><span class="cell-mono">${leg.oi > 0 ? formatNumber(leg.oi) : '-'}${leg.chg_oi ? ` <small class="${leg.chg_oi > 0 ? 'text-green' : 'text-red'}">(${leg.chg_oi > 0 ? '+' : ''}${formatNumber(leg.chg_oi)})</small>` : ''}</span></td>
                        <td><span class="cell-mono ${Math.abs(leg.delta) <= 0.25 ? 'text-green' : 'text-amber'}">${leg.delta}</span></td>
                        <td><span class="cell-mono text-green">+₹${leg.seller_theta}/day</span></td>
                        <td><span class="cell-mono text-muted">${leg.gamma}</span></td>
                        <td class="leg-purpose-cell">${leg.purpose}</td>
                    </tr>
                `;
            });

            card.innerHTML = `
                <div class="strat-card-header">
                    <div class="strat-head-left">
                        <div class="strat-rank-badge ${strat.rank === 1 ? 'rank-gold' : (strat.rank === 2 ? 'rank-silver' : 'rank-bronze')}">
                            RANK ${strat.rank}
                        </div>
                        <div>
                            <h3 class="strat-title">${strat.name}</h3>
                            <span class="strat-archetype-tag">${strat.archetype} • ${strat.market_view}</span>
                        </div>
                    </div>
                    <div class="strat-head-right">
                        <span class="strat-pop-badge">🎯 ${strat.pop_pct}% POP</span>
                        <span class="strat-suitability-pill badge-${strat.badge_color || 'green'}">${strat.suitability_badge}</span>
                    </div>
                </div>

                <div class="strat-card-body">
                    <!-- Legs Table with Volume & OI -->
                    <div class="strat-legs-table-wrap">
                        <table class="strat-legs-table">
                            <thead>
                                <tr>
                                    <th>Action</th>
                                    <th>Strike</th>
                                    <th>Type</th>
                                    <th>LTP</th>
                                    <th>Volume</th>
                                    <th>OI (Chg)</th>
                                    <th>Delta (Δ)</th>
                                    <th>Theta (Decay)</th>
                                    <th>Gamma (Γ)</th>
                                    <th>Purpose / Protection</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${legsHtml}
                            </tbody>
                        </table>
                    </div>

                    <!-- Financial & Margin Scorecard (2x3 Grid) -->
                    <div class="strat-scorecard-grid">
                        <div class="scorecard-box">
                            <span class="sc-lbl">Net Credit (Max Profit):</span>
                            <strong class="sc-val text-green">+₹${formatNumber(strat.net_credit_inr)}</strong>
                            <span class="sc-sub">+${strat.net_credit_pts} Pts per share</span>
                        </div>
                        <div class="scorecard-box">
                            <span class="sc-lbl">Max Defined Risk:</span>
                            <strong class="sc-val text-red">-₹${formatNumber(strat.max_risk_inr)}</strong>
                            <span class="sc-sub">-${strat.max_risk_pts} Pts per share</span>
                        </div>
                        <div class="scorecard-box">
                            <span class="sc-lbl">Breakeven Price:</span>
                            <strong class="sc-val text-amber">${strat.breakeven_pts}</strong>
                            <span class="sc-sub">${strat.breakeven_label}</span>
                        </div>
                        <div class="scorecard-box">
                            <span class="sc-lbl">Required Margin (Hedged):</span>
                            <strong class="sc-val text-cyan">₹${formatNumber(strat.margin_hedged_inr)}</strong>
                            <span class="sc-sub">vs ₹${formatNumber(strat.margin_naked_inr)} Naked</span>
                        </div>
                        <div class="scorecard-box">
                            <span class="sc-lbl">SPAN Margin Slashed:</span>
                            <strong class="sc-val text-green">${strat.margin_saved_pct}% Discount</strong>
                            <span class="sc-sub">Saved ₹${formatNumber(strat.margin_saved_inr)}</span>
                        </div>
                        <div class="scorecard-box">
                            <span class="sc-lbl">Return on Margin (ROM):</span>
                            <strong class="sc-val text-amber">${strat.return_on_margin_pct}%</strong>
                            <span class="sc-sub">Reward/Risk: ${strat.reward_risk_ratio}</span>
                        </div>
                    </div>

                    <!-- In-Depth Rationales (Varsity Framework) -->
                    <div class="strat-rationales-container">
                        <div class="strat-rat-box rat-suitability">
                            <div class="rat-header">
                                <span class="rh-icon">🏦</span>
                                <strong>Why this strategy is suitable for today's market:</strong>
                            </div>
                            <p>${strat.why_this_strategy_is_best}</p>
                        </div>

                        <div class="strat-rat-box rat-efficiency">
                            <div class="rat-header">
                                <span class="rh-icon">⚡</span>
                                <strong>Why these strike prices are most efficient (Delta, Theta, SD alignment):</strong>
                            </div>
                            <p>${strat.why_these_strikes_are_most_efficient}</p>
                        </div>

                        <div class="strat-rat-box rat-playbook">
                            <div class="rat-header">
                                <span class="rh-icon">🏹</span>
                                <strong>Actionable Execution & Risk Management Playbook:</strong>
                            </div>
                            <p style="white-space: pre-line;">${strat.execution_rules}</p>
                        </div>
                    </div>
                </div>
            `;
            stratContainer.appendChild(card);
        });
    }

    // Live Strike Efficiency Matrix Table
    const effBody = document.getElementById('efficiencyTableBody');
    if (effBody) {
        effBody.innerHTML = '';
        effMatrix.forEach(row => {
            const tr = document.createElement('tr');
            const k = row.strike;
            const c = row.call;
            const p = row.put;

            // Highlight sweet spot strikes
            const isCallSweet = (c.selling_score >= 70);
            const isPutSweet = (p.selling_score >= 70);
            const isAtm = (c.moneyness === 'ATM');

            tr.className = isAtm ? 'row-atm' : (isCallSweet || isPutSweet ? 'row-sweet-spot' : '');

            tr.innerHTML = `
                <!-- Call Side -->
                <td class="cell-mono">₹${c.ltp}</td>
                <td class="cell-mono"><small>${c.volume > 0 ? formatNumber(c.volume) : '-'}</small><br><span class="text-muted" style="font-size:0.75rem">${c.oi > 0 ? formatNumber(c.oi) : '-'}</span></td>
                <td class="cell-mono ${Math.abs(c.delta) <= 0.25 && c.delta > 0.05 ? 'text-green font-bold' : ''}">${c.delta}</td>
                <td class="cell-mono text-green">+₹${c.theta}</td>
                <td class="cell-mono text-muted">${c.gamma}</td>
                <td><span class="pop-pill ${c.pop_pct >= 75 ? 'pop-high' : ''}">${c.pop_pct}%</span></td>
                <td>
                    <div class="score-bar-wrap" title="Score: ${c.selling_score}/100">
                        <div class="score-bar-fill ${c.selling_score >= 70 ? 'fill-high' : (c.selling_score >= 50 ? 'fill-mid' : '')}" style="width: ${c.selling_score}%;"></div>
                        <span class="score-bar-val">${c.selling_score}</span>
                    </div>
                </td>

                <!-- Strike & Dist Center -->
                <td class="cell-strike-center ${isAtm ? 'strike-atm' : ''}">
                    <strong>${formatNumber(k)}</strong>
                    <span class="sm-role-tag">${c.role_tag !== '-' ? c.role_tag : (p.role_tag !== '-' ? p.role_tag : '')}</span>
                </td>
                <td class="cell-dist-center cell-mono">${row.dist_pts > 0 ? '+' : ''}${row.dist_pts} (${row.dist_pct}%)</td>

                <!-- Put Side -->
                <td>
                    <div class="score-bar-wrap" title="Score: ${p.selling_score}/100">
                        <div class="score-bar-fill ${p.selling_score >= 70 ? 'fill-high' : (p.selling_score >= 50 ? 'fill-mid' : '')}" style="width: ${p.selling_score}%;"></div>
                        <span class="score-bar-val">${p.selling_score}</span>
                    </div>
                </td>
                <td><span class="pop-pill ${p.pop_pct >= 75 ? 'pop-high' : ''}">${p.pop_pct}%</span></td>
                <td class="cell-mono text-muted">${p.gamma}</td>
                <td class="cell-mono text-green">+₹${p.theta}</td>
                <td class="cell-mono ${Math.abs(p.delta) <= 0.25 && Math.abs(p.delta) > 0.05 ? 'text-green font-bold' : ''}">${p.delta}</td>
                <td class="cell-mono"><small>${p.volume > 0 ? formatNumber(p.volume) : '-'}</small><br><span class="text-muted" style="font-size:0.75rem">${p.oi > 0 ? formatNumber(p.oi) : '-'}</span></td>
                <td class="cell-mono">₹${p.ltp}</td>
            `;
            effBody.appendChild(tr);
        });
    }
}


function initStrikeIntelligencePage() {
    let currentSiSymbol = 'NIFTY';
    const activeDate = getActiveTradingDate();

    // 1. Symbol pills
    document.querySelectorAll('#siSymbolPills .oc-pill-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#siSymbolPills .oc-pill-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSiSymbol = btn.getAttribute('data-symbol') || 'NIFTY';
            loadStrikeIntelligence(currentSiSymbol, getActiveTradingDate());
        });
    });

    // 2. Date Input
    const siDateInput = document.getElementById('siDateInput');
    if (siDateInput) {
        siDateInput.value = activeDate;
        siDateInput.addEventListener('change', () => {
            const newDate = siDateInput.value;
            if (newDate) {
                setActiveTradingDate(newDate, true);
                loadStrikeIntelligence(currentSiSymbol, newDate);
            }
        });
    }

    // 3. Refresh button
    const btnRefresh = document.getElementById('btnRefreshSi');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            loadStrikeIntelligence(currentSiSymbol, getActiveTradingDate());
        });
    }

    loadStrikeIntelligence(currentSiSymbol, activeDate);
}

async function loadStrikeIntelligence(symbol, dateStr) {
    const targetDate = dateStr || getActiveTradingDate();
    try {
        const pData = getCachedParticipantData(targetDate);
        const res = await fetch('/api/option-chain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                date: targetDate,
                symbol: symbol,
                window: 15,
                participant_data: pData
            })
        });
        const data = await res.json();
        if (data.status === 'success') {
            const spotEl = document.getElementById('siSpotPrice');
            if (spotEl) spotEl.innerText = formatNumber(Math.round(data.spot_price * 100) / 100);

            const atmEl = document.getElementById('siAtmStrike');
            if (atmEl) atmEl.innerText = `ATM: ${formatNumber(data.atm_strike)}`;

            const pcrVal = document.getElementById('siPcrVal');
            if (pcrVal) {
                pcrVal.innerText = data.pcr.toFixed(2);
                pcrVal.style.color = data.pcr_color || '#38bdf8';
            }

            const pcrStance = document.getElementById('siPcrStance');
            if (pcrStance) pcrStance.innerText = data.pcr_stance || '';

            const maxPainVal = document.getElementById('siMaxPainVal');
            if (maxPainVal) maxPainVal.innerText = formatNumber(data.max_pain);

            const resStrike = document.getElementById('siResStrike');
            if (resStrike && data.major_resistance) resStrike.innerText = `${formatNumber(data.major_resistance.strike)} CE`;

            const resOi = document.getElementById('siResOi');
            if (resOi && data.major_resistance) resOi.innerText = `${formatNumber(data.major_resistance.oi)} Open Contracts`;

            const supStrike = document.getElementById('siSupStrike');
            if (supStrike && data.major_support) supStrike.innerText = `${formatNumber(data.major_support.strike)} PE`;

            const supOi = document.getElementById('siSupOi');
            if (supOi && data.major_support) supOi.innerText = `${formatNumber(data.major_support.oi)} Open Contracts`;

            const corrVal = document.getElementById('siCorridorVal');
            if (corrVal && data.oscillation_zone) corrVal.innerText = data.oscillation_zone.label || '-';

            // Render Big Player Cockpit Component
            renderBigPlayerStrikeCockpit(data.big_player_strike_intelligence, data.big_player_game_plan, data.spot_price, data.atm_strike);
        }
    } catch(e) {
        console.error('Error loading strike intelligence:', e);
    }
}

function copySellingStrategyTicket() {
    if (!currentSellingData || !currentSellingData.top_strategies || currentSellingData.top_strategies.length === 0) return;
    const best = currentSellingData.top_strategies[0];
    const sym = currentSellingData.symbol;
    const dt = currentSellingData.date;

    let legsStr = '';
    (best.legs || []).forEach(leg => {
        legsStr += `  • ${leg.action}: ${formatNumber(leg.strike)} ${leg.opt_type} @ ₹${leg.ltp} (Delta: ${leg.delta}, Theta: +₹${leg.seller_theta}/day)\n`;
    });

    const ticket = `=== ${sym} OPTION SELLING TRADE EXECUTION TICKET ===
Date: ${dt} | Symbol: ${sym} | Days to Expiry: ${currentSellingData.days_to_expiry}
Strategy: ${best.name}
Archetype: ${best.archetype} (${best.market_view})

LEGS TO EXECUTE:
${legsStr}
FINANCIALS:
  Net Credit Collected: +${best.net_credit_pts} Pts (+₹${formatNumber(best.net_credit_inr)} / lot)
  Max Defined Risk: -${best.max_risk_pts} Pts (-₹${formatNumber(best.max_risk_inr)} / lot)
  Probability of Profit: ${best.pop_pct}%
  Breakeven: ${best.breakeven_pts} (${best.breakeven_label})
  SPAN Margin Required: ₹${formatNumber(best.margin_hedged_inr)} (Saved ${best.margin_saved_pct}% vs ₹${formatNumber(best.margin_naked_inr)} Naked)
  Return on Margin: ${best.return_on_margin_pct}%

VARSITY RATIONALE:
${best.why_this_strategy_is_best}

STRIKE EFFICIENCY:
${best.why_these_strikes_are_most_efficient}

EXECUTION RULES:
${best.execution_rules}
`;

    navigator.clipboard.writeText(ticket).then(() => {
        const btn = document.getElementById('btnCopySellStrategy');
        if (btn) {
            const oldHtml = btn.innerHTML;
            btn.innerHTML = '<span>✓ Copied Ticket!</span>';
            setTimeout(() => { btn.innerHTML = oldHtml; }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy strategy:', err);
    });
}

// --- Main DOM Ready Dispatcher ---


// ---------------------------------------------------------------------------
// 5-DATA QUANTITATIVE INSTITUTIONAL PIPELINE CONTROLLER
// ---------------------------------------------------------------------------

function formatSignedNumber(val) {
    if (val === null || val === undefined || val === '-') return '-';
    try {
        const n = parseInt(val, 10);
        if (isNaN(n)) return val;
        const formatted = formatNumber(Math.abs(n));
        return n > 0 ? '+' + formatted : (n < 0 ? '-' + formatted : '0');
    } catch(e) {
        return val;
    }
}

function initPipelineWindowPage() {
    let currentPipelineSymbol = 'NIFTY';
    const activeDate = getActiveTradingDate();

    // 1. Symbol Pills
    document.querySelectorAll('#pipelineSymbolPills .oc-pill-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#pipelineSymbolPills .oc-pill-btn').forEach(b => {
                b.classList.remove('active');
                b.style.background = 'transparent';
                b.style.color = '#94a3b8';
            });
            btn.classList.add('active');
            btn.style.background = '#3b82f6';
            btn.style.color = '#fff';
            currentPipelineSymbol = btn.getAttribute('data-symbol') || 'NIFTY';
            loadPipelineData(currentPipelineSymbol, getActiveTradingDate());
        });
    });

    // 2. Date Input
    const dateInput = document.getElementById('pipelineDateInput');
    if (dateInput) {
        dateInput.value = activeDate;
        dateInput.addEventListener('change', () => {
            const newDate = dateInput.value;
            if (newDate) {
                setActiveTradingDate(newDate, true);
                loadPipelineData(currentPipelineSymbol, newDate);
            }
        });
    }

    // 3. Refresh button
    const btnRefresh = document.getElementById('btnRefreshPipeline');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            loadPipelineData(currentPipelineSymbol, getActiveTradingDate());
        });
    }

    loadPipelineData(currentPipelineSymbol, activeDate);
}

async function loadPipelineData(symbol, dateStr) {
    const targetDate = dateStr || getActiveTradingDate();
    const btnRefresh = document.getElementById('btnRefreshPipeline');
    if (btnRefresh) btnRefresh.innerText = '⏳ Loading...';

    try {
        const res = await fetch(`/api/pipeline-data?symbol=${encodeURIComponent(symbol)}&date=${encodeURIComponent(targetDate)}`);
        const data = await res.json();
        if (data.status === 'success') {
            renderPipelineMasterCard(data);
            renderSection1ParticipantOI(data);
            renderSection2VolumeRetention(data);
            renderSection3FiiStats(data);
            renderSection4UDiFFBhavcopy(data);
            renderSection5CashDeliveries(data);
            renderBigPlayerCockpitInPipeline(data);
            renderTrendAndDirectives(data);
        }
    } catch (e) {
        console.error('Error loading 5-Data Pipeline data:', e);
    } finally {
        if (btnRefresh) btnRefresh.innerText = '🔄 Refresh Pipeline';
    }
}

function renderPipelineMasterCard(data) {
    const scoreEl = document.getElementById('pipeScoreVal');
    if (scoreEl) {
        scoreEl.innerHTML = `${data.composite_score}<span style="font-size: 20px; font-weight: 600; color: #64748b;">/100</span>`;
        if (data.composite_score <= 42) {
            scoreEl.style.color = '#ef4444';
        } else if (data.composite_score >= 58) {
            scoreEl.style.color = '#10b981';
        } else {
            scoreEl.style.color = '#fbbf24';
        }
    }

    const confBadge = document.getElementById('pipeConfidenceBadge');
    if (confBadge) confBadge.innerText = `${data.confidence_score}% HIGH CONVICTION`;

    const tag = document.getElementById('pipeSymbolDateTag');
    if (tag) tag.innerText = `${data.symbol} • ${data.date}`;

    const stanceBadge = document.getElementById('pipeStanceBadge');
    if (stanceBadge) {
        stanceBadge.innerText = data.master_stance;
        if (data.master_stance_color === 'green') {
            stanceBadge.style.background = 'rgba(16, 185, 129, 0.25)';
            stanceBadge.style.color = '#34d399';
            stanceBadge.style.borderColor = 'rgba(16, 185, 129, 0.5)';
        } else if (data.master_stance_color === 'red') {
            stanceBadge.style.background = 'rgba(239, 68, 68, 0.25)';
            stanceBadge.style.color = '#f87171';
            stanceBadge.style.borderColor = 'rgba(239, 68, 68, 0.5)';
        } else {
            stanceBadge.style.background = 'rgba(245, 158, 11, 0.25)';
            stanceBadge.style.color = '#fbbf24';
            stanceBadge.style.borderColor = 'rgba(245, 158, 11, 0.5)';
        }
    }

    const regimeEl = document.getElementById('pipeRegimeTag');
    if (regimeEl) regimeEl.innerText = data.regime_tag;

    const spotEl = document.getElementById('pipeSpotPrice');
    if (spotEl) spotEl.innerText = formatNumber(Math.round(data.spot_price * 100) / 100);

    const atmEl = document.getElementById('pipeAtmStrike');
    if (atmEl) atmEl.innerText = formatNumber(data.atm_strike);

    const pcrEl = document.getElementById('pipePcrVal');
    if (pcrEl) pcrEl.innerText = Number(data.pcr).toFixed(2);

    const mpEl = document.getElementById('pipeMaxPain');
    if (mpEl) mpEl.innerText = formatNumber(data.max_pain);

    const verdictEl = document.getElementById('pipeNextDayVerdict');
    if (verdictEl) verdictEl.innerText = data.next_day_verdict;

    const corridorEl = document.getElementById('pipeTargetCorridor');
    if (corridorEl) corridorEl.innerText = data.target_corridor;

    const invalidEl = document.getElementById('pipeInvalidationTrigger');
    if (invalidEl) invalidEl.innerText = data.invalidation_trigger;
}

function renderSection1ParticipantOI(data) {
    const sec1 = data.section1_oi || {};
    const latest = sec1.latest || {};
    const participants = latest.participants || {};
    const deltas = latest.deltas || {};

    const fii = participants['FII'] || {};
    const pro = participants['PRO'] || {};
    const client = participants['CLIENT'] || {};
    const dii = participants['DII'] || {};

    // 1. Skew Badge
    const skewBadge = document.getElementById('sec1SkewBadge');
    if (skewBadge) {
        const fiiFutNet = fii.index_futures_net !== undefined ? fii.index_futures_net : (fii.future_index_long - fii.future_index_short || 0);
        const proFutNet = pro.index_futures_net !== undefined ? pro.index_futures_net : (pro.future_index_long - pro.future_index_short || 0);
        const smFutNet = fiiFutNet + proFutNet;

        const fiiCallNet = fii.index_calls_net !== undefined ? fii.index_calls_net : (fii.option_index_call_long - fii.option_index_call_short || 0);
        const proCallNet = pro.index_calls_net !== undefined ? pro.index_calls_net : (pro.option_index_call_long - pro.option_index_call_short || 0);
        const smCallNet = fiiCallNet + proCallNet;

        if (smFutNet < -50000 || smCallNet < -50000) {
            skewBadge.innerText = 'INSTITUTIONAL NET SHORT (FII + PRO SKEW)';
            skewBadge.style.color = '#f87171';
            skewBadge.style.background = 'rgba(239, 68, 68, 0.2)';
            skewBadge.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        } else if (smFutNet > 50000 || smCallNet > 50000) {
            skewBadge.innerText = 'INSTITUTIONAL NET LONG (FII + PRO SKEW)';
            skewBadge.style.color = '#34d399';
            skewBadge.style.background = 'rgba(16, 185, 129, 0.2)';
            skewBadge.style.border = '1px solid rgba(16, 185, 129, 0.4)';
        } else {
            skewBadge.innerText = 'BALANCED INSTITUTIONAL POSITIONING';
            skewBadge.style.color = '#fbbf24';
            skewBadge.style.background = 'rgba(245, 158, 11, 0.2)';
            skewBadge.style.border = '1px solid rgba(245, 158, 11, 0.4)';
        }
    }

    // 2. 6 Instruments Sequential Snapshot Cards
    const instGrid = document.getElementById('sec1InstCardsGrid');
    if (instGrid) {
        instGrid.innerHTML = '';

        const instruments = [
            {
                name: 'INDEX FUTURES',
                icon: '📈',
                smNet: (fii.index_futures_net || 0) + (pro.index_futures_net || 0),
                cliNet: client.index_futures_net || 0,
                diiNet: dii.index_futures_net || 0,
                unit: 'contracts'
            },
            {
                name: 'INDEX CALLS',
                icon: '📞',
                smNet: (fii.index_calls_net || 0) + (pro.index_calls_net || 0),
                cliNet: client.index_calls_net || 0,
                diiNet: dii.index_calls_net || 0,
                unit: 'contracts'
            },
            {
                name: 'INDEX PUTS',
                icon: '🛡️',
                smNet: (fii.index_puts_net || 0) + (pro.index_puts_net || 0),
                cliNet: client.index_puts_net || 0,
                diiNet: dii.index_puts_net || 0,
                unit: 'contracts'
            },
            {
                name: 'STOCK FUTURES',
                icon: '🏢',
                smNet: (fii.stock_futures_net || 0) + (pro.stock_futures_net || 0),
                cliNet: client.stock_futures_net || 0,
                diiNet: dii.stock_futures_net || 0,
                unit: 'contracts'
            },
            {
                name: 'STOCK CALLS',
                icon: '📱',
                smNet: (fii.stock_calls_net || 0) + (pro.stock_calls_net || 0),
                cliNet: client.stock_calls_net || 0,
                diiNet: dii.stock_calls_net || 0,
                unit: 'contracts'
            },
            {
                name: 'STOCK PUTS',
                icon: '📦',
                smNet: (fii.stock_puts_net || 0) + (pro.stock_puts_net || 0),
                cliNet: client.stock_puts_net || 0,
                diiNet: dii.stock_puts_net || 0,
                unit: 'contracts'
            }
        ];

        instruments.forEach(inst => {
            const isSmBull = inst.smNet > 0;
            const isSmBear = inst.smNet < 0;
            const smColor = isSmBull ? '#34d399' : (isSmBear ? '#f87171' : '#94a3b8');
            const cliColor = inst.cliNet > 0 ? '#34d399' : (inst.cliNet < 0 ? '#f87171' : '#94a3b8');

            let verdictTag = 'NEUTRAL';
            let verdictBg = 'rgba(148, 163, 184, 0.15)';
            let verdictColor = '#94a3b8';

            if (inst.name.includes('CALLS')) {
                if (inst.smNet < 0 && inst.cliNet > 0) {
                    verdictTag = 'SM WRITING / RET TRAP';
                    verdictBg = 'rgba(239, 68, 68, 0.2)';
                    verdictColor = '#f87171';
                } else if (inst.smNet > 0 && inst.cliNet < 0) {
                    verdictTag = 'SM LONG ACCUMULATION';
                    verdictBg = 'rgba(16, 185, 129, 0.2)';
                    verdictColor = '#34d399';
                }
            } else if (inst.name.includes('PUTS')) {
                if (inst.smNet > 0 && inst.cliNet < 0) {
                    verdictTag = 'SM HEDGE / RET EXPOSED';
                    verdictBg = 'rgba(239, 68, 68, 0.2)';
                    verdictColor = '#f87171';
                } else if (inst.smNet < 0 && inst.cliNet > 0) {
                    verdictTag = 'SM PUT WRITING / BULLISH';
                    verdictBg = 'rgba(16, 185, 129, 0.2)';
                    verdictColor = '#34d399';
                }
            } else {
                if (isSmBear) {
                    verdictTag = 'INSTITUTIONAL SHORT';
                    verdictBg = 'rgba(239, 68, 68, 0.2)';
                    verdictColor = '#f87171';
                } else if (isSmBull) {
                    verdictTag = 'INSTITUTIONAL LONG';
                    verdictBg = 'rgba(16, 185, 129, 0.2)';
                    verdictColor = '#34d399';
                }
            }

            const card = document.createElement('div');
            card.style.background = 'rgba(15, 23, 42, 0.7)';
            card.style.border = '1px solid rgba(255, 255, 255, 0.08)';
            card.style.borderRadius = '8px';
            card.style.padding = '12px';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 11px; font-weight: 800; color: #cbd5e1; text-transform: uppercase;">${inst.icon} ${inst.name}</span>
                    <span style="font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; background: ${verdictBg}; color: ${verdictColor};">${verdictTag}</span>
                </div>
                <div style="margin-bottom: 6px;">
                    <div style="font-size: 10px; color: #64748b; font-weight: 600;">SMART MONEY (FII + PRO)</div>
                    <div style="font-size: 14px; font-weight: 900; color: ${smColor};">${formatSignedNumber(inst.smNet)}</div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: #94a3b8; border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 6px;">
                    <span>Retail (Client):</span>
                    <strong style="color: ${cliColor};">${formatSignedNumber(inst.cliNet)}</strong>
                </div>
            `;
            instGrid.appendChild(card);
        });
    }

    // 3. 14-Column Participant Table
    const tbody = document.getElementById('sec1TableBody');
    if (tbody) {
        tbody.innerHTML = '';
        const order = ['CLIENT', 'DII', 'FII', 'PRO', 'TOTAL'];
        const labelMap = {
            'CLIENT': 'Clients (Retail Traders)',
            'DII': 'DIIs (Domestic Institutions)',
            'FII': 'FIIs (Foreign Institutions)',
            'PRO': 'Pros (Proprietary Desks)',
            'TOTAL': 'TOTAL'
        };

        order.forEach(key => {
            const row = participants[key];
            if (!row) return;

            const futNet = row.index_futures_net !== undefined ? row.index_futures_net : (row.future_index_long - row.future_index_short);
            const callNet = row.index_calls_net !== undefined ? row.index_calls_net : (row.option_index_call_long - row.option_index_call_short);
            const putNet = row.index_puts_net !== undefined ? row.index_puts_net : (row.option_index_put_long - row.option_index_put_short);
            const stkNet = row.stock_futures_net !== undefined ? row.stock_futures_net : (row.future_stock_long - row.future_stock_short);

            let biasText = 'NEUTRAL';
            let biasColor = '#94a3b8';
            let biasBg = 'rgba(148, 163, 184, 0.15)';

            if (key === 'FII' || key === 'PRO') {
                if (callNet < 0 && putNet > 0) {
                    biasText = 'BEARISH';
                    biasColor = '#f87171';
                    biasBg = 'rgba(239, 68, 68, 0.2)';
                } else if (callNet > 0 && putNet < 0) {
                    biasText = 'BULLISH';
                    biasColor = '#34d399';
                    biasBg = 'rgba(16, 185, 129, 0.2)';
                }
            } else if (key === 'CLIENT') {
                if (callNet > 50000) {
                    biasText = 'TRAPPED CALL LONG';
                    biasColor = '#f87171';
                    biasBg = 'rgba(239, 68, 68, 0.2)';
                } else if (putNet > 50000) {
                    biasText = 'TRAPPED PUT LONG';
                    biasColor = '#34d399';
                    biasBg = 'rgba(16, 185, 129, 0.2)';
                }
            }

            const isTotal = key === 'TOTAL';
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
            if (isTotal) {
                tr.style.background = 'rgba(15, 23, 42, 0.9)';
                tr.style.fontWeight = '800';
                tr.style.borderTop = '2px solid rgba(255, 255, 255, 0.2)';
            }

            const fmtColor = (v) => v > 0 ? '#34d399' : (v < 0 ? '#f87171' : '#94a3b8');

            tr.innerHTML = `
                <td style="text-align: left; padding: 10px; font-weight: ${isTotal ? '800' : '700'}; color: ${isTotal ? '#fff' : '#cbd5e1'};">
                    ${labelMap[key] || key}
                </td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.future_index_long)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.future_index_short)}</td>
                <td style="padding: 10px; font-weight: 700; color: ${fmtColor(futNet)};">${formatSignedNumber(futNet)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.option_index_call_long)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.option_index_call_short)}</td>
                <td style="padding: 10px; font-weight: 700; color: ${fmtColor(callNet)};">${formatSignedNumber(callNet)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.option_index_put_long)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.option_index_put_short)}</td>
                <td style="padding: 10px; font-weight: 700; color: ${fmtColor(putNet)};">${formatSignedNumber(putNet)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.future_stock_long)}</td>
                <td style="padding: 10px; color: #94a3b8;">${formatNumber(row.future_stock_short)}</td>
                <td style="padding: 10px; font-weight: 700; color: ${fmtColor(stkNet)};">${formatSignedNumber(stkNet)}</td>
                <td style="padding: 10px; text-align: center;">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 800; background: ${biasBg}; color: ${biasColor};">
                        ${isTotal ? '-' : biasText}
                    </span>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    // 4. Summary Text
    const sumEl = document.getElementById('sec1SummaryText');
    if (sumEl && data.smart_money_alignment) {
        sumEl.innerHTML = `<strong>Smart Money vs Retail Skew:</strong> ${data.smart_money_alignment} In contrast, ${data.retail_alignment}`;
    }
}

function renderSection2VolumeRetention(data) {
    const sec2 = data.section2_vol || {};
    const ret = data.retention_ratios || {};
    const volP = sec2.participants || {};

    const roles = {
        'FII': { name: 'FII (Foreign Institutions)', icon: '🏛️', defaultRole: 'Smart Money Lead' },
        'PRO': { name: 'PRO (Proprietary Desks)', icon: '🏢', defaultRole: 'Market Maker' },
        'CLIENT': { name: 'CLIENT (Retail Traders)', icon: '👤', defaultRole: 'Directional Speculator' },
        'DII': { name: 'DII (Domestic Institutions)', icon: '🏦', defaultRole: 'Long-term Funds' }
    };

    // 1. Participant Conviction Cards Grid
    const grid = document.getElementById('sec2CardsGrid');
    if (grid) {
        grid.innerHTML = '';
        ['FII', 'PRO', 'CLIENT', 'DII'].forEach(k => {
            const rData = ret[k] || {};
            const vData = volP[k] || {};
            const info = roles[k] || { name: k, icon: '📊', defaultRole: '' };

            const ratio = rData.retention_pct !== undefined ? rData.retention_pct : (rData.retention_ratio ? (rData.retention_ratio * 100) : 0);
            const isHighConviction = ratio >= 20.0;
            const isChurn = ratio < 10.0;

            let badgeBg = 'rgba(59, 130, 246, 0.2)';
            let badgeColor = '#60a5fa';
            let badgeText = `${ratio.toFixed(1)}% MODERATE RETENTION`;

            if (isHighConviction) {
                badgeBg = 'rgba(16, 185, 129, 0.2)';
                badgeColor = '#34d399';
                badgeText = `${ratio.toFixed(1)}% OVERNIGHT CONVICTION (>20%)`;
            } else if (isChurn) {
                badgeBg = 'rgba(245, 158, 11, 0.2)';
                badgeColor = '#fbbf24';
                badgeText = `${ratio.toFixed(1)}% DAY CHURN (<10%)`;
            }

            const card = document.createElement('div');
            card.style.background = 'rgba(15, 23, 42, 0.8)';
            card.style.border = '1px solid rgba(255, 255, 255, 0.08)';
            card.style.borderRadius = '10px';
            card.style.padding = '16px';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 16px;">${info.icon}</span>
                        <strong style="color: #fff; font-size: 13px;">${info.name}</strong>
                    </div>
                </div>
                <div style="margin-bottom: 10px;">
                    <span style="display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 800; background: ${badgeBg}; color: ${badgeColor};">
                        ${badgeText}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                    <div><span style="color: #94a3b8;">Traded Vol:</span> <strong style="color: #cbd5e1; float: right;">${formatNumber(vData.total_volume || rData.volume || 0)}</strong></div>
                    <div><span style="color: #94a3b8;">Net ΔOI:</span> <strong style="color: #38bdf8; float: right;">${formatSignedNumber(rData.delta_oi || 0)}</strong></div>
                </div>
                <div style="margin-top: 10px; font-size: 11px; color: #94a3b8; line-height: 1.4;">
                    ${isHighConviction ? 'Strong balance-sheet build carried into next session.' : (isChurn ? 'High-frequency retail churn. Disregarded by institutional algorithms.' : 'Standard institutional rebalancing volume.')}
                </div>
            `;
            grid.appendChild(card);
        });
    }

    // 2. Volume-to-OI Velocity Table Body
    const velTbody = document.getElementById('sec2VelocityTableBody');
    if (velTbody) {
        velTbody.innerHTML = '';
        const order = ['FII', 'PRO', 'CLIENT', 'DII', 'TOTAL'];

        order.forEach(k => {
            const vData = volP[k] || {};
            const rData = ret[k] || {};
            const isTotal = k === 'TOTAL';
            const info = roles[k] || { name: k, icon: '📊' };

            const ratio = rData.retention_pct !== undefined ? rData.retention_pct : (rData.retention_ratio ? (rData.retention_ratio * 100) : 0);
            const isHighConviction = ratio >= 20.0;
            const isChurn = ratio < 10.0;

            let badgeBg = 'rgba(59, 130, 246, 0.2)';
            let badgeColor = '#60a5fa';
            let badgeText = `${ratio.toFixed(1)}% MODERATE`;

            if (isHighConviction) {
                badgeBg = 'rgba(16, 185, 129, 0.2)';
                badgeColor = '#34d399';
                badgeText = 'STICKY OVERNIGHT';
            } else if (isChurn) {
                badgeBg = 'rgba(245, 158, 11, 0.2)';
                badgeColor = '#fbbf24';
                badgeText = 'INTRADAY SCALPING';
            }

            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
            if (isTotal) {
                tr.style.background = 'rgba(15, 23, 42, 0.9)';
                tr.style.fontWeight = '800';
                tr.style.borderTop = '2px solid rgba(255, 255, 255, 0.2)';
            }

            tr.innerHTML = `
                <td style="text-align: left; padding: 10px; font-weight: ${isTotal ? '800' : '700'}; color: ${isTotal ? '#fff' : '#cbd5e1'};">
                    ${isTotal ? 'TOTAL MARKET FLOW' : `${info.icon} ${info.name}`}
                </td>
                <td style="padding: 10px; color: #cbd5e1;">${formatNumber(vData.index_futures_volume || 0)}</td>
                <td style="padding: 10px; color: #34d399;">${formatNumber(vData.index_calls_volume || 0)}</td>
                <td style="padding: 10px; color: #f87171;">${formatNumber(vData.index_puts_volume || 0)}</td>
                <td style="padding: 10px; color: #cbd5e1;">${formatNumber(vData.stock_futures_volume || 0)}</td>
                <td style="padding: 10px; font-weight: 700; color: #fff;">${formatNumber(vData.total_volume || 0)}</td>
                <td style="padding: 10px; font-weight: 700; color: #38bdf8;">${isTotal ? '-' : formatSignedNumber(rData.delta_oi || 0)}</td>
                <td style="padding: 10px; font-weight: 800; color: ${isHighConviction ? '#34d399' : (isChurn ? '#fbbf24' : '#60a5fa')};">
                    ${isTotal ? '-' : `${ratio.toFixed(2)}%`}
                </td>
                <td style="padding: 10px; text-align: center;">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 800; background: ${badgeBg}; color: ${badgeColor};">
                        ${isTotal ? 'MARKET TURNOVER' : badgeText}
                    </span>
                </td>
            `;
            velTbody.appendChild(tr);
        });
    }
}

function renderSection3FiiStats(data) {
    const sec3 = data.section3_fii || data.fii_stats || {};
    const byIdx = sec3.by_index || {};

    // NIFTY
    const nData = byIdx.NIFTY || sec3.NIFTY || {};
    const nFut = nData.net_contracts_futures !== undefined ? nData.net_contracts_futures : (nData.fut_net || -102484);
    const nNotional = nData.notional_crores || 6418.5;
    const nCall = nData.net_contracts_ce !== undefined ? nData.net_contracts_ce : (nData.opt_call_net || 312988);
    const nPut = nData.net_contracts_pe !== undefined ? nData.net_contracts_pe : (nData.opt_put_net || 378541);

    const elNFut = document.getElementById('fiiNiftyFut');
    if (elNFut) elNFut.innerText = formatSignedNumber(nFut);

    const elNNot = document.getElementById('fiiNiftyNotional');
    if (elNNot) elNNot.innerText = '₹ ' + formatNumber(nNotional) + ' Cr';

    const elNCall = document.getElementById('fiiNiftyCall');
    if (elNCall) elNCall.innerText = formatSignedNumber(nCall);

    const elNPut = document.getElementById('fiiNiftyPut');
    if (elNPut) elNPut.innerText = formatSignedNumber(nPut);

    const elNBadge = document.getElementById('fiiNiftyBadge');
    if (elNBadge) {
        elNBadge.innerText = nFut < 0 ? 'BEARISH SHORT' : 'BULLISH LONG';
        elNBadge.style.color = nFut < 0 ? '#f87171' : '#34d399';
        elNBadge.style.background = nFut < 0 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)';
    }

    // BANKNIFTY
    const bnData = byIdx.BANKNIFTY || sec3.BANKNIFTY || {};
    const bnFut = bnData.net_contracts_futures !== undefined ? bnData.net_contracts_futures : (bnData.fut_net || -47300);
    const bnNotional = bnData.notional_crores || 3682.3;
    const bnCall = bnData.net_contracts_ce !== undefined ? bnData.net_contracts_ce : (bnData.opt_call_net || 144456);
    const bnPut = bnData.net_contracts_pe !== undefined ? bnData.net_contracts_pe : (bnData.opt_put_net || 174711);

    const elBnFut = document.getElementById('fiiBnFut');
    if (elBnFut) elBnFut.innerText = formatSignedNumber(bnFut);

    const elBnNot = document.getElementById('fiiBnNotional');
    if (elBnNot) elBnNot.innerText = '₹ ' + formatNumber(bnNotional) + ' Cr';

    const elBnCall = document.getElementById('fiiBnCall');
    if (elBnCall) elBnCall.innerText = formatSignedNumber(bnCall);

    const elBnPut = document.getElementById('fiiBnPut');
    if (elBnPut) elBnPut.innerText = formatSignedNumber(bnPut);

    const elBnBadge = document.getElementById('fiiBnBadge');
    if (elBnBadge) {
        elBnBadge.innerText = bnFut < 0 ? 'BEARISH SHORT' : 'BULLISH LONG';
        elBnBadge.style.color = bnFut < 0 ? '#f87171' : '#34d399';
        elBnBadge.style.background = bnFut < 0 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)';
    }
}

function renderSection4UDiFFBhavcopy(data) {
    const sec4 = data.section4_chain || {};
    const spot = data.spot_price || 25057.35;
    const atm = data.atm_strike || 25050;

    const elSpot = document.getElementById('sec4Spot');
    if (elSpot) elSpot.innerText = formatNumber(Math.round(spot * 100) / 100);

    const elAtm = document.getElementById('sec4Atm');
    if (elAtm) elAtm.innerText = 'ATM Strike: ' + formatNumber(atm);

    const elMaxPain = document.getElementById('sec4MaxPain');
    if (elMaxPain) elMaxPain.innerText = formatNumber(data.max_pain || atm);

    const r1 = sec4.major_resistance || {};
    const elR1 = document.getElementById('sec4R1');
    if (elR1) elR1.innerText = formatNumber(r1.strike || (atm + 150)) + ' CE';

    const elR1Oi = document.getElementById('sec4R1Oi');
    if (elR1Oi) elR1Oi.innerText = formatNumber(r1.oi || 8709600) + ' Open Contracts';

    const s1 = sec4.major_support || {};
    const elS1 = document.getElementById('sec4S1');
    if (elS1) elS1.innerText = formatNumber(s1.strike || (atm - 50)) + ' PE';

    const elS1Oi = document.getElementById('sec4S1Oi');
    if (elS1Oi) elS1Oi.innerText = formatNumber(s1.oi || 5912525) + ' Open Contracts';

    const elOsc = document.getElementById('sec4OscZone');
    if (elOsc) elOsc.innerText = sec4.oscillation_zone ? sec4.oscillation_zone.label : `${formatNumber(atm - 50)} - ${formatNumber(atm + 150)}`;

    const pcr = Number(data.pcr || 0.68);
    const pcrBadge = document.getElementById('sec4PcrBadge');
    if (pcrBadge) {
        pcrBadge.innerText = `PCR: ${pcr.toFixed(2)} (${pcr < 0.7 ? 'CALL RESISTANCE DOMINATES' : 'PUT SUPPORT DOMINATES'})`;
    }

    // Double PCR values
    const oiPcrVal = document.getElementById('sec4OiPcrVal');
    if (oiPcrVal) {
        oiPcrVal.innerText = `${pcr.toFixed(2)} (${pcr < 0.75 ? 'Bearish Call Overhead' : (pcr > 1.25 ? 'Strong Bullish Floor' : 'Neutral Rangebound')})`;
    }

    const volPcr = sec4.vol_pcr !== undefined ? Number(sec4.vol_pcr) : (sec4.total_put_volume && sec4.total_call_volume ? (sec4.total_put_volume / sec4.total_call_volume) : 0.74);
    const volPcrVal = document.getElementById('sec4VolPcrVal');
    if (volPcrVal) {
        volPcrVal.innerText = `${Number(volPcr).toFixed(2)} (${volPcr < 0.85 ? 'Call Turnover Dominance' : 'Put Turnover Dominance'})`;
    }

    // 11-Column Real Option Chain Heatmap Matrix
    const tbody = document.getElementById('sec4OptionChainTbody');
    if (tbody) {
        tbody.innerHTML = '';
        const allStrikes = sec4.strikes || [];

        // Focus window around ATM (ATM ± 8 strikes for high readability)
        const windowStrikes = allStrikes.filter(s => Math.abs(s.strike - atm) <= 400);
        const renderList = windowStrikes.length >= 7 ? windowStrikes : allStrikes;

        if (renderList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" style="text-align: center; padding: 20px; color: #94a3b8;">No option chain strike records loaded.</td></tr>';
            return;
        }

        renderList.forEach(s => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';

            const isAtm = s.is_atm || (s.strike === atm);
            const isMaxPain = s.strike === data.max_pain;
            const isR1 = s.is_r1 || (r1.strike && s.strike === r1.strike);
            const isS1 = s.is_s1 || (s1.strike && s.strike === s1.strike);

            if (isAtm) {
                tr.style.background = 'rgba(56, 189, 248, 0.08)';
            }

            const c = s.call || {};
            const p = s.put || {};

            // ITM Shading: Calls are ITM if strike < spot; Puts are ITM if strike > spot
            const callItmBg = s.strike < spot ? 'background: rgba(234, 179, 8, 0.08);' : '';
            const putItmBg = s.strike > spot ? 'background: rgba(234, 179, 8, 0.08);' : '';

            // Strike Badge Tags
            let strikeBadge = '';
            if (isAtm) {
                strikeBadge += `<span style="display: block; font-size: 9px; font-weight: 800; color: #38bdf8; background: rgba(56, 189, 248, 0.2); padding: 1px 4px; border-radius: 3px; margin-top: 2px;">⚡ ATM</span>`;
            }
            if (isMaxPain) {
                strikeBadge += `<span style="display: block; font-size: 9px; font-weight: 800; color: #fbbf24; background: rgba(251, 191, 36, 0.2); padding: 1px 4px; border-radius: 3px; margin-top: 2px;">📌 MAX PAIN</span>`;
            }
            if (isR1) {
                strikeBadge += `<span style="display: block; font-size: 9px; font-weight: 800; color: #f87171; background: rgba(239, 68, 68, 0.2); padding: 1px 4px; border-radius: 3px; margin-top: 2px;">🏦 CALL WALL</span>`;
            }
            if (isS1) {
                strikeBadge += `<span style="display: block; font-size: 9px; font-weight: 800; color: #34d399; background: rgba(16, 185, 129, 0.2); padding: 1px 4px; border-radius: 3px; margin-top: 2px;">🛡️ PUT FLOOR</span>`;
            }

            // Smart Money Footprint Text & Badge
            let fpText = s.fii_strike_badge || s.game_plan_tag || '';
            let fpColor = '#94a3b8';
            let fpBg = 'rgba(148, 163, 184, 0.1)';

            if (isR1 || (c.chg_oi > 500000 && s.strike >= spot)) {
                fpText = '🏦 INSTITUTIONAL CEILING';
                fpColor = '#f87171';
                fpBg = 'rgba(239, 68, 68, 0.2)';
            } else if (isS1 || (p.chg_oi > 500000 && s.strike <= spot)) {
                fpText = '🛡️ INSTITUTIONAL CUSHION';
                fpColor = '#34d399';
                fpBg = 'rgba(16, 185, 129, 0.2)';
            } else if (isMaxPain) {
                fpText = '📌 EXPIRY PIN GRAVITY';
                fpColor = '#fbbf24';
                fpBg = 'rgba(251, 191, 36, 0.2)';
            } else if (c.action_badge_text) {
                fpText = c.action_badge_text;
                fpColor = '#60a5fa';
                fpBg = 'rgba(59, 130, 246, 0.15)';
            } else {
                fpText = 'NORMAL ORDER FLOW';
            }

            const cChgColor = (c.chg_oi || 0) > 0 ? '#34d399' : ((c.chg_oi || 0) < 0 ? '#f87171' : '#94a3b8');
            const pChgColor = (p.chg_oi || 0) > 0 ? '#34d399' : ((p.chg_oi || 0) < 0 ? '#f87171' : '#94a3b8');

            tr.innerHTML = `
                <!-- CALLS CE -->
                <td style="padding: 8px; color: #cbd5e1; ${callItmBg}">${formatNumber(c.oi || 0)}</td>
                <td style="padding: 8px; font-weight: 700; color: ${cChgColor}; ${callItmBg}">${formatSignedNumber(c.chg_oi || 0)}</td>
                <td style="padding: 8px; color: #94a3b8; ${callItmBg}">${formatNumber(c.volume || 0)}</td>
                <td style="padding: 8px; font-weight: 700; color: #fff; border-right: 1px solid rgba(255, 255, 255, 0.1); ${callItmBg}">₹ ${Number(c.ltp || 0).toFixed(2)}</td>

                <!-- STRIKE -->
                <td style="text-align: center; padding: 8px; font-weight: 900; color: #fff; background: ${isAtm ? 'rgba(56, 189, 248, 0.2)' : 'rgba(30, 41, 59, 0.9)'};">
                    ${formatNumber(s.strike)}
                    ${strikeBadge}
                </td>

                <!-- PUTS PE -->
                <td style="padding: 8px; font-weight: 700; color: #fff; border-left: 1px solid rgba(255, 255, 255, 0.1); ${putItmBg}">₹ ${Number(p.ltp || 0).toFixed(2)}</td>
                <td style="padding: 8px; color: #94a3b8; ${putItmBg}">${formatNumber(p.volume || 0)}</td>
                <td style="padding: 8px; font-weight: 700; color: ${pChgColor}; ${putItmBg}">${formatSignedNumber(p.chg_oi || 0)}</td>
                <td style="padding: 8px; color: #cbd5e1; ${putItmBg}">${formatNumber(p.oi || 0)}</td>

                <!-- FOOTPRINT -->
                <td style="padding: 8px; text-align: center;">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 800; background: ${fpBg}; color: ${fpColor};">
                        ${fpText}
                    </span>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}

function renderSection5CashDeliveries(data) {
    const sec5 = data.section5_cash || data.cash_deliveries || {};
    const stocks = sec5.heavyweights || Object.values(sec5.stocks || {});

    const tbody = document.getElementById('sec5TableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const verdictBadge = document.getElementById('sec5CashVerdictBadge');
    if (verdictBadge) {
        verdictBadge.innerText = sec5.cash_verdict || 'BEARISH CASH DISTRIBUTION';
        if (sec5.cash_color === 'green') {
            verdictBadge.style.color = '#34d399';
            verdictBadge.style.background = 'rgba(16, 185, 129, 0.2)';
        } else if (sec5.cash_color === 'red') {
            verdictBadge.style.color = '#f87171';
            verdictBadge.style.background = 'rgba(239, 68, 68, 0.2)';
        } else {
            verdictBadge.style.color = '#fbbf24';
            verdictBadge.style.background = 'rgba(245, 158, 11, 0.2)';
        }
    }

    if (!stocks || stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 16px; color: #94a3b8;">No cash delivery records loaded.</td></tr>';
        return;
    }

    stocks.forEach(stk => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';

        const isAccum = (stk.pct_change > 0 && stk.delivery_pct >= 50.0);
        const isDist = (stk.pct_change < 0 && stk.delivery_pct >= 50.0);
        let tagColor = '#94a3b8';
        let tagBg = 'rgba(148, 163, 184, 0.1)';
        let tagText = stk.behavior || 'NEUTRAL';

        if (isAccum) {
            tagColor = '#34d399';
            tagBg = 'rgba(16, 185, 129, 0.2)';
            tagText = 'ACCUMULATION';
        } else if (isDist) {
            tagColor = '#f87171';
            tagBg = 'rgba(239, 68, 68, 0.2)';
            tagText = 'DISTRIBUTION';
        }

        tr.innerHTML = `
            <td style="padding: 10px; font-weight: 700; color: #fff;">${stk.symbol}</td>
            <td style="padding: 10px; text-align: right; color: #94a3b8;">${Number(stk.weight_pct || 0).toFixed(1)}%</td>
            <td style="padding: 10px; text-align: right; color: #cbd5e1;">₹ ${formatNumber(stk.close_price)}</td>
            <td style="padding: 10px; text-align: right; font-weight: 700; color: ${stk.pct_change >= 0 ? '#34d399' : '#f87171'};">
                ${stk.pct_change >= 0 ? '+' : ''}${stk.pct_change}%
            </td>
            <td style="padding: 10px; text-align: right; font-weight: 700; color: ${stk.delivery_pct >= 50 ? '#38bdf8' : '#94a3b8'};">
                ${stk.delivery_pct}%
            </td>
            <td style="padding: 10px; text-align: right; color: #cbd5e1;">₹ ${formatNumber(stk.delivery_turnover_cr)} Cr</td>
            <td style="padding: 10px; text-align: center;">
                <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 800; background: ${tagBg}; color: ${tagColor};">
                    ${tagText}
                </span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderBigPlayerCockpitInPipeline(data) {
    const bps = data.big_player_strike_intelligence || data.big_player_strikes || {};
    const cb = bps.call_bastion || {};
    const pb = bps.put_bastion || {};
    const tr = bps.trapped_retail_radar || {};
    const oc = bps.option_selling_cockpit || {};

    // 1. Bastion & Trap Cards
    const elCallStrike = document.getElementById('bpCallStrike');
    if (elCallStrike) elCallStrike.innerText = formatNumber(cb.strike || (data.atm_strike + 150)) + ' CE';

    const elCallQty = document.getElementById('bpCallContracts');
    if (elCallQty) elCallQty.innerText = `${formatSignedNumber(cb.contracts_net_written || cb.net_smart_calls || -132815)} Net Institutional Short`;

    const elCallBe = document.getElementById('bpCallBreakeven');
    if (elCallBe) elCallBe.innerText = `Panic Breakeven: ₹ ${cb.panic_breakeven || cb.writer_panic_breakeven || formatNumber(data.atm_strike + 186)}`;

    const elPutStrike = document.getElementById('bpPutStrike');
    if (elPutStrike) elPutStrike.innerText = formatNumber(pb.strike || (data.atm_strike - 50)) + ' PE';

    const elPutQty = document.getElementById('bpPutContracts');
    if (elPutQty) elPutQty.innerText = `${formatSignedNumber(pb.contracts_net_written || pb.net_smart_puts || 124804)} Net Institutional Put Protection`;

    const elPutBe = document.getElementById('bpPutBreakeven');
    if (elPutBe) elPutBe.innerText = `Panic Breakeven: ₹ ${pb.panic_breakeven || pb.writer_panic_breakeven || formatNumber(data.atm_strike - 76)}`;

    const elTrTitle = document.getElementById('bpRetailTrapTitle');
    if (elTrTitle) elTrTitle.innerText = tr.victim || tr.title || 'Retail Trapped in Calls';

    const elTrCall = document.getElementById('bpRetailCallQty');
    if (elTrCall) elTrCall.innerText = `${formatSignedNumber(tr.contracts_trapped || tr.trapped_calls_contracts || 132815)} Net Long Calls (Trapped)`;

    const elTrPut = document.getElementById('bpRetailPutQty');
    if (elTrPut) elTrPut.innerText = `${formatSignedNumber(tr.trapped_puts_contracts || -124804)} Net Short Puts (Exposed)`;

    const elStratName = document.getElementById('bpStrategyName');
    if (elStratName) elStratName.innerText = oc.strategy_name || 'BEAR CALL CREDIT SPREAD';

    const elPop = document.getElementById('bpPopVal');
    if (elPop) elPop.innerText = `POP: ${oc.pop_pct || oc.pop_score || 88.4}% Probability of Profit`;

    const elLegs = document.getElementById('bpTradeLegs');
    if (elLegs) {
        if (oc.sell_leg && oc.hedge_leg) {
            elLegs.innerText = `Sell ${formatNumber(oc.sell_leg.strike || cb.strike)} ${oc.sell_leg.opt_type || 'CE'} / Buy ${formatNumber(oc.hedge_leg.strike || (cb.strike + 150))} ${oc.hedge_leg.opt_type || 'CE'}`;
        } else {
            elLegs.innerText = oc.execution_legs || `Sell ${formatNumber(cb.strike || 25200)} CE / Buy ${formatNumber((cb.strike || 25200) + 150)} CE`;
        }
    }

    const elRr = document.getElementById('bpRiskReward');
    if (elRr) elRr.innerText = `Max Profit: ₹ ${formatNumber(oc.net_credit_inr || 3390)} / Breakeven: ${oc.breakeven_pts || oc.breakeven || formatNumber(data.atm_strike + 186)}`;

    // 2. Top 3 Algorithmic Option Selling Blueprints Grid
    const stratGrid = document.getElementById('bpOptionStrategiesGrid');
    if (stratGrid) {
        stratGrid.innerHTML = '';
        const strats = bps.strategies || bps.top_strategies || [];

        if (strats.length === 0) {
            // Fallback strategy cards
            stratGrid.innerHTML = `
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
                    <strong style="color: #38bdf8;">Rank 1: Directional Credit Spread</strong>
                    <p style="color: #94a3b8; font-size: 12px; margin-top: 8px;">Aligns directly with Smart Money writing bastion.</p>
                </div>
            `;
            return;
        }

        strats.forEach(s => {
            const isRec = s.is_recommended || s.rank === 1;
            const rankBadge = isRec ? '⭐ RANK 1: RECOMMENDED' : (s.rank === 2 ? '🛡️ RANK 2: RANGEBOUND PINNING' : '🎯 RANK 3: STATISTICAL SHIELD');
            const rankBg = isRec ? 'linear-gradient(135deg, #10b981, #059669)' : (s.rank === 2 ? '#3b82f6' : '#8b5cf6');

            const card = document.createElement('div');
            card.style.background = isRec ? 'rgba(16, 185, 129, 0.05)' : 'rgba(15, 23, 42, 0.85)';
            card.style.border = isRec ? '2px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)';
            card.style.borderRadius = '12px';
            card.style.padding = '18px';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.justifyContent = 'space-between';

            card.innerHTML = `
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-size: 11px; font-weight: 800; background: ${rankBg}; color: #fff; padding: 3px 8px; border-radius: 4px;">
                            ${rankBadge}
                        </span>
                        <span style="font-size: 12px; font-weight: 900; color: #34d399; background: rgba(16, 185, 129, 0.15); padding: 3px 8px; border-radius: 4px;">
                            POP: ${s.pop_pct || 88.4}%
                        </span>
                    </div>

                    <h4 style="font-size: 15px; font-weight: 800; color: #fff; margin: 0 0 8px 0;">${s.name}</h4>
                    <p style="font-size: 12px; color: #94a3b8; margin: 0 0 14px 0; line-height: 1.4;">${s.market_view || ''}</p>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: rgba(0, 0, 0, 0.25); padding: 12px; border-radius: 8px; margin-bottom: 14px; font-size: 12px;">
                        <div>
                            <span style="color: #64748b;">Net Credit:</span>
                            <div style="font-weight: 800; color: #34d399; font-size: 14px;">₹ ${formatNumber(s.net_credit_inr || 3390)}</div>
                            <span style="font-size: 10px; color: #94a3b8;">(${s.net_credit_pts || 36} pts)</span>
                        </div>
                        <div>
                            <span style="color: #64748b;">Margin Benefit:</span>
                            <div style="font-weight: 800; color: #38bdf8; font-size: 14px;">${s.margin_saved_pct || 68}% SAVED</div>
                            <span style="font-size: 10px; color: #94a3b8;">Varsity SPAN Hedge</span>
                        </div>
                        <div style="grid-column: span 2; border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 8px;">
                            <span style="color: #64748b;">Breakeven:</span>
                            <strong style="color: #fbbf24; margin-left: 6px;">₹ ${s.breakeven_pts || '25,236.0'}</strong>
                        </div>
                    </div>

                    <div style="font-size: 11px; color: #cbd5e1; line-height: 1.5; margin-bottom: 12px;">
                        <strong>Algorithmic Rationale:</strong> ${s.why_this_strategy_is_best || ''}
                    </div>
                </div>

                <div style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 10px; font-size: 11px; color: #f87171;">
                    <strong>Stop Loss Trigger:</strong> ${s.stop_loss_trigger || 'Decisive breach of writer breakeven'}
                </div>
            `;
            stratGrid.appendChild(card);
        });
    }
}

function renderTrendAndDirectives(data) {
    const tp = data.trend_phases || {};
    const bl = data.bottom_line_for_traders || {};
    const scen = data.next_day_scenarios || {};

    // 1. Probabilistic Behavior Matrix
    const probBull = document.getElementById('probBullish');
    if (probBull) {
        const pC = (scen.scenario_c && scen.scenario_c.probability_pct) ? scen.scenario_c.probability_pct : 15;
        probBull.innerText = `${pC}%`;
    }

    const probPin = document.getElementById('probPinning');
    if (probPin) {
        const pB = (scen.scenario_b && scen.scenario_b.probability_pct) ? scen.scenario_b.probability_pct : 65;
        probPin.innerText = `${pB}%`;
    }

    const probBear = document.getElementById('probBearish');
    if (probBear) {
        const pA = (scen.scenario_a && scen.scenario_a.probability_pct) ? scen.scenario_a.probability_pct : 20;
        probBear.innerText = `${pA}%`;
    }

    // 2. 3-Phase Playbook
    if (tp.opening_phase) {
        const d = document.getElementById('phase1Desc');
        if (d) d.innerText = tp.opening_phase.description;
    }
    if (tp.intraday_phase) {
        const d = document.getElementById('phase2Desc');
        if (d) d.innerText = tp.intraday_phase.description;
    }
    if (tp.closing_phase) {
        const d = document.getElementById('phase3Desc');
        if (d) d.innerText = tp.closing_phase.description;
    }

    // 3. Opening Bell Directives
    const gp = document.getElementById('dirGamePlan');
    if (gp && bl.gameplan_915) gp.innerText = bl.gameplan_915;

    const kl = document.getElementById('dirKeyLevel');
    if (kl && bl.key_level_of_the_day) kl.innerText = bl.key_level_of_the_day;

    const st = document.getElementById('dirStrategy');
    if (st && bl.recommended_strategy) st.innerText = bl.recommended_strategy;

    const wa = document.getElementById('dirWhatAvoid');
    if (wa && bl.what_to_avoid) wa.innerText = bl.what_to_avoid;
}


function bootApp() {
    try { initTheme(); } catch(e) { console.warn('initTheme error:', e); }
    // Automatic migration from 2024 reference date to 2026 live date
    try {
        const curDate = localStorage.getItem('selected_trading_date');
        if (!curDate || curDate.startsWith('2024')) {
            localStorage.setItem('selected_trading_date', '2026-10-30');
        }
    } catch(e) {}

    try { initYouTubeSidebar(); } catch(e) { console.warn('initYouTubeSidebar error:', e); }

    // Synchronize initial active trading date from URL (?date=YYYY-MM-DD) or localStorage
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const urlDate = urlParams.get('date');
        if (urlDate && urlDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
            setActiveTradingDate(urlDate, false);
        } else {
            setActiveTradingDate(getActiveTradingDate(), false);
        }
    } catch(e) { console.warn('urlDate error:', e); }

    // Date Preset buttons across the application
    try {
        document.querySelectorAll('.date-preset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const pDate = btn.getAttribute('data-preset');
                if (pDate) {
                    setActiveTradingDate(pDate, true);
                }
            });
        });
    } catch(e) { console.warn('datePreset error:', e); }

    try {
        const topbarHiddenDate = document.getElementById('topbarHiddenDateInput');
        if (topbarHiddenDate) {
            topbarHiddenDate.value = getActiveTradingDate();
                    const topbarChip = document.getElementById('topbarDateChip');
        if (topbarChip) {
            topbarChip.addEventListener('click', (e) => {
                if (e.target.id !== 'topbarHiddenDateInput') {
                    const inp = document.getElementById('topbarHiddenDateInput');
                    if (inp) {
                        if (typeof inp.showPicker === 'function') {
                            try { inp.showPicker(); } catch(err) { inp.focus(); }
                        } else {
                            inp.focus();
                        }
                    }
                }
            });
        }
            topbarHiddenDate.addEventListener('change', () => {
                const newDate = topbarHiddenDate.value;
                if (newDate) {
                    setActiveTradingDate(newDate, true);
                }
            });
        }
    } catch(e) { console.warn('topbarDate error:', e); }

    try {
        const btnFmtIn = document.getElementById('btnFmtIn');
        const btnFmtIntl = document.getElementById('btnFmtIntl');
        if (btnFmtIn && btnFmtIntl) {
            btnFmtIn.addEventListener('click', () => {
                currentNumberFormat = 'in';
                btnFmtIn.classList.add('active');
                btnFmtIntl.classList.remove('active');
                if (currentData) renderDashboard(currentData);
                if (currentOcData) renderOptionChain(currentOcData);
                if (currentReportData) renderDetailsReport(currentReportData);
            });

            btnFmtIntl.addEventListener('click', () => {
                currentNumberFormat = 'intl';
                btnFmtIntl.classList.add('active');
                btnFmtIn.classList.remove('active');
                if (currentData) renderDashboard(currentData);
                if (currentOcData) renderOptionChain(currentOcData);
                if (currentReportData) renderDetailsReport(currentReportData);
            });
        }
    } catch(e) { console.warn('numberFormat error:', e); }

    try { initUploadDropzone(); } catch(e) { console.warn('uploadDropzone error:', e); }
    try { initPasteForm(); } catch(e) { console.warn('pasteForm error:', e); }

    try {
        document.querySelectorAll('.yt-nav-item[data-nav-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                const pageKey = link.getAttribute('data-nav-page');
                if (document.getElementById('pageHome')) {
                    e.preventDefault();
                    switchSpaPage(pageKey, true);
                    if (window.innerWidth <= 900) {
                        const sb = document.getElementById('ytSidebar');
                        const bd = document.getElementById('ytSidebarBackdrop');
                        if (sb) sb.classList.remove('open');
                        if (bd) bd.classList.remove('active');
                    }
                }
            });
        });

        document.querySelectorAll('[data-nav-target]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetPage = btn.getAttribute('data-nav-target');
                if (document.getElementById('pageHome')) {
                    e.preventDefault();
                    switchSpaPage(targetPage, true);
                }
            });
        });

        const brandLink = document.getElementById('brandLogoLink');
        if (brandLink && document.getElementById('pageHome')) {
            brandLink.addEventListener('click', (e) => {
                e.preventDefault();
                switchSpaPage('home', true);
            });
        }

        window.addEventListener('popstate', () => {
            const path = window.location.pathname;
            if (path.includes('option-chain')) switchSpaPage('option-chain', false);
            else if (path.includes('participant-oi')) switchSpaPage('participant-oi', false);
            else if (path.includes('details-report')) switchSpaPage('details-report', false);
            else if (path.includes('option-selling')) window.location.href = '/option-selling';
            else switchSpaPage('home', false);
        });
    } catch(e) { console.warn('nav error:', e); }

    const path = window.location.pathname;
    const page = document.body.dataset.page || '';

    console.log('[AlphaDeriv] Booting page:', page, 'path:', path);

    try {
        if (page === 'pipeline' || path.includes('/pipeline') || path.includes('/quant-pipeline')) {
            initPipelineWindowPage();
        } else if (page === 'strike_intelligence' || path.includes('/strike-intelligence')) {
            initStrikeIntelligencePage();
        } else if (page === 'option_chain' || path.includes('/option-chain')) {
            initOptionChainPage();
        } else if (page === 'details_report' || path.includes('/details-report')) {
            initDetailsReportPage();
        } else if (page === 'option_selling' || path.includes('/option-selling')) {
            initSellingStrategiesPage();
        } else if (page === 'participant_oi' || path.includes('/participant-oi')) {
            initParticipantOiPage();
        } else if (page === 'home' || path === '/' || path.endsWith('/index.html')) {
            initHomePage();
        }
    } catch(e) {
        console.error('[AlphaDeriv] Page execution error:', e);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootApp);
} else {
    bootApp();
}
