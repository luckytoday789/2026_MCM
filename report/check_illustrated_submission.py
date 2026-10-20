"""Independently check figure source projections, saved-path math and PDF text."""
import argparse,csv,hashlib,io,json,math,re,subprocess
from pathlib import Path
from PIL import Image
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def norm(t):return re.sub(r'\s+',' ',t).strip()
def core(pdf):
    pages=[]
    for i,page in enumerate(pdf.pages,1):
        t=page.extract_text().replace('SafeInvest - development and frozen final evidence\n','')
        t=t.replace('SafeInvest | Scenario study in purchasing power\n'+str(i)+'\n','');pages.append(t)
    return norm(' '.join(pages))

def check(output):
    m=json.loads((ROOT/'report/figures/illustrated-final-v1/figure-provenance.json').read_bytes())
    C=m['producer_commit'];cache={};checks=0
    def blob(path):
        if path not in cache:cache[path]=subprocess.check_output(['git','show',C+':'+path],cwd=ROOT)
        assert sha(cache[path])==m['source_sha256'][path]
        return cache[path]
    def rows(path):return list(csv.DictReader(io.StringIO(blob(path).decode())))
    def close(x,y):
        nonlocal checks
        assert math.isclose(x,y,abs_tol=2e-10,rel_tol=1e-12),(x,y);checks+=1
    receipt=json.loads(subprocess.check_output(['git','show',C+':handoff/HY3-010/result.json'],cwd=ROOT))
    assert receipt['status']=='completed'
    for path,h in m['source_sha256'].items():assert receipt['artifacts_sha256'][path]==h
    expected=[r for r in rows('results/final/HY3-010/summary.csv') if r['horizon']=='30' and r['fee_rate']=='0.0025']
    assert len(expected)==8
    for a,b in zip(expected,m['figures'][0]['data']):
        assert a['mode']==b['mode'];close(float(a['median_growth_pct']),b['median_growth_pct']);close(float(a['p90_loss_pct']),b['p90_loss_pct'])
    all_clients=json.loads(blob('results/final/HY3-010/personalized.json'))
    expected=[r for r in all_clients if r['scenario_count']==60]
    assert expected==m['figures'][1]['data'] and len(expected)==4
    assert len([r for r in all_clients if r['scenario_count']==0])==6
    for row in expected:assert row['p90_loss_pct']>row['loss_tolerance_pct'] and row['exceedance_count']==7
    for series in m['figures'][2]['data']:
        rr=[r for r in rows('results/final/HY3-010/generic/'+series['mode']+'/0.0025/annual_ledgers.csv') if r['scenario_id']=='172']
        assert len(rr)==30
        expected_t=[0];expected_v=[100.]
        for row in rr:expected_t.extend([int(row['year'])-1,int(row['year'])]);expected_v.extend([float(row['real_wealth_after_fee']),float(row['real_wealth_end'])])
        assert expected_t==series['year'] and expected_v==series['real_wealth']
        peak=100.;loss=[]
        for v,saved in zip(expected_v,series['drawdown_pct']):
            peak=max(peak,v);d=(peak-v)/peak*100;loss.append(d);close(d,saved)
        close(max(loss),series['max_drawdown_pct'])
    images=[]
    for fig in m['figures']:
        path=ROOT/fig['path'];assert sha(path.read_bytes())==fig['sha256']
        image=Image.open(path);dpi=image.info['dpi'];assert min(dpi)>=299
        assert fig['font_pt_at_manuscript_width']>=11
        images.append({'id':fig['id'],'pixels':image.size,'dpi':dpi,'sha256':fig['sha256']})
    pdf=PdfReader(output/'SafeInvest-final-illustrated.pdf');old=PdfReader(ROOT/'.runtime/final-release-20261020/SafeInvest-final.pdf')
    new_text=core(pdf)
    for fig in m['figures']:
        caption=norm(fig['caption']);assert new_text.count(caption)==1;new_text=new_text.replace(caption,'')
    assert core(old)==norm(new_text),'Actual PDF text changed beyond captions.'
    assert len(pdf.pages)<=10 and sum(len(list(p.images)) for p in pdf.pages)==3
    sizes=[]
    for page in pdf.pages:
        assert abs(float(page.mediabox.width)-595.2756)<.02 and abs(float(page.mediabox.height)-841.8898)<.02
        page.extract_text(visitor_text=lambda t,cm,tm,font,size:sizes.append(float(size)) if t.strip() else None)
    assert min(sizes)>=11
    return dict(status='passed',pdf_sha256=sha((output/'SafeInvest-final-illustrated.pdf').read_bytes()),pages=len(pdf.pages),images=images,scalar_checks=checks,exact_original_pdf_body_preserved=True,only_new_prose='three figure captions',original_source_files=len(cache),minimum_text_font_pt=min(sizes),simulation_rerun=False,original_observations_opened=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);args=p.parse_args()
    result=check((ROOT/args.output_dir).resolve());print(json.dumps(result,indent=2))
