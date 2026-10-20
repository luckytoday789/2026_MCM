"""SOL-030 independent saved-output audit. No simulation; --check never writes.

Only stdlib is needed for arithmetic/integrity. Chief renderer dependencies are
separately diagnosed; this verifier never imports either chief script.
"""
import argparse, csv, hashlib, io, json, math, re, struct, subprocess, sys, zlib
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = '04be213a76855b1b1815405a735f2a49be678935'
RELEASE = 'f2e2743a4b57e05bb438c3af4b801c1e99f6dbb4'
TASK_SHA = 'c164559e5fc86d5de16d7bf54679518a8941927a079f75364d174586263ac191'
RESULT = '7652410d73425371110784ef5fa97c03470a074e'
REVIEW = '818af5d65bd8a271962d848dd552bd39ca561f68'
P = ('bills_keep','equal_weight_annual','equal_weight_buy_hold')
COLORS = ('#333333','#0072b2','#a94400')
PREFIX = 'results/development/HY3-003/'
FIG = 'report/figures/'
NS = {'s':'http://www.w3.org/2000/svg'}
EVIDENCE = ('review.md','findings.json','inspection.json','execution-history.json',
            'integrity-self-tests.json','selftest.py','task-lock.json')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(raw, path):
    # Git text identity; binaries and PNG/PDF data are never normalized.
    return raw if Path(path).suffix.lower() in ('.pdf','.png') else raw.replace(b'\r\n',b'\n')

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def blob(commit,path):
    return git('show',commit+':'+path)

def load(path):
    return json.loads(Path(path).read_bytes())

def dump(path,value):
    with Path(path).open('x',encoding='utf8',newline='\n') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False)
        f.write('\n')

def task_identity():
    t=json.loads(blob(RELEASE,'ops/tasks/SOL-030.json'))
    require(sha(json.dumps(t,sort_keys=True,separators=(',',':')).encode())==TASK_SHA,'task identity')
    require(t['base_commit']==BASE and t['owner']=='sol' and t['allowed_paths']==['audit/SOL-030'],'task scope')
    local=ROOT/'.runtime/task.json'
    if local.exists(): require(load(local)==t,'runner task changed')
    require(load(HERE/'task-lock.json')==t,'task lock changed')
    return t

def make_binding(t):
    sources={}
    paths=dict(t['parameters']['source_sha256'])
    # Include actual inspected negative history and role/release evidence in closure.
    extra=['AGENTS.md','ops/PROTOCOL.md','ops/queue.json','ops/control.json',
           'audit/chief/SOL-021-review.json']
    extra+=git('ls-tree','-r','--name-only',BASE,'audit/chief/baseline-figures-history').decode().splitlines()
    for p in extra: paths[p]=sha(blob(BASE,p))
    for p,h in sorted(paths.items()):
        raw=blob(BASE,p)
        require(sha(raw)==h,'base pin '+p)
        require(sha(canonical((ROOT/p).read_bytes(),p))==h,'local input changed: '+p)
        sources[p]={'sha256':h,'bytes':len(raw),'commit':BASE}
    for p in (PREFIX+'summary.csv',PREFIX+'scenario_metrics.csv',PREFIX+'annual_ledgers.csv','handoff/HY3-003/result.json'):
        require(blob(RESULT,p)==blob(BASE,p),'accepted source commit '+p)
    receipt=json.loads(blob(RESULT,'handoff/HY3-003/result.json'))
    for name in ('summary.csv','scenario_metrics.csv','annual_ledgers.csv'):
        p=PREFIX+name
        require(receipt['artifacts_sha256'][p]==sources[p]['sha256'],'accepted receipt '+p)
    queue=json.loads(blob(BASE,'ops/queue.json'))['tasks']
    for name,commit in [('HY3-003',RESULT),('SOL-008',REVIEW)]:
        e=next(x for x in queue if x['id']==name)
        require(e['state']=='accepted' and e['reviewed_commit']==commit,'acceptance '+name)
    rq=json.loads(blob(RELEASE,'ops/queue.json'))['tasks']
    e=next(x for x in rq if x['id']=='SOL-030')
    require(e['state']=='ready' and e['task_sha256']==TASK_SHA,'release')
    control=json.loads(blob(RELEASE,'ops/control.json'))
    require(control['state']=='running' and not control['final_data_open'],'release control')
    return {'schema_version':1,'task_id':'SOL-030','attempt':1,'task_sha256':TASK_SHA,
            'base_commit':BASE,'release_snapshot_commit':RELEASE,
            'release_queue_sha256':sha(blob(RELEASE,'ops/queue.json')),
            'release_control_sha256':sha(blob(RELEASE,'ops/control.json')),
            'source_result_commit':RESULT,'accepted_result_review_commit':REVIEW,
            'sources':sources,'verifier_sha256':sha(canonical(Path(__file__).read_bytes(),'verify.py')),
            'hash_basis':'canonical Git text bytes; exact PNG/PDF bytes',
            'mutable_HEAD_or_main_required':False}

def check_binding(candidate,expected):
    require(candidate==expected,'source identity/binding differs from immutable closure')

def rows(path):
    return list(csv.DictReader(io.StringIO(Path(path).read_text(encoding='utf8'))))

def linear(values,q):
    a=sorted(values); pos=(len(a)-1)*q; lo=math.floor(pos); hi=math.ceil(pos)
    return a[lo]+(a[hi]-a[lo])*(pos-lo)

def numerical(points_path=None):
    metrics=rows(ROOT/(PREFIX+'scenario_metrics.csv'))
    sums=rows(ROOT/(PREFIX+'summary.csv'))
    ledger=rows(ROOT/(PREFIX+'annual_ledgers.csv'))
    require((len(metrics),len(sums),len(ledger))==(1800,15,10800),'saved row counts')
    h30=[r for r in metrics if int(r['horizon'])==30]
    require(len(h30)==360 and all(r['split']=='development' for r in h30),'H30 development')
    summaries={r['policy']:r for r in sums if int(r['horizon'])==30}
    prov=load(ROOT/(FIG+'baseline-figures-provenance.json'))
    require(prov['source_commit']==RESULT and prov['independent_review_commit']==REVIEW,'provenance commits')
    require(prov['summary_rows']==[summaries[p] for p in P],'provenance summary rows')
    stats=[]; severe={}
    for p in P:
        a=[r for r in h30 if r['policy']==p]
        require(len(a)==120 and sorted(int(r['scenario_id']) for r in a)==list(range(1,121)),'metric keys '+p)
        for out,field,q in [('median_growth_pct','net_real_cagr_pct',.5),('p10_growth_pct','net_real_cagr_pct',.1),
                            ('median_loss_pct','max_real_drawdown_pct',.5),('p90_loss_pct','max_real_drawdown_pct',.9)]:
            val=linear([float(r[field]) for r in a],q); saved=float(summaries[p][out])
            require(math.isclose(val,saved,rel_tol=0,abs_tol=1e-12),'summary '+p+'/'+out)
            stats.append({'policy':p,'quantity':out,'recomputed':val,'saved':saved,'residual':saved-val})
        # No rounding or approximate tie grouping; smallest ID only on EXACT ties.
        chosen=min(a,key=lambda r:(-float(r['max_real_drawdown_pct']),int(r['scenario_id'])))
        sid=int(chosen['scenario_id']); require(sid==int(summaries[p]['severe_scenario_id']),'severe ID '+p)
        severe[p]={'scenario_id':sid,'loss_pct':float(chosen['max_real_drawdown_pct']),
                   'exact_tie_ids':sorted(int(r['scenario_id']) for r in a if float(r['max_real_drawdown_pct'])==float(chosen['max_real_drawdown_pct']))}
    scenario=severe['equal_weight_annual']['scenario_id']
    require(scenario==5,'annual severe selection')
    expected=[]
    for p in P:
        a=sorted([r for r in ledger if r['policy']==p and int(r['scenario_id'])==scenario],key=lambda r:int(r['year']))
        require([int(r['year']) for r in a]==list(range(1,31)),'ledger years '+p)
        path=[{'policy':p,'scenario_id':scenario,'event_index':0,'year':0,'stage':'initial','elapsed_years':0,'real_wealth':100.0}]
        for r in a:
            require(r['split']=='development','ledger split')
            y=int(r['year'])
            for stage,time,key in [('post_fee',y-1,'real_wealth_after_fee'),('end',y,'real_wealth_end')]:
                path.append({'policy':p,'scenario_id':scenario,'event_index':len(path),'year':y,'stage':stage,
                             'elapsed_years':time,'real_wealth':float(r[key])})
        expected+=path
    actual=rows(points_path or ROOT/(FIG+'baseline-h30-severe-points.csv'))
    require(len(actual)==183,'point count')
    for i,(a,e) in enumerate(zip(actual,expected)):
        require(set(a)==set(e),'point columns')
        for k,v in e.items():
            observed=float(a[k]) if k=='real_wealth' else int(a[k]) if isinstance(v,int) else a[k]
            require(observed==v,'point '+str(i)+' '+k+': '+str(observed)+' != '+str(v))
    annual=[e for e in expected if e['policy']=='equal_weight_annual']
    peak=annual[0]; worst=0.; peak_at=trough=peak
    for e in annual:
        if e['real_wealth']>peak['real_wealth']: peak=e
        loss=100*(1-e['real_wealth']/peak['real_wealth'])
        if loss>worst: worst,peak_at,trough=loss,dict(peak),dict(e)
    s=summaries['equal_weight_annual']
    for kind,event in [('peak',peak_at),('trough',trough)]:
        require(event['year']==int(s['severe_drawdown_'+kind+'_year']) and event['stage']==s['severe_drawdown_'+kind+'_kind'],'strict '+kind)
        require(event==prov[kind],'provenance '+kind)
    require(worst==float(s['severe_max_real_drawdown_pct'])==prov['loss_pct'],'severe loss')
    require(trough['year']==8 and trough['stage']=='post_fee' and trough['elapsed_years']==7,'fee event time')
    require(annual[-1]['real_wealth']!=trough['real_wealth'],'terminal is not trough')
    require(annual[-1]['real_wealth']==float(s['severe_terminal_real_wealth']),'terminal wealth')
    for name,record in prov['outputs'].items():
        raw=(ROOT/FIG/name).read_bytes()
        require(sha(raw)==record['sha256'] and len(raw)==record['bytes'],'stored export '+name)
    return {'statistics':stats,'h30_metric_rows':360,'severe':severe,'point_count':183,
            'field_comparisons':sum(len(e) for e in expected),'points':expected,'peak':peak_at,'trough':trough,
            'loss_pct':worst,'terminal_annual_real_wealth':annual[-1]['real_wealth'],
            'same_scenario_comparators':True,'duplicated_times_retained':True}

def vertices(path):
    d=path.get('d','')
    require(not re.search('[CQAHVSTcqahvst]',d),'unexpected SVG curve')
    return [(float(x),float(y)) for x,y in re.findall(r'[ML]\s+([-\d.e]+)\s+([-\d.e]+)',d)]

def axis_map(ax,axis):
    ticks=[]
    for g in ax.findall('s:g',NS):
        if g.get('id','').startswith(axis+'tick_'):
            text=g.find('.//s:text',NS); use=g.find('.//s:use',NS)
            if text is not None and use is not None:
                try: ticks.append((float(''.join(text.itertext())),float(use.get(axis))))
                except (ValueError,TypeError): pass
    require(len(ticks)>=2,'SVG tick calibration '+axis)
    a,b=ticks[0],ticks[-1]; scale=(b[1]-a[1])/(b[0]-a[0]); offset=a[1]-scale*a[0]
    return lambda x:offset+scale*x

def export_inspection(n):
    result={}
    for name in ['summary','severe-path']:
        path=ROOT/(FIG+'baseline-h30-'+name+'.svg'); svg=ET.fromstring(path.read_bytes())
        width=float(svg.get('width').removesuffix('pt'))*25.4/72
        require(abs(width-180)<.001,'SVG width')
        sizes=[float(v) for e in svg.iter() for v in re.findall(r'font-size:\s*([\d.]+)px',e.get('style',''))]
        require(sizes and min(sizes)>=11,'SVG font size')
        entry={'svg_width_mm':width,'svg_min_font_pt_at_export_width':min(sizes)}
        axes=[g for g in svg.iter() if g.get('id','').startswith('axes_')]
        residual=0.; count=0
        for axindex,ax in enumerate(axes):
            xmap=axis_map(ax,'x'); ymap=axis_map(ax,'y') if name=='severe-path' else None
            for p,color in zip(P,COLORS):
                lines=[e for e in ax.iter() if e.tag.endswith('path') and 'stroke: '+color+';' in e.get('style','') and e.get('clip-path')]
                target=[e for e in lines if len(vertices(e))==(61 if name=='severe-path' else 2)]
                require(len(target)==1,'SVG data path '+name+'/'+p)
                vs=vertices(target[0])
                if name=='severe-path':
                    pts=[e for e in n['points'] if e['policy']==p]
                    desired=[(xmap(e['elapsed_years']),ymap(e['real_wealth'])) for e in pts]
                else:
                    fields=('median_growth_pct','p10_growth_pct') if axindex==0 else ('median_loss_pct','p90_loss_pct')
                    vals={e['quantity']:e['recomputed'] for e in n['statistics'] if e['policy']==p}
                    desired=[(xmap(vals[f]),vs[j][1]) for j,f in enumerate(fields)]
                for a,b in zip(vs,desired):
                    for v,w in zip(a,b): residual=max(residual,abs(v-w))
                    require(max(abs(v-w) for v,w in zip(a,b))<2e-6,'SVG coordinate '+name+'/'+p)
                    count+=1
        entry.update({'svg_vertices_checked':count,'svg_max_coordinate_residual_pt':residual})
        pdf=(ROOT/(FIG+'baseline-h30-'+name+'.pdf')).read_bytes()
        box=re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)',pdf)
        require(box is not None,'PDF page size')
        mm=[float(v)*25.4/72 for v in box.groups()]; require(abs(mm[0]-180)<.001,'PDF width')
        fonts=sorted(set(v.decode() for v in re.findall(rb'/BaseFont\s*/([^\s/>]+)',pdf)))
        require(b'/Subtype /Type3' not in pdf and b'/CIDFontType2' in pdf and pdf.count(b'/FontFile2')==len(fonts),'PDF embedded TrueType')
        font_sizes=[]
        for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream',pdf,re.S):
            try: raw=zlib.decompress(m.group(1))
            except zlib.error: continue
            if b'BT' in raw: font_sizes += [float(v) for v in re.findall(rb'/F\d+\s+([\d.]+)\s+Tf',raw)]
        require(font_sizes and min(font_sizes)>=11,'PDF minimum font')
        png=(ROOT/(FIG+'baseline-h30-'+name+'.png')).read_bytes()
        require(png[:8]==b'\x89PNG\r\n\x1a\n','PNG signature')
        pixels=list(struct.unpack('>II',png[16:24])); pos=8; dpi=None
        while pos<len(png):
            length=struct.unpack('>I',png[pos:pos+4])[0]; typ=png[pos+4:pos+8]; data=png[pos+8:pos+8+length]; pos+=12+length
            if typ==b'pHYs':
                x,y,unit=struct.unpack('>IIB',data); require(unit==1,'PNG physical units'); dpi=[x*.0254,y*.0254]
        require(dpi and min(dpi)>=299,'PNG resolution')
        entry.update({'pdf_mm':mm,'pdf_fonts':fonts,'pdf_embedded_fontfiles':pdf.count(b'/FontFile2'),
                      'pdf_min_font_pt':min(font_sizes),'png_pixels':pixels,'png_dpi':dpi})
        result[name]=entry
    return result

def calculate(t,binding):
    n=numerical()
    visual=export_inspection(n)
    evidence={}
    for name in EVIDENCE:
        raw=(HERE/name).read_bytes(); require(len(raw)<10485760,'artifact size '+name)
        evidence[name]=sha(canonical(raw,name))
    trials=load(HERE/'integrity-self-tests.json')
    require(len(trials['trials'])==2 and all(x['rejected'] and x['unchanged'] for x in trials['trials']),'corruption demonstrations')
    return {'schema_version':1,'task_id':'SOL-030','task_sha256':TASK_SHA,'base_commit':BASE,
            'source_binding_sha256':sha(canonical((HERE/'source-binding.json').read_bytes(),'source-binding.json')),
            'verifier_sha256':binding['verifier_sha256'],'numerical':n,'exports':visual,
            'evidence_sha256':evidence,'simulation_rerun':False,'competition_inputs_read':False,
            'numerical_verdict':'passed','chief_renderer_check':'blocked_missing_matplotlib',
            'read_only_check_supported':True,'policy_or_final_approval':False}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true'); ap.add_argument('--create',action='store_true')
    a=ap.parse_args(); require(a.check!=a.create,'choose exactly --check or --create')
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    t=task_identity(); binding=make_binding(t)
    if a.create:
        require(not (HERE/'source-binding.json').exists() and not (HERE/'verification.json').exists(),'refuse evidence overwrite')
        dump(HERE/'source-binding.json',binding)
    check_binding(load(HERE/'source-binding.json'),binding)
    verification=calculate(t,binding)
    if a.create: dump(HERE/'verification.json',verification)
    else: require(load(HERE/'verification.json')==verification,'saved evidence differs from independent reconstruction')
    print(json.dumps({'status':'passed','read_only':a.check,'summary_quantities':12,'H30_rows':360,
                      'path_points':183,'source_pins':len(binding['sources']),
                      'loss_pct':verification['numerical']['loss_pct'],
                      'chief_renderer_check':'blocked_missing_matplotlib'}))

if __name__=='__main__':
    main()
