"""Four-page incomplete layout proof from locked methods and accepted tables.

No simulation, fitting, final input or private identity reads. Optional layout
requirements are separate from numerical requirements. Build refuses overwrite;
--check is read-only. New builds can use an ignored --output-dir for comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from html import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'report'))
from build_baseline_note import build as source_tables, COMMIT, REVIEW

INPUTS = ['specs/PROBLEM_LOCK.md', 'specs/ACCOUNTING.md',
          'report/methods-draft.md', 'report/baseline-development.md',
          'report/baseline-development-provenance.json',
          'report/build_baseline_note.py', 'report/build_layout_proof.py',
          'report/requirements-layout.txt']
NAMES = {'bills_keep':'Bills held', 'equal_weight_annual':'Annual thirds',
         'equal_weight_buy_hold':'Initial thirds'}
PDF_NAME = 'methods-baselines.pdf'
MANIFEST_NAME = 'layout-provenance.json'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def source():
    files = source_tables()
    for name, expected in files.items():
        assert (ROOT/'report'/name).read_bytes().replace(b'\r\n', b'\n') == expected
    return json.loads(files['baseline-development-provenance.json'])['source_rows']

def fingerprints():
    return {p:sha((ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in INPUTS}

def table_rows(rows):
    first=[]; second=[]
    for r in rows:
        prefix=[r['horizon'],NAMES[r['policy']]]
        first.append(prefix+[f'{float(r[k]):.2f}' for k in (
            'median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct',
            'pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')])
        second.append(prefix+[
            f"{float(r['median_volatility_pct']):.2f}",
            f"{float(r['median_nominal_fee_sum']):.2f}",r['severe_scenario_id'],
            f"{float(r['severe_max_real_drawdown_pct']):.2f}",
            r['severe_drawdown_peak_year']+' '+r['severe_drawdown_peak_kind'],
            r['severe_drawdown_trough_year']+' '+r['severe_drawdown_trough_kind']])
    return first,second

def inspect_pdf(path, rows):
    from pypdf import PdfReader
    reader=PdfReader(path)
    assert len(reader.pages)==4, f'Expected four layout pages, got {len(reader.pages)}'
    texts=[]; sizes=[]
    for page in reader.pages:
        assert abs(float(page.mediabox.width)-595.2756)<.02
        assert abs(float(page.mediabox.height)-841.8898)<.02
        def visit(text,cm,tm,font,size):
            if text.strip(): sizes.append(float(size))
        texts.append(' '.join(page.extract_text(visitor_text=visit).split()))
        assert 'INCOMPLETE LAYOUT PROOF' in texts[-1]
    assert min(sizes)>=11, min(sizes)
    for page_rows,text in zip(table_rows(rows),texts[2:]):
        cursor=0
        for row in page_rows:
            needle=' '.join(row)
            where=text.find(needle,cursor)
            assert where>=0, f'Missing or changed displayed row: {needle}'
            cursor=where+len(needle)
    assert 'Final outcomes remain closed' in texts[0]
    assert 'not a customer assignment' in texts[2]
    return {'pages':4,'paper':'A4 portrait','minimum_text_size_pt':min(sizes),
            'table_rows_checked':30,'source_rows':15,
            'numeric_and_event_cells_checked':180,
            'all_pages_labeled_incomplete':True,
            'visual_inspection':'separate rendered-page review required'}

def build(output):
    from reportlab import Version
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    rows=source(); first,second=table_rows(rows)
    output.mkdir(parents=True,exist_ok=True)
    pdf=output/PDF_NAME; manifest=output/MANIFEST_NAME
    if pdf.exists() or manifest.exists():
        raise FileExistsError('Preserve existing proof; use a fresh --output-dir.')
    body=ParagraphStyle('body',fontName='Times-Roman',fontSize=11.5,leading=15.5,spaceAfter=8)
    heading=ParagraphStyle('heading',parent=body,fontName='Times-Bold',fontSize=15,leading=19,spaceBefore=8,spaceAfter=9)
    title=ParagraphStyle('title',parent=heading,fontSize=21,leading=25)
    small=ParagraphStyle('table',parent=body,fontSize=11,leading=13,spaceAfter=0)
    eq=ParagraphStyle('equation',parent=body,fontName='Times-Italic',fontSize=12,leading=17,leftIndent=12,spaceAfter=10)
    story=[]
    def p(text,style=body): story.append(Paragraph(text,style))
    def h(text): p(text,heading)
    def equation(text): p(text,eq)
    def nextpage(): story.append(PageBreak())
    def table(headers,data,widths):
        content=[[Paragraph(escape(x).replace('\n','<br/>'),small) for x in headers]]
        content += [[Paragraph(escape(x),small) for x in row] for row in data]
        t=Table(content,colWidths=widths,repeatRows=1,hAlign='LEFT')
        styles=[('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6edf3')),
                ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#37536a')),
                ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
                ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]
        for i in (3,6,9,12,15): styles.append(('LINEBELOW',(0,i),(-1,i),.4,colors.HexColor('#aebbc7')))
        t.setStyle(TableStyle(styles)); story.append(t); story.append(Spacer(1,10))
    p('SafeInvest',title)
    p('Accounting methods and accepted development references',heading)
    p('<b>Working layout only.</b> Policy selection, customer suitability, cost sensitivity and final evaluation are pending. Final outcomes remain closed. This proof has no team identities and is not a competition submission.')
    h('1. Independent annual scenarios')
    p('The supplied inputs contain 180 independent synthetic scenarios, each with 30 annual observations. Scenarios 1-120 support development; 121-180 are reserved for evaluation after a recorded freeze. Scenarios are never joined into a historical time series. Each path begins with wealth 100 in bills, with no borrowing, deposits, withdrawals or terminal liquidation fee.')
    p('At the start of year t, a decision uses observations through t-1 from that scenario and legitimately development-calibrated parameters. Internal validation excludes its evaluation scenarios from calibration. Current returns and inflation are applied after the decision.')
    h('2. Transfers, fees and purchasing power')
    p('Let h<super size="11">-</super> be pre-trade holdings, W<super size="11">-</super> their sum, u their weights, and w a nonnegative target summing to one. With k = 0.0025:')
    equation('T = (W<super size="11">-</super>/2) sum<sub size="11">i</sub> |w<sub size="11">i</sub> - u<sub size="11">i</sub>|, &nbsp; c = kT, &nbsp; h<super size="11">+</super> = (W<super size="11">-</super> - c)w.')
    p('Transfers are measured on pre-fee wealth and counted once. Fees are paid before returns and funded proportionally, leaving the target exact. The fee-funding adjustment is not charged again. Keep preserves dollar holdings and costs zero. Initial allocation incurs the same fee.')
    equation('h<sub size="11">t,i</sub><super size="11">end</super> = h<sub size="11">t,i</sub><super size="11">+</super>(1 + r<sub size="11">t,i</sub>), &nbsp; C<sub size="11">0</sub> = 1, &nbsp; C<sub size="11">t</sub> = C<sub size="11">t-1</sub>(1 + inflation<sub size="11">t</sub>).')
    equation('V<sub size="11">t</sub><super size="11">+</super> = sum<sub size="11">i</sub> h<sub size="11">t,i</sub><super size="11">+</super> / C<sub size="11">t-1</sub>, &nbsp; V<sub size="11">t</sub> = sum<sub size="11">i</sub> h<sub size="11">t,i</sub><super size="11">end</super> / C<sub size="11">t</sub>.')
    p('The exact real gross return is (1 + nominal return)/(1 + inflation). Bills can lose purchasing power. Post-fee wealth uses the previous CPI because the trade precedes current-year inflation.')
    nextpage()
    h('3. Growth, ordinary fluctuation and large loss')
    p('For horizon H, let q<sub size="11">t</sub> = V<sub size="11">t</sub>/V<sub size="11">t-1</sub> - 1 be the annual net real return. Initial real wealth is V<sub size="11">0</sub> = 100. Annualized real growth and ordinary fluctuation are:')
    equation('G<sub size="11">H</sub> = 100[(V<sub size="11">H</sub>/100)<super size="11">1/H</super> - 1],')
    equation('F<sub size="11">H</sub> = 100 sqrt[sum<sub size="11">t=1..H</sub>(q<sub size="11">t</sub> - mean(q))<super size="11">2</super> / (H - 1)].')
    p('Growth is percent per year. Fluctuation is the sample standard deviation of annual returns in percentage points, with ddof = 1. Post-fee observations are not extra annual return intervals.')
    p('For x = (100, V<sub size="11">1</sub><super size="11">+</super>, V<sub size="11">1</sub>, ..., V<sub size="11">H</sub><super size="11">+</super>, V<sub size="11">H</sub>), maximum real drawdown is:')
    equation('L<sub size="11">H</sub> = 100 max<sub size="11">j</sub> [1 - x<sub size="11">j</sub> / max<sub size="11">ell &lt;= j</sub> x<sub size="11">ell</sub>].')
    p('Larger loss is worse. Including initial and post-fee wealth retains initial fees and temporary fee-induced troughs. Profile horizons A/B/C/D/E are 5/15/30/25/6 years; each uses its own prefix. The common policy comparison uses H = 30.')
    h('4. Scenario summaries and severe cases')
    p('Metrics are calculated per scenario before taking medians or linear quantiles. For n sorted values and probability p, interpolate at index (n - 1)p. Required summaries are median and p10 growth, and median and p90 loss. The p90 is a descriptive quantile, not a guarantee, worst-case bound or CVaR.')
    p('A severe case is the greatest drawdown for that reference and horizon; exact ties choose the smallest scenario ID. Within a path, scan initial, post-fee and year-end observations. Update peaks and selected losses only on strict increases, preserving the earliest maximizing pair and the initial sentinel for zero loss.')
    p('An annual review involves a trade when T &gt; 10<super size="11">-10</super>. Pooled trade share divides trade count by nH. The share excluding initial allocation uses years 2 through H and denominator n(H - 1). Both shares are percentages.')
    h('5. Evidence and interpretation')
    p('Annual thirds restores equal weights at every review, including year 1. Initial thirds buys equal weights once and then keeps component dollars at reviews while returns change their values. Bills held never transfers. None of these references has a human-review overlay.')
    p('Independent review and chief replay accepted the saved development baselines. They establish descriptive evidence, not suitability or added value from automatic target updates. Differences between marginal medians are not median paired differences. The original annual-simple-return accounting and final-data gate remain binding.')
    nextpage()
    h('6. Accepted reference summaries')
    p('Development scenarios 1-120; n = 120 per row; one-way fee 0.25%. Growth is real CAGR (% per year); loss is maximum real drawdown (%). Display rounding is two decimals. This is not a customer assignment or final evaluation.')
    p('Reference names: Bills held; Annual thirds; Initial thirds (held after the initial allocation). All rows use their own horizon H.')
    table(['H','Reference','Median\ngrowth','p10\ngrowth','Median\nloss','p90\nloss','Trades\nall (%)','Trades\nlater (%)'], first,[25,91,65,59,62,55,65,65])
    p('At H = 30, annual thirds and initial thirds differ in both allocation drift and fees. Their comparison does not isolate a causal fee effect. Bills also experience purchasing-power losses. No new cost-aware policy outcome or recommendation is inferred from these tables.')
    p('The source tables were viewed before the policy pilot design. Later internally cross-fitted experiments remain development evidence. Final evaluation requires an accepted frozen policy and protocol.')
    nextpage()
    h('7. Fluctuation and severe-case locations')
    p('F is median ordinary fluctuation in percentage points. Fee is the median sum of nominal fees. ID is each row\'s own severe scenario; loss is its maximum real drawdown (%). Peak and trough give year and event stage. post_fee is before that year\'s return and inflation.')
    table(['H','Reference','F','Fee','ID','Severe\nloss','Peak','Trough'],second,[25,91,42,42,32,58,89,108])
    p('A shared scenario ID does not imply identical paths or peak/trough locations. Nominal fee sums are descriptive currency totals, not inflation-adjusted welfare losses. Quantiles are not confidence bounds.')
    h('Source and writing status')
    p('Competition data and conventions: specs/PROBLEM_LOCK.md and specs/ACCOUNTING.md. Tables: accepted HY3-003 summary.csv; independent review SOL-008. The companion layout-provenance.json records exact source and review commits, input hashes and displayed row checks. No simulation was rerun.')
    p('This chief-prepared proof adapts existing methods-draft.md and baseline-development.md. Reportlab assembles the pages and pypdf checks text, paper size and font sizes; rendered pages require visual inspection. Independent manuscript review, remaining results, local member names and the final AI-use disclosure are still required.')
    def decorate(c,doc):
        c.saveState(); c.setFont('Times-Roman',11); c.setFillColor(colors.HexColor('#43596b'))
        c.drawString(36,815,'INCOMPLETE LAYOUT PROOF - development evidence only')
        c.setStrokeColor(colors.HexColor('#bdc8d0')); c.line(36,806,559,806)
        c.drawString(36,25,'SafeInvest | Working methods and reference tables')
        c.drawRightString(559,25,str(doc.page)); c.restoreState()
    def stable_canvas(*args,**kwargs):
        kwargs['invariant']=1; return canvas.Canvas(*args,**kwargs)
    doc=SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=36,rightMargin=36,topMargin=47,bottomMargin=44,
                          title='SafeInvest incomplete methods and baseline layout proof',author='SafeInvest project')
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate,canvasmaker=stable_canvas)
    checks=inspect_pdf(pdf,rows)
    meta={'schema_version':1,'kind':'incomplete_layout_proof','independently_accepted':False,
          'source_result_commit':COMMIT,'source_review_commit':REVIEW,
          'source_main_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'source_sha256':fingerprints(),'source_hash_basis':'UTF-8 source with LF newlines',
          'reportlab_version':Version,'python_version':sys.version.split()[0],
          'pdf_sha256':sha(pdf.read_bytes()),'pdf_bytes':pdf.stat().st_size,
          'simulation_rerun':False,'final_input_access':False,'private_identity_access':False,
          'checks':checks,'display_rows':{'performance':first,'severe':second}}
    manifest.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    return meta

def check(output):
    rows=source(); meta=json.loads((output/MANIFEST_NAME).read_bytes())
    assert meta['source_sha256']==fingerprints()
    assert meta['pdf_sha256']==sha((output/PDF_NAME).read_bytes())
    assert meta['source_result_commit']==COMMIT and meta['source_review_commit']==REVIEW
    first,second=table_rows(rows)
    assert meta['display_rows']=={'performance':first,'severe':second}
    assert meta['checks']==inspect_pdf(output/PDF_NAME,rows)
    return meta

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'report/layout-proof')
    args=parser.parse_args()
    result=check(args.output_dir) if args.check else build(args.output_dir)
    print(json.dumps({'status':'passed','mode':'check' if args.check else 'build',**result['checks']}))
