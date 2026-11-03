"""
Script to generate sample NSE participant OI PDFs and CSVs for 5 days,
matching the exact screenshot for Day 5 (15-Oct) and showing multi-day trends.
"""
import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# In the screenshot:
# Net Carried 2 Days Ago (13-Oct), 1 Day Ago (14-Oct), Today (15-Oct)
# And the Long Chg, Short Chg from 14-Oct to 15-Oct.

# Let's define realistic base Long and Short contracts for each participant for 13-Oct, 14-Oct, 15-Oct:
# To make: Long - Short = Carried Net
# And Long(15) - Long(14) = Long Chg, Short(15) - Short(14) = Short Chg

# Let's derive 14-Oct and 15-Oct:
# For Client Index Futures:
# Carried 14-Oct = 245358. Suppose Long(14) = 350000, Short(14) = 104642 (350000 - 104642 = 245358)
# Long chg = -22453 => Long(15) = 350000 - 22453 = 327547
# Short chg = +3593 => Short(15) = 104642 + 3593 = 108235
# Net(15) = 327547 - 108235 = 219312! Exactly matches Carried Today!

def generate_sample_data():
    # Base numbers for 14-Oct (Day 4)
    # Form: { participant: { inst: (long_14, short_14) } }
    base_14 = {
        "Client": {
            "fut_idx": (350000, 104642),       # net = 245358
            "opt_idx_ce": (1250000, 1062579),   # net = 187421
            "opt_idx_pe": (2000000, 2706501),   # net = -706501
            "fut_stk": (4500000, 1277925),      # net = 3222075
            "opt_stk_ce": (1800000, 812387),    # net = 987613
            "opt_stk_pe": (400000, 618398),     # net = -218398
        },
        "DII": {
            "fut_idx": (80000, 49978),          # net = 30022
            "opt_idx_ce": (100000, 1617),       # net = 98383
            "opt_idx_pe": (80000, 4050),        # net = 75950
            "fut_stk": (200000, 4597081),       # net = -4397081
            "opt_stk_ce": (5000, 372996),       # net = -367996
            "opt_stk_pe": (10000, 5680),        # net = 4320
        },
        "FII": {
            "fut_idx": (50000, 346697),         # net = -296697
            "opt_idx_ce": (600000, 932906),     # net = -332906
            "opt_idx_pe": (900000, 355235),     # net = 544765
            "fut_stk": (1600000, 856014),      # net = 743986
            "opt_stk_ce": (150000, 315987),     # net = -165987
            "opt_stk_pe": (250000, 116934),     # net = 133066
        },
        "Pro": {
            "fut_idx": (100000, 78683),         # net = 21317
            "opt_idx_ce": (500000, 452899),     # net = 47101
            "opt_idx_pe": (800000, 714214),     # net = 85786
            "fut_stk": (1200000, 768980),      # net = 431020
            "opt_stk_ce": (400000, 853630),     # net = -453630
            "opt_stk_pe": (450000, 368988),     # net = 81012
        }
    }

    # Delays / changes from 14-Oct to 15-Oct from screenshot:
    changes_15 = {
        "Client": {
            "fut_idx": (-22453, 3593),
            "opt_idx_ce": (-248261, -118753),
            "opt_idx_pe": (1076630, 842170),
            "fut_stk": (-12222, 30783),
            "opt_stk_ce": (-39331, 4593),
            "opt_stk_pe": (54952, 11871),
        },
        "DII": {
            "fut_idx": (1768, -4651),
            "opt_idx_ce": (-79118, 160),
            "opt_idx_pe": (5711, 0),
            "fut_stk": (14795, -5732),
            "opt_stk_ce": (-7195, 28913),
            "opt_stk_pe": (90, 663),
        },
        "FII": {
            "fut_idx": (4267, -12603),
            "opt_idx_ce": (8264, -116761),
            "opt_idx_pe": (160469, 258207),
            "fut_stk": (12856, -29719),
            "opt_stk_ce": (34243, 17846),
            "opt_stk_pe": (16767, 30462),
        },
        "Pro": {
            "fut_idx": (-3670, -6427),
            "opt_idx_ce": (-4402, -88164),
            "opt_idx_pe": (364435, 506868),
            "fut_stk": (9022, 29119),
            "opt_stk_ce": (66328, 2693),
            "opt_stk_pe": (10521, 39334),
        }
    }

    # Let's construct 15-Oct:
    data_15 = {}
    for p in base_14:
        data_15[p] = {}
        for inst in base_14[p]:
            l14, s14 = base_14[p][inst]
            dl, ds = changes_15[p][inst]
            data_15[p][inst] = (l14 + dl, s14 + ds)

    # Let's construct 13-Oct such that net positions match 2 DAYS AGO:
    # 2 DAYS AGO carried nets:
    carried_13 = {
        "Client": {"fut_idx": 229857, "opt_idx_ce": 111452, "opt_idx_pe": -586835, "fut_stk": 3212609, "opt_stk_ce": 863596, "opt_stk_pe": -202004},
        "DII": {"fut_idx": 34531, "opt_idx_ce": 94848, "opt_idx_pe": 74365, "fut_stk": -4435039, "opt_stk_ce": -354012, "opt_stk_pe": 7596},
        "FII": {"fut_idx": -289495, "opt_idx_ce": -288995, "opt_idx_pe": 565338, "fut_stk": 774020, "opt_stk_ce": -152484, "opt_stk_pe": 124293},
        "Pro": {"fut_idx": 25107, "opt_idx_ce": 82695, "opt_idx_pe": -52868, "fut_stk": 448410, "opt_stk_ce": -357100, "opt_stk_pe": 70115},
    }
    data_13 = {}
    for p in base_14:
        data_13[p] = {}
        for inst in base_14[p]:
            l14, s14 = base_14[p][inst]
            target_net = carried_13[p][inst]
            # Keep short close to s14, adjust long
            s13 = s14
            l13 = s13 + target_net
            data_13[p][inst] = (l13, s13)

    # Also generate Day 1 (11-Oct) and Day 2 (12-Oct) for full 5 days
    data_11 = {}
    data_12 = {}
    for p in base_14:
        data_11[p] = {}
        data_12[p] = {}
        for inst in base_14[p]:
            l13, s13 = data_13[p][inst]
            data_12[p][inst] = (int(l13 * 0.98), int(s13 * 0.99))
            data_11[p][inst] = (int(l13 * 0.96), int(s13 * 0.98))

    return {
        "2026-10-11": data_11,
        "2026-10-12": data_12,
        "2026-10-13": data_13,
        "2026-10-14": base_14,
        "2026-10-15": data_15,
    }

def create_csv_files(days_data, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    header = "Client Type,Future Index Long,Future Index Short,Future Stock Long,Future Stock Short,Option Index Call Long,Option Index Put Long,Option Index Call Short,Option Index Put Short,Option Stock Call Long,Option Stock Put Long,Option Stock Call Short,Option Stock Put Short,Total Long Contracts,Total Short Contracts\n"
    
    csv_paths = []
    for date_str, day in days_data.items():
        fname = f"fao_participant_oi_{date_str.replace('-', '')}.csv"
        path = os.path.join(output_dir, fname)
        lines = [header]
        
        totals = [0] * 14
        for p in ["Client", "DII", "FII", "Pro"]:
            row = [p]
            inst_vals = [
                day[p]["fut_idx"][0], day[p]["fut_idx"][1],
                day[p]["fut_stk"][0], day[p]["fut_stk"][1],
                day[p]["opt_idx_ce"][0], day[p]["opt_idx_pe"][0],
                day[p]["opt_idx_ce"][1], day[p]["opt_idx_pe"][1],
                day[p]["opt_stk_ce"][0], day[p]["opt_stk_pe"][0],
                day[p]["opt_stk_ce"][1], day[p]["opt_stk_pe"][1]
            ]
            t_long = sum(inst_vals[0::2])
            t_short = sum(inst_vals[1::2])
            row_full = [p] + [str(x) for x in inst_vals] + [str(t_long), str(t_short)]
            lines.append(",".join(row_full) + "\n")
            
            for i in range(12):
                totals[i] += inst_vals[i]
            totals[12] += t_long
            totals[13] += t_short
            
        total_row = ["TOTAL"] + [str(x) for x in totals]
        lines.append(",".join(total_row) + "\n")
        
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        csv_paths.append(path)
    return csv_paths

def create_pdf_files(days_data, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    pdf_paths = []
    
    headers = ["Client Type", "Fut Idx L", "Fut Idx S", "Fut Stk L", "Fut Stk S", "Opt Idx CE L", "Opt Idx PE L", "Opt Idx CE S", "Opt Idx PE S", "Opt Stk CE L", "Opt Stk PE L", "Opt Stk CE S", "Opt Stk PE S", "Total L", "Total S"]
    
    for date_str, day in days_data.items():
        fname = f"fao_participant_oi_{date_str.replace('-', '')}.pdf"
        path = os.path.join(output_dir, fname)
        
        doc = SimpleDocTemplate(path, pagesize=landscape(letter), leftMargin=18, rightMargin=18, topMargin=20, bottomMargin=20)
        elements = []
        styles = getSampleStyleSheet()
        
        title = Paragraph(f"<b>National Stock Exchange of India - Participant wise Open Interest (OI) in Equity Derivatives on {date_str}</b>", styles['Heading2'])
        elements.append(title)
        elements.append(Spacer(1, 10))
        
        table_data = [headers]
        totals = [0] * 14
        for p in ["Client", "DII", "FII", "Pro"]:
            inst_vals = [
                day[p]["fut_idx"][0], day[p]["fut_idx"][1],
                day[p]["fut_stk"][0], day[p]["fut_stk"][1],
                day[p]["opt_idx_ce"][0], day[p]["opt_idx_pe"][0],
                day[p]["opt_idx_ce"][1], day[p]["opt_idx_pe"][1],
                day[p]["opt_stk_ce"][0], day[p]["opt_stk_pe"][0],
                day[p]["opt_stk_ce"][1], day[p]["opt_stk_pe"][1]
            ]
            t_long = sum(inst_vals[0::2])
            t_short = sum(inst_vals[1::2])
            row = [p] + [f"{x:,}" for x in inst_vals] + [f"{t_long:,}", f"{t_short:,}"]
            table_data.append(row)
            for i in range(12): totals[i] += inst_vals[i]
            totals[12] += t_long
            totals[13] += t_short
            
        table_data.append(["TOTAL"] + [f"{x:,}" for x in totals])
        
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#f8fafc')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        elements.append(t)
        doc.build(elements)
        pdf_paths.append(path)
        
    return pdf_paths

if __name__ == "__main__":
    out_dir = r"C:\Users\suman_yrhfixt\.gemini\antigravity\scratch\participant-oi-analyzer\sample_files"
    days = generate_sample_data()
    csvs = create_csv_files(days, out_dir)
    pdfs = create_pdf_files(days, out_dir)
    print(f"Generated {len(csvs)} CSV files and {len(pdfs)} PDF files in {out_dir}")
