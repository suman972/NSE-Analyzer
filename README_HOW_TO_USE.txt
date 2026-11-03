================================================================================
  NSE DERIVATIVES & OPTION SELLING INTELLIGENCE SYSTEM
================================================================================

HOW TO RUN THE APPLICATION:
---------------------------
Method 1 (Easiest):
  • Go to your Desktop and double-click:
    "Start_NSE_Analyzer.bat"

Method 2:
  • Open the "NSE-Option-Selling-Analyzer" folder on your Desktop
  • Double-click "run_app.bat"

What happens:
  1. The local server starts on port 5000.
  2. Your web browser automatically opens directly to the Option Selling Dashboard:
     http://127.0.0.1:5000/option-selling


AVAILABLE MODULES & WEB PAGES:
-----------------------------
1. Option Selling & Market View Matrix:
   URL: http://127.0.0.1:5000/option-selling
   • 5-Pillar Quantitative View Creation Engine (Futures, Writing, Retail Trap, Chain, 1-SD Volatility)
   • Top 3 Recommended Option Selling Strategies (Bull Put Spread, Iron Condor, Bear Call Spread)
   • Live Strike Efficiency Matrix (Delta, Theta, Gamma, Volume, OI)
   • Zerodha Varsity Quantitative Framework (Delta 0.15-0.25 sweet spot, Gamma Trap avoidance, SPAN Margin discount)

2. Institutional Details Report:
   URL: http://127.0.0.1:5000/details-report
   • Comprehensive 4-Participant Dossiers (FIIs, PRO desks, Retail Clients, DIIs)
   • Cross-Reference Synergy Matrix (Participant OI <-> Option Chain Strikes)
   • 3 Actionable Next-Day Trading Scenarios
   • Print to PDF / Executive Briefing export

3. Proper Option Chain (Big Player Perspectives):
   URL: http://127.0.0.1:5000/option-chain
   • 13-Column Option Chain with ITM yellow highlight & ATM spot marker
   • FII, PRO, and Client viewpoint filters
   • Probabilistic Support (S1, S2) and Resistance (R1, R2) with holding probabilities

4. Participant-Wise Open Interest Analyzer:
   URL: http://127.0.0.1:5000/participant-oi
   • 6 Segregated Instrument Tables (Index Futures, Index Calls, Index Puts, Stock Futures, Stock Calls, Stock Puts)
   • 5-Day Historical Carried Positions
   • Retail Trap Squeeze Alert Banner

5. Home Hub:
   URL: http://127.0.0.1:5000/


HOW TO CHANGE DATES & SYMBOLS:
------------------------------
• In the top navigation bar of any page, click NIFTY, BANKNIFTY, or FINNIFTY.
• Change the date picker (e.g. 2024-10-15 vs 2024-10-14).
• All 5 pillars, composite conviction scores, Greeks, and strategies will update dynamically in real time.


REQUIREMENTS:
-------------
• Python 3.10+
• Required libraries (Flask, requests, numpy, scipy) are already installed in your Python environment.
================================================================================
