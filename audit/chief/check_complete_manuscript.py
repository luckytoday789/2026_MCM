"""Check complete review-manuscript transcription and actual local PDF bounds.

Chief mechanical verification only, not independent manuscript acceptance.
Reads saved accepted Git outputs; never opens original scenario observations.
"""
import argparse,csv,io,json,re,subprocess,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'report'))
import build_submission as builder

def check(output):
    from pypdf import PdfReader
    text,meta=builder.assemble()
    saved=json.loads((output/'build-provenance.json').read_bytes())
    assert not saved['private_identity_access']
    assert (output/'expanded-draft.md').read_text(encoding='utf8')==text
    for key in ('source_hashes','slot_status','numeric_paragraph_mappings','final_provenance','word_count'):
        assert meta[key]==saved[key],key
    assert meta['pending_slots']==[] and not meta['submission_ready'] and not meta['independent_manuscript_accepted']
    assert meta['final_outcomes_accessed'] and not meta['original_final_input_read'] and not meta['simulation_rerun']
    assert 'PENDING ' not in text and '{{' not in text
    R='4b8ac5d6822ac39ff1189c13d34ed3f84f699319';prefix='results/final/HY3-010/'
    def blob(name):return subprocess.check_output(['git','show',R+':'+prefix+name],cwd=ROOT)
    rows=list(csv.DictReader(io.StringIO(blob('summary.csv').decode())))
    cols=('median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct','median_volatility_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')
    count=0
    for r in rows:
        if r['horizon']=='30' and float(r['fee_rate'])==.0025:
            expected='| '+builder.LABELS[r['mode']]+' | '+' | '.join(format(float(r[k]),'.2f') for k in cols)+' |'
            assert expected in text;count+=len(cols)
    profiles=json.loads(blob('personalized.json'))
    for r in profiles:
        if r['eligible']:
            assert r['horizon']=={'B':15,'C':30}[r['profile_id']]
            assert r['p90_loss_pct']>r['loss_tolerance_pct'] and r['p10_growth_pct']>0
            assert r['exceedance_count']==7 and r['denominator']==60
            fields=[r['profile_id']+'/'+str(r['horizon']),format(100*r['fee_rate'],'.2f'),str(r['loss_tolerance_pct']),
                    format(r['p90_loss_pct'],'.2f'),format(r['p10_growth_pct'],'.2f'),'7/60',format(r['median_loss_pct'],'.2f'),format(r['severe_loss_pct'],'.2f')]
            assert '| '+' | '.join(fields)+' |' in text;count+=6
        else:
            assert r['profile_id'] in 'ADE' and r['recommended_class'] is None
    assert 'All A-E require human review.' in text and 'No fallback class is tried.' in text
    for phrase in ('26.46% against B\'s 25% tolerance','40.52% against C\'s 40%',
                   '0.814 percentage points/year','7.073 points','scenario is 172',
                   '62.44%','year 13 (end)','year 27 (end)','44.17%','scenario 155','57.81%'):
        assert phrase in text,phrase
    customer=re.search(r'<!-- SLOT:CUSTOMER_EXPLANATION -->(.*?)<!-- END_SLOT:CUSTOMER_EXPLANATION -->',text,re.S)[1]
    customer=re.sub(r'\[E\d(?:, E\d)*\]','',customer)
    words=len(re.findall(r"\b[\w'-]+\b",customer));assert words<=50
    pdf=output/'SafeInvest-review-manuscript.pdf';reader=PdfReader(pdf);sizes=[];pdf_text=[]
    for page in reader.pages:
        assert abs(float(page.mediabox.width)-595.2756)<.02 and abs(float(page.mediabox.height)-841.8898)<.02
        content=page.extract_text(visitor_text=lambda t,cm,tm,font,size:sizes.append(float(size)) if t.strip() else None)
        assert 'REVIEW COPY' in content;pdf_text.append(content)
    assert len(reader.pages)<=10 and min(sizes)>=11
    assert builder.sha(pdf.read_bytes())==saved['pdf_checks']['pdf_sha256']
    assert 'All A-E require human review.' in ' '.join(pdf_text)
    corruptions=[]
    originals=builder.final_source()
    for name,old,new in [('final-evaluation.md',b'26.46',b'26.45'),
                         ('final-evaluation-provenance.json',b'"all_clients_human_review": true',b'"all_clients_human_review": false')]:
        changed=dict(originals);assert old in changed[name];changed[name]=changed[name].replace(old,new,1)
        try:
            with patch.object(builder,'final_source',return_value=changed):builder.final_sources()
        except AssertionError:corruptions.append(name)
        else:raise AssertionError('Corrupted final note accepted: '+name)
    return dict(status='passed',scope='Chief mechanical transcription/PDF check; independent review remains required',
                final_numeric_cells_checked=count,customer_word_count=words,pages=len(reader.pages),minimum_font_pt=min(sizes),
                pdf_sha256=builder.sha(pdf.read_bytes()),source_hashes=saved['source_hashes'],
                corruptions_rejected=corruptions,original_final_inputs_read=False,simulation_rerun=False,submission_ready=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--record',type=Path)
    a=p.parse_args();result=check(a.output_dir)
    if a.record:
        assert not a.record.exists();a.record.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'}))
