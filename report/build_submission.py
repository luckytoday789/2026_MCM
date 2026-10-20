"""Assemble an explicitly incomplete, evidence-bound local submission draft.

Reads accepted summary blobs through the existing read-only note generators.
Never reads raw/final datasets, executes experiments, changes gates or uploads.
Private identities and PDF files are permitted only inside ignored .runtime/.
Optional --team-file is local-only; no identity is copied into tracked sources.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import io
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "report"))
from build_primary_note import build as primary_source
from build_baseline_note import build as baseline_source

LABELS = {
    "bills_keep": "Bills held", "equal_weight_annual": "Annual thirds",
    "equal_weight_buy_hold": "Initial thirds", "conservative_cost": "Conservative",
    "balanced_cost": "Balanced fixed", "growth_cost": "Growth",
    "balanced_context": "Balanced context", "balanced_adaptive": "Balanced adaptive",
}
SOURCES = {
    "E0": ["specs/PROBLEM_LOCK.md", "specs/ACCOUNTING.md", "report/methods-draft.md"],
    "E1": ["report/primary-development-provenance.json", "audit/chief/HY3-004-review.json",
           "audit/chief/SOL-040-review.json"],
    "E2": ["report/policy-catalogue.md", "report/policy-methods-draft.md",
           "specs/development_policy_pilot_v2.json"],
    "E3": ["report/evidence-map.json", "ops/PROTOCOL.md"],
    "E4": ["report/baseline-development-provenance.json", "audit/chief/HY3-003-review.json",
           "audit/chief/SOL-008-review.json"],
    "E5": ["audit/chief/HY3-006-review.json", "audit/chief/CHIEF-HY3-006-20261020-review.json"],
    "E6": ["audit/chief/HY3-009-review.json", "results/development/HY3-009/selection.json"],
    "E7": ["audit/chief/CHIEF-PERSONALIZED-RUN-002-review.json",
           "results/development/CHIEF-PERSONALIZED-RUN-002/personalized_summary.csv"],
}


def canonical(raw):
    return raw.replace(b"\r\n", b"\n")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def mdtable(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(map(str, row)) + " |" for row in rows)])


def accepted_sources():
    # Regenerate in memory from exact accepted Git blobs; refuse source drift.
    result = {}
    for generator in (primary_source, baseline_source):
        files = generator()
        for name, raw in files.items():
            original=(ROOT / "report" / name).read_bytes()
            if canonical(original) != canonical(raw):
                # Chief may add a typed approval for the same exact accepted result.
                # Historical display provenance stays immutable; only that approval
                # pointer may change, never a result row, unit, source hash or value.
                if name != 'primary-development-provenance.json':
                    raise ValueError("Source note/provenance drift: " + name)
                old,new=json.loads(original),json.loads(raw)
                previous=old.pop('acceptances');current=new.pop('acceptances')
                if old!=new or set(previous)!=set(current):
                    raise ValueError('Numeric/source drift in primary provenance')
                for ident,record in previous.items():
                    historical=(ROOT/record['path']).read_bytes()
                    review=json.loads(historical)
                    assert sha(historical)==record['sha256'] and record['commit']==current[ident]['commit']
                    assert review['reviewed_commit']==record['commit']
                    assert review.get('verdict')=={'HY3-004':'accept_primary_development_bundle',
                        'SOL-040':'accept_independent_primary_review'}[ident]
                    positive=json.loads((ROOT/current[ident]['path']).read_bytes())
                    assert positive['reviewed_commit']==record['commit']
                    assert positive.get('result_verdict')=='approve' or positive.get('code_verdict')=='approve'
            if name.endswith("provenance.json"):
                result[name] = json.loads(raw)
    return result["primary-development-provenance.json"], result["baseline-development-provenance.json"]


def doubled_sources():
    commit='319781ef3c7fb5d4328a0ae4cea438bcc26a6f18'
    independent='194a45ac5fced5dfab02903e4e732b1cac1c6e67'
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
    for ident,expected in (('HY3-006',commit),('HY3-007',independent)):
        task=next(t for t in queue if t['id']==ident)
        assert task['state']=='accepted' and task['reviewed_commit']==expected
    review=json.loads((ROOT/'audit/chief/HY3-006-review.json').read_bytes())
    assert review['reviewed_commit']==commit and review['result_verdict']=='approve'
    numerical=json.loads((ROOT/'audit/chief/CHIEF-HY3-006-20261020-review.json').read_bytes())
    assert numerical['reviewed_commit']==independent and numerical['reviewed_result_commit']==commit
    assert numerical['result_verdict']==numerical['code_verdict']=='approve'
    def blob(path,source=commit):
        return subprocess.check_output(['git','show',source+':'+path],cwd=ROOT)
    oracle=numerical['oracle_execution']
    assert oracle['exit_code']==0 and sha(blob(oracle['log_path'],independent))==oracle['log_sha256']
    receipt=json.loads(blob('handoff/HY3-006/result.json'))
    assert receipt['status']=='completed' and receipt['artifact_hash_basis']=='canonical_git_blob'
    result=[];sources={}
    for mode in ('equal_weight_annual','balanced_cost','balanced_context','balanced_adaptive'):
        path=f'results/development/HY3-006/cases/{mode}/summary.csv';raw=blob(path)
        assert sha(raw)==receipt['artifacts_sha256'][path]==review['artifacts_sha256'][path]
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        row=next(r for r in rows if r['horizon']=='30')
        assert row['mode']==mode and row['split']=='development' and row['scenario_count']=='120'
        assert float(row['fee_rate'])==.005
        result.append(row);sources[path]={'sha256':sha(raw),'source_row':row}
    return result,dict(producer_commit=commit,independent_review_commit=independent,source_rows=sources)



def analysis_sources():
    commit='680c2faaf603df975c35e828aeebdadd8ce242cb'
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
    task=next(t for t in queue if t['id']=='HY3-009')
    assert task['state']=='accepted' and task['reviewed_commit']==commit and task['result_verdict']=='approve'
    review=json.loads((ROOT/task['acceptance_evidence']).read_bytes())
    assert review['reviewed_commit']==commit and review['numerical_review']['status']=='passed'
    prefix='results/development/HY3-009/'
    def read(name):
        path=prefix+name;raw=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
        assert sha(raw)==review['artifacts_sha256'][path]==task['artifacts_sha256'][path]
        return json.loads(raw)
    selection=read('selection.json');gates=read('comparison_gates.json')
    assert selection['selected_mode']=='balanced_cost' and selection['sensitivity_may_reselect'] is False
    pairs=[('balanced_cost','equal_weight_annual'),('balanced_context','balanced_cost'),
           ('balanced_adaptive','balanced_context'),('balanced_adaptive','balanced_cost')]
    selected=[next(r for r in gates if (r['candidate_mode'],r['reference_mode'])==pair and
                   r['fee_rate']==.0025 and r['horizon']==30) for pair in pairs]
    expected=[(.8378266961618253,-.17554525396301868,7.097619156859601,4),
              (0.,.11663999335577158,-1.7849863458934792,1),
              (.04696748609172019,-.09571123451484587,2.5384319317096242,4),
              (0.,.02092875884092571,.7534455858161451,2)]
    for row,values in zip(selected,expected):
        assert tuple(row[k] for k in ('median_paired_growth_gain_pp','marginal_p10_growth_difference_pp',
                    'marginal_p90_loss_difference_pp','positive_fold_count'))==values and row['passed'] is False
    cells=[[LABELS[r['candidate_mode']]+' / '+LABELS[r['reference_mode']],
            *(format(float(r[k]),'.3f') for k in ('median_paired_growth_gain_pp','marginal_p10_growth_difference_pp','marginal_p90_loss_difference_pp')),
            str(r['positive_fold_count'])+'/4','Fail'] for r in selected]
    return mdtable(['Candidate / control','Paired gain','p10 diff.','p90 loss diff.','Positive folds','Gate'],cells),dict(
        producer_commit=commit,acceptance_evidence=task['acceptance_evidence'],source_rows=selected,
        source_hashes={prefix+n:review['artifacts_sha256'][prefix+n] for n in ('selection.json','comparison_gates.json')})



def personalized_sources():
    ident='CHIEF-PERSONALIZED-RUN-002'
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
    task=next(t for t in queue if t['id']==ident)
    commit='b334b27a2f9fb8df99a6dee611e298bd0dc867d3'
    assert task['state']=='accepted' and task['reviewed_commit']==commit and task['result_verdict']=='approve'
    review=json.loads((ROOT/task['acceptance_evidence']).read_bytes())
    assert review['status']=='accepted' and review['reviewed_commit']==commit
    assert review['numerical_review']['status']=='passed' and review['numerical_review']['scalar_checks']==197524
    path='results/development/'+ident+'/personalized_summary.csv'
    raw=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
    assert sha(raw)==review['artifacts_sha256'][path]==task['artifacts_sha256'][path]
    assert canonical((ROOT/path).read_bytes())==canonical(raw)
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
    assert len(rows)==10 and {(r['profile_id'],float(r['fee_rate'])) for r in rows}=={(p,k) for p in 'ABCDE' for k in (.0025,.005)}
    cells=[]
    for r in rows:
        assert r['split']=='development' and r['component_source_verified']=='false' and r['bridge_provenance_verified']=='true'
        if r['profile_id'] in 'ADE':
            assert r['status']=='upstream_referral' and r['scenario_count']==r['denominator']=='0'
            assert r['recommended_class']==r['p10_growth_pct']==r['p90_loss_pct']==''
            continue
        assert r['status']=='eligible_after_personalized_development_rescreen' and r['recommended_class']=='conservative'
        assert r['scenario_count']==r['denominator']=='120' and r['risk_pass']==r['purchasing_power_pass']=='true'
        assert r['horizon']=={'B':'15','C':'30'}[r['profile_id']]
        assert float(r['p90_loss_pct'])<=float(r['loss_tolerance_pct']) and float(r['p10_growth_pct'])>=0
        cells.append([r['profile_id']+'/'+r['horizon'],format(100*float(r['fee_rate']),'.2f'),
            *[format(float(r[k]),'.2f') for k in ('median_growth_pct','p10_growth_pct','p90_loss_pct')],
            r['exceedance_count']+'/'+r['denominator'],
            *[format(float(r[k]),'.2f') for k in ('pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')]])
    return mdtable(['Profile/H','Fee %','Med G','p10 G','p90 L','Loss > tol.','Trades all','Trades later'],cells),dict(
        producer_commit=commit,acceptance_evidence=task['acceptance_evidence'],source_path=path,source_sha256=sha(raw),source_rows=rows,
        review_scope=review['numerical_review']['scope'])


def assemble(team_file=None):
    primary, baseline = accepted_sources()
    promotion_table,analysis_provenance=analysis_sources()
    doubled,doubled_provenance=doubled_sources()
    personalized_table,personalized_provenance=personalized_sources()
    text = (ROOT / "report/submission-draft.md").read_text(encoding="utf-8")
    primary_rows = [r["source_row"] for r in primary["displayed_rows"]
                    if r["key"]["horizon"] == 30]
    # Bind the few prose numbers as well as generated table cells to exact rows.
    claims = {
        "balanced_cost": {"median_growth_pct": "4.53", "p10_growth_pct": "1.10",
            "median_loss_pct": "26.84", "p90_loss_pct": "41.94", "pooled_trade_share_pct": "9.72"},
        "equal_weight_annual": {"median_growth_pct": "3.58", "p10_growth_pct": "1.28",
            "median_loss_pct": "20.10", "p90_loss_pct": "34.84", "pooled_trade_share_pct": "100.00"},
        "bills_keep": {"p90_loss_pct": "22.16", "severe_max_real_drawdown_pct": "29.86"}}
    for mode, values in claims.items():
        row = next(r for r in primary_rows if r["mode"] == mode)
        for key, expected in values.items():
            if format(float(row[key]), ".2f") != expected:
                raise ValueError("Prose result drift: " + mode + "/" + key)
    annual_30 = next(r for r in baseline["source_rows"]
                     if r["policy"] == "equal_weight_annual" and r["horizon"] == "30")
    assert annual_30["severe_scenario_id"] == "5"
    assert format(float(annual_30["severe_max_real_drawdown_pct"]), ".2f") == "50.88"
    doubled_fixed=next(r for r in doubled if r['mode']=='balanced_cost')
    doubled_claims={'median_growth_pct':'4.53','median_loss_pct':'28.26','p90_loss_pct':'42.02',
                    'pooled_trade_share_pct':'8.33'}
    assert all(format(float(doubled_fixed[k]),'.2f')==v for k,v in doubled_claims.items())
    cols = ["median_growth_pct", "p10_growth_pct", "median_loss_pct", "p90_loss_pct",
            "median_volatility_pct", "pooled_trade_share_pct", "pooled_trade_share_ex_initial_pct"]
    primary_table = mdtable(["Policy", "Median G", "p10 G", "Median L", "p90 L", "Fluct.",
                             "Trades all", "Trades later"],
        [[LABELS[r["mode"]], *(format(float(r[c]), ".2f") for c in cols)] for r in primary_rows])
    menus = [["Conservative", "15", "20", "65"], ["Balanced", "33 1/3", "33 1/3", "33 1/3"],
             ["Growth", "60", "30", "10"], ["Defensive alternative", "20", "25", "55"],
             ["Growth alternative", "45", "30", "25"]]
    design = json.loads((ROOT / "specs/development_policy_pilot_v2.json").read_bytes())
    assert design["targets"] == {"conservative": [.15, .2, .65], "balanced": ["1/3"]*3,
        "growth": [.6, .3, .1], "balanced_defensive": [.2, .25, .55],
        "balanced_growth_tilt": [.45, .3, .25]}
    profile_rows = [["A", "5", "10", "high", "60", "Conservative"],
                    ["B", "15", "25", "medium", "25", "Conservative, Balanced"],
                    ["C", "30", "40", "low", "10", "All three"],
                    ["D", "25", "15", "medium", "25", "Conservative, Balanced"],
                    ["E", "6", "35", "high", "60", "Conservative"]]
    annual = [r for r in baseline["source_rows"] if r["policy"] == "equal_weight_annual"]
    horizon_table = mdtable(["Horizon", "Median G", "p10 G", "Median L", "p90 L"],
        [[r["horizon"], *(format(float(r[c]), ".2f") for c in cols[:4])] for r in annual])
    sensitivity=[]
    for mode in ('equal_weight_annual','balanced_cost','balanced_context','balanced_adaptive'):
        for row,fee in ((next(r for r in primary_rows if r['mode']==mode),'0.25'),
                        (next(r for r in doubled if r['mode']==mode),'0.50')):
            human=row['pooled_human_review_share_pct']
            sensitivity.append([LABELS[mode],fee,*[format(float(row[c]),'.2f') for c in cols[:4]],
                format(float(row['pooled_trade_share_pct']),'.2f'),'-' if human=='' else format(float(human),'.2f')])
    sensitivity_table=mdtable(['Policy','Fee %','Median G','p10 G','Median L','p90 L','Trades %','Review %'],sensitivity)
    severe = next(r for r in primary_rows if r["mode"] == "balanced_cost")
    severe_text = (
        "For fixed-prior Balanced at the same development horizon and fee, the selected severe scenario is "
        f"{severe['severe_scenario_id']}. Its real CAGR is {float(severe['severe_net_real_cagr_pct']):.2f}%/year, "
        f"maximum drawdown {float(severe['severe_max_real_drawdown_pct']):.2f}%, and terminal real wealth "
        f"{float(severe['severe_terminal_real_wealth']):.2f} from initial wealth 100. The maximizing real peak "
        f"is year {severe['severe_drawdown_peak_year']} ({severe['severe_drawdown_peak_kind']}), and its trough "
        f"is year {severe['severe_drawdown_trough_year']} ({severe['severe_drawdown_trough_kind']}). "
        "This policy's severe case is distinct from selecting the benchmark's own worst path. [E1]")
    team = "Team identities are inserted only in the local submission copy."
    if team_file:
        local_root = (ROOT / ".runtime").resolve()
        team_file = team_file.resolve()
        if not team_file.is_relative_to(local_root):
            raise ValueError("The identity input must be in ignored .runtime/.")
        private = json.loads(team_file.read_bytes())
        # The caller supplies a display string; do not guess a private JSON schema.
        team = private.get("report_display", "")
        if not isinstance(team, str) or not team.strip():
            raise ValueError("The optional team file needs nonempty report_display text.")
    replacements = {"LOCAL_TEAM": team,
        "MENU_TABLE": mdtable(["Target", "Stocks %", "Bonds %", "Bills %"], menus),
        "PROFILE_TABLE": mdtable(["Profile", "Years", "Loss tol. %", "Liquidity", "Bills %", "Eligible classes"], profile_rows),
        "PRIMARY_H30_TABLE": primary_table, "BALANCED_SEVERE": severe_text,
        "BASELINE_HORIZON_TABLE": horizon_table,'SENSITIVITY_H30_TABLE':sensitivity_table,'PROMOTION_TABLE':promotion_table,'PERSONALIZED_TABLE':personalized_table}
    for key, value in replacements.items():
        if text.count("{{" + key + "}}") != 1:
            raise ValueError("Missing or duplicate template key " + key)
        text = text.replace("{{" + key + "}}", value)
    if re.search(r"\{\{.*?\}\}", text):
        raise ValueError("Unknown unexpanded template key")
    customer=re.search(r'<!-- SLOT:CUSTOMER_EXPLANATION -->(.*?)<!-- END_SLOT:CUSTOMER_EXPLANATION -->',text,re.S).group(1)
    customer= re.sub(r'\[E[0-9](?:, E[0-9])*\]','',customer)
    assert len(re.findall(r"\b[\w'-]+\b",customer))<=50,'Customer explanation exceeds50 words'
    markers=re.findall(r'<!-- SLOT:([A-Z_]+) -->',text)
    blocks=list(re.finditer(r'<!-- SLOT:([A-Z_]+) -->(.*?)<!-- END_SLOT:\1 -->',text,re.S))
    assert [m.group(1) for m in blocks]==markers and len(markers)==len(set(markers)), 'invalid/duplicate draft slot blocks'
    slot_status={}
    for block in blocks:
        name,content=block.group(1),block.group(2)
        pending=bool(re.search(r'(?m)^PENDING '+re.escape(name)+r':',content))
        # Numeric sensitivity has independently accepted exact source evidence.
        # Text filled into another slot still requires its own acceptance gate.
        slot_status[name]={'state':'pending' if pending else 'completed' if name in ('SENSITIVITY_RESULTS','PROMOTION_RESULTS','SENSITIVITY_RECOMMENDATION_IMPACT','CUSTOMER_EXPLANATION','PERSONALIZED_RESULTS') else
                           'text_filled_pending_evidence','pending_marker_present':pending,
                           'evidence_gate':'accepted_personalized_exact_ten_outcomes' if name=='PERSONALIZED_RESULTS' else
                           'accepted_HY3_004_and_HY3_006_results' if name=='SENSITIVITY_RESULTS' else
                           'accepted_HY3_009_selection_and_reviewed_policy' if name in ('PROMOTION_RESULTS','SENSITIVITY_RECOMMENDATION_IMPACT','CUSTOMER_EXPLANATION','PERSONALIZED_RESULTS') else
                           'accepted_upstream_and_report_conclusion_required'}
    slots=[name for name,record in slot_status.items() if record['state']!='completed']
    numeric_paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        if re.search(r"\d", paragraph) and not paragraph.startswith(("#", "|", "<!--", "PENDING")):
            sources = sorted(set(re.findall(r"E[0-9]", paragraph)))
            if paragraph.startswith("T ="):
                sources = ["E0"]
            elif paragraph.startswith("GPT-"):
                sources = ["E3"]
            elif paragraph == team:
                continue
            if not sources:
                raise ValueError("Numeric paragraph lacks an evidence marker: " + paragraph[:110])
            numeric_paragraphs.append({"paragraph_sha256": sha(paragraph.encode()), "sources": sources})
    metadata = {"schema_version": 1, "kind": "incomplete_submission_preparation",
        "submission_ready": False, "independent_manuscript_accepted": False,
        "final_outcomes_accessed": False, "simulation_rerun": False,
        "pending_slots": slots, "word_count": len(re.findall(r"\b[\w'-]+\b", text)),
        "completed_slots":[name for name,record in slot_status.items() if record['state']=='completed'],
        "slot_status":slot_status,
        "sensitivity_evidence_gate":dict(state='accepted',producer_commit=doubled_provenance['producer_commit'],
            independent_review_commit=doubled_provenance['independent_review_commit'],
            interpretation_gate='SENSITIVITY_RECOMMENDATION_IMPACT'),
        "personalized_provenance":personalized_provenance, "analysis_provenance":analysis_provenance, "source_registry": SOURCES, "numeric_paragraph_mappings": numeric_paragraphs,
        "primary_producer": primary["producer_commit"],
        "primary_review": primary["independent_review_commit"],
        "primary_current_acceptances":primary['acceptances'],
        "baseline_producer": baseline["source_commit"],
        "baseline_review": baseline["independent_review_commit"],
        "doubled_fee_provenance":doubled_provenance,
        "doubled_fee_prose_checks":doubled_claims,
        "prose_result_claim_checks": {"horizon": 30, "split": "development", "fee_rate": .0025,
            "primary_summary_values": claims, "baseline_annual_severe_id": "5",
            "baseline_annual_severe_loss_pct": "50.88"},
        "source_hashes": {p: sha(canonical((ROOT / p).read_bytes()))
            for p in sorted({"report/submission-draft.md", "report/build_submission.py",
                             *[p for paths in SOURCES.values() for p in paths]})},
        "rounding": "format(float(source_string), '.2f'); display only",
        "private_identity_access": team_file is not None,
        "minimum_font_pt": 11, "max_pages": 10,
        "missing_evidence": [
            "accepted reserved-scenario evaluation", "final customer explanation and conclusion",
            "independent full manuscript review", "local names, final rendering and source ZIP checks"]}
    return text, metadata


def render(text, output):
    from pypdf import PdfReader
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    body = ParagraphStyle("body", fontName="Times-Roman", fontSize=11.2, leading=13.4, spaceAfter=6)
    heading = ParagraphStyle("heading", parent=body, fontName="Times-Bold", fontSize=13,
                             leading=16, spaceBefore=9, spaceAfter=7, keepWithNext=True)
    title = ParagraphStyle("title", parent=heading, fontSize=19, leading=23)
    cell = ParagraphStyle("cell", parent=body, fontSize=11, leading=12.5, spaceAfter=0)
    story = []
    lines = text.splitlines(); index = 0; paragraph = []
    def html(value):
        value = escape(value)
        value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
        # Preserve exact commit IDs while permitting safe line wrapping.
        return re.sub(r"\b[0-9a-f]{40}\b", lambda m: "<wbr/>".join(m[0][i:i+10] for i in range(0, 40, 10)), value)
    def flush():
        if paragraph:
            story.append(Paragraph(html(" ".join(paragraph)), body)); paragraph.clear()
    while index < len(lines):
        line = lines[index]
        if line.startswith("<!--"):
            flush(); index += 1; continue
        if line.startswith("|"):
            flush(); rows = []
            while index < len(lines) and lines[index].startswith("|"):
                values = [x.strip() for x in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", x) for x in values):
                    rows.append([Paragraph(html(x), cell) for x in values])
                index += 1
            n = len(rows[0]); usable = A4[0] - 78
            widths = {8: [105, 58, 49, 56, 49, 53, 60, 65],
                      6: [43, 41, 70, 64, 54, 223],
                      5: [90, 100, 100, 108, 107],
                      4: [205, 100, 100, 100]}.get(n)
            if n == 6 and rows[0][0].getPlainText() == 'Candidate / control':
                widths = [185, 65, 65, 80, 65, 50]
            if widths:
                widths = [usable * w / sum(widths) for w in widths]
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT",rowSplitRange=(2,-2))
            table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf1")),
                ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#607483")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            story.extend([table, Spacer(1, 7)]); continue
        if line.startswith("#"):
            flush(); story.append(Paragraph(html(line.lstrip("# ")), title if line.startswith("# ") else heading))
        elif not line.strip():
            flush()
        else:
            paragraph.append(line)
        index += 1
    flush()
    def decorate(canvas, doc):
        canvas.saveState(); canvas.setFont("Times-Roman", 11)
        canvas.setFillColor(colors.HexColor("#5b6670"))
        canvas.drawString(39, 817, "INCOMPLETE DRAFT - accepted development evidence only")
        canvas.drawString(39, 25, "SafeInvest | Review and missing result gates remain open")
        canvas.drawRightString(A4[0]-39, 25, str(doc.page)); canvas.restoreState()
    def stable_canvas(*args, **kwargs):
        return Canvas(*args, **{**kwargs, "invariant": 1})
    pdf = output / "SafeInvest-incomplete-draft.pdf"
    SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=39, rightMargin=39,
        topMargin=43, bottomMargin=43, title="SafeInvest incomplete evidence-bound draft",
        author="SafeInvest project").build(story, onFirstPage=decorate, onLaterPages=decorate,
                                          canvasmaker=stable_canvas)
    reader = PdfReader(pdf); sizes = []; page_checks = []
    for page in reader.pages:
        text = page.extract_text(visitor_text=lambda text, cm, tm, font, size:
            sizes.append(float(size)) if text.strip() else None)
        page_checks.append("INCOMPLETE DRAFT" in text)
        assert abs(float(page.mediabox.width)-A4[0]) < .02
        assert abs(float(page.mediabox.height)-A4[1]) < .02
    assert min(sizes) >= 11
    assert all(page_checks)
    # Do not label an oversized draft compliant; preserve and report it.
    return {"pdf_sha256": sha(pdf.read_bytes()), "pages": len(reader.pages), "paper": "A4",
        "minimum_font_pt": min(sizes), "within_page_limit": len(reader.pages) <= 10,
        "all_pages_marked_incomplete": all(page_checks), "visual_review": "pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--team-file", type=Path)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args(); output = args.output_dir.resolve()
    if not output.is_relative_to((ROOT / ".runtime").resolve()):
        raise ValueError("All generated artifacts must remain inside ignored .runtime/.")
    if output.exists():
        raise FileExistsError("Preserve prior artifacts; use a fresh output directory.")
    text, metadata = assemble(args.team_file)
    output.mkdir(parents=True)
    (output / "expanded-draft.md").write_text(text, encoding="utf-8")
    if not args.metadata_only:
        metadata["pdf_checks"] = render(text, output)
    metadata["created_at"] = datetime.now(timezone.utc).isoformat()
    (output / "build-provenance.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in ("kind", "submission_ready", "word_count", "pending_slots")} |
                     {"pdf_checks": metadata.get("pdf_checks")}))


if __name__ == "__main__":
    main()
