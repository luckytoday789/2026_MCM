import argparse,csv,hashlib,io,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    note=ROOT/'report/primary-development.md'
    rows=[r for r in note.read_text(encoding='utf-8').splitlines() if r.startswith('| ')][2:]
    assert len(rows)==40
    checked=0
    for line in rows:
        cells=[s.strip() for s in line.strip('|').split('|')];h=int(cells[0]);mode=cells[1]
        data=subprocess.check_output(['git','show','6aa2ccdce80834c8beb52a827993f1f587d1d8a6:results/development/HY3-004/cases/'+mode+'/summary.csv'],cwd=ROOT)
        source=next(r for r in csv.DictReader(io.StringIO(data.decode('utf-8'))) if int(r['horizon'])==h)
        columns=('median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct','median_volatility_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')
        for actual,key in zip(cells[2:],columns):
            assert actual==format(float(source[key]),'.2f');checked+=1
    record=dict(status='passed',scope='accepted_primary_descriptive_table_only',rows=40,independent_display_cells=checked,
        source_commit='6aa2ccdce80834c8beb52a827993f1f587d1d8a6',note_sha256=hashlib.sha256(note.read_bytes()).hexdigest(),
        no_simulation=True,final_outcomes_read=False,policy_selected=False,customer_assignment=False)
    target=ROOT/'audit/chief/primary-report-validation.json'
    if args.check:assert json.loads(target.read_bytes())==record
    else:
        with target.open('xb') as handle:handle.write((json.dumps(record,indent=2)+'\n').encode())
    print(json.dumps(record))
if __name__=='__main__':main()
