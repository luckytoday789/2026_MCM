"""Plot exact accepted saved final results. No input observations or simulation.

Python3.12, Matplotlib3.11.2; supplied synthetic paths remain separate. The
three figures are display-only supplements to independently accepted text.
"""
import argparse,csv,hashlib,io,json,subprocess
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
COMMIT='4b8ac5d6822ac39ff1189c13d34ed3f84f699319'
PREFIX='results/final/HY3-010'
DEST=ROOT/'report/figures/illustrated-final-v1'
WIDTH=(595.2755905511812-78)/72
LABELS=['Bills held','Annual thirds','Initial thirds','Conservative','Balanced fixed','Growth','Balanced context','Balanced adaptive']
BLUE='#0072B2';ORANGE='#A64B00';GREY='#52616B'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def blob(path):
    assert path.startswith(PREFIX+'/') and not path.startswith('data/')
    raw=subprocess.check_output(['git','show',COMMIT+':'+path],cwd=ROOT)
    receipt=json.loads(subprocess.check_output(['git','show',COMMIT+':handoff/HY3-010/result.json'],cwd=ROOT))
    assert sha(raw)==receipt['artifacts_sha256'][path]
    SOURCES[path]=sha(raw)
    return raw
def rows(path):return list(csv.DictReader(io.StringIO(blob(path).decode())))
def clean(ax):
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='x',color='#D9DFE3',linewidth=.6);ax.set_axisbelow(True)
def export(fig,name,height,caption,data):
    fig.savefig(DEST/(name+'.png'),dpi=300,facecolor='white')
    fig.savefig(DEST/(name+'.pdf'),facecolor='white',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    FIGURES.append(dict(id=name,path=DEST.relative_to(ROOT).as_posix()+'/'+name+'.png',
        width_inches=WIDTH,height_inches=height,font_pt_at_manuscript_width=11.2,
        caption=caption,data=data,sha256=sha((DEST/(name+'.png')).read_bytes())))

SOURCES={};FIGURES=[]
def main():
    global DEST
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default='report/figures/illustrated-final-v1')
    args=parser.parse_args();DEST=(ROOT/args.output_dir).resolve()
    assert DEST.is_relative_to(ROOT)
    assert not DEST.exists(),'Preserve existing figure version; create a new version instead.'
    DEST.mkdir(parents=True)
    with plt.rc_context({'font.family':'DejaVu Sans','font.size':11.2,'axes.labelsize':11.2,
        'xtick.labelsize':11.2,'ytick.labelsize':11.2,'legend.fontsize':11.2,
        'pdf.fonttype':42,'axes.linewidth':.6}):
        summary=rows(PREFIX+'/summary.csv')
        primary=[r for r in summary if float(r['fee_rate'])==.0025 and int(r['horizon'])==30]
        assert len(primary)==8 and all(int(r['scenario_count'])==60 for r in primary)
        assert [r['mode'] for r in primary]==['bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive']
        values=[[float(r['median_growth_pct']),float(r['p90_loss_pct'])] for r in primary]
        fig,axes=plt.subplots(1,2,figsize=(WIDTH,2.65),sharey=True)
        fig.subplots_adjust(left=.23,right=.97,bottom=.23,top=.86,wspace=.24)
        for j,(ax,title,xlabel,limit) in enumerate(zip(axes,['(a) Median real growth','(b) p90 real drawdown'],['Growth (%/year)','Drawdown (%)'],[5.6,63])):
            bars=ax.barh(range(8),[v[j] for v in values],height=.67,color=[ORANGE if i==4 else BLUE for i in range(8)])
            ax.set(xlim=(0,limit),xlabel=xlabel,title=title,yticks=range(8),yticklabels=LABELS)
            ax.invert_yaxis() if not ax.yaxis_inverted() else None
            for i,v in enumerate(values):ax.text(v[j]+limit*.025,i,f'{v[j]:.2f}',va='center',fontsize=11.2)
            clean(ax)
        export(fig,'figure1-final-comparison',2.65,
            'Figure 1. Frozen final comparison: 60 scenarios, H=30 years, one-way fee 0.25%. Orange identifies fixed Balanced, selected before final access. Panels show separate marginal summaries; p90 drawdown is not a loss bound. [E8]',
            [dict(mode=r['mode'],median_growth_pct=v[0],p90_loss_pct=v[1]) for r,v in zip(primary,values)])

        clients=json.loads(blob(PREFIX+'/personalized.json'))
        executed=[r for r in clients if r['scenario_count']==60]
        assert len(executed)==4 and all(r['risk_pass'] is False and r['purchasing_power_pass'] is True for r in executed)
        y=list(range(4));loss=[r['p90_loss_pct'] for r in executed];tol=[r['loss_tolerance_pct'] for r in executed]
        fig,ax=plt.subplots(figsize=(WIDTH,1.95));fig.subplots_adjust(left=.23,right=.96,bottom=.30,top=.81)
        ax.barh(y,loss,height=.58,color=BLUE,label='Final p90 loss')
        ax.scatter(tol,y,color='#151515',marker='|',s=210,linewidth=2,label='Client tolerance',zorder=3)
        for i,r in enumerate(executed):ax.text(loss[i]+.7,i,f'{loss[i]:.2f} / {tol[i]}',va='center',fontsize=11.2)
        ax.set(yticks=y,yticklabels=[f"{r['profile_id']} | {100*r['fee_rate']:.2f}% fee" for r in executed],xlim=(0,53),xlabel='Real drawdown (%)');ax.invert_yaxis();clean(ax)
        ax.legend(loc='lower left',bbox_to_anchor=(-.02,1.01),ncol=2,frameon=False,borderaxespad=0,columnspacing=1.3)
        export(fig,'figure2-client-validation',1.95,
            'Figure 2. Own-horizon Conservative validation for B (15 years) and C (30 years), n=60 per row. Labels give p90 loss / tolerance. All four loss screens fail; each has 7/60 exceedances. A, D and E remain development referrals with no personalized final paths. [E8]',executed)

        chosen=next(r for r in primary if r['mode']=='balanced_cost');sid=int(chosen['severe_scenario_id'])
        assert sid==172
        fig,axes=plt.subplots(1,2,figsize=(WIDTH,2.65));fig.subplots_adjust(left=.10,right=.98,bottom=.24,top=.82,wspace=.36)
        data=[]
        for mode,label,color,style in [('balanced_cost','Fixed Balanced',ORANGE,'-'),('equal_weight_annual','Annual thirds',BLUE,'--')]:
            selected=[r for r in rows(PREFIX+'/generic/'+mode+'/0.0025/annual_ledgers.csv') if int(r['scenario_id'])==sid]
            assert len(selected)==30 and [int(r['year']) for r in selected]==list(range(1,31))
            t=[0];wealth=[100.]
            for r in selected:t.extend([int(r['year'])-1,int(r['year'])]);wealth.extend([float(r['real_wealth_after_fee']),float(r['real_wealth_end'])])
            peak=100.;loss=[]
            for v in wealth:peak=max(peak,v);loss.append(100*(1-v/peak))
            expected=float(chosen['severe_max_real_drawdown_pct']) if mode=='balanced_cost' else 44.16550682905277
            assert abs(max(loss)-expected)<2e-10
            assert all(v>0 for v in wealth)
            axes[0].plot(t,wealth,style,color=color,label=label,lw=1.5)
            axes[1].plot(t,loss,style,color=color,label=label,lw=1.5)
            data.append(dict(mode=mode,scenario_id=sid,year=t,real_wealth=wealth,drawdown_pct=loss,max_drawdown_pct=max(loss)))
        for ax,title,ylabel in zip(axes,['(a) Same-path purchasing power','(b) Running real drawdown'],['Real wealth (initial=100)','Drawdown (%)']):
            ax.set(xlim=(0,30),ylim=(0,None),xlabel='Year',ylabel=ylabel,title=title,xticks=[0,10,20,30]);clean(ax)
        axes[0].legend(loc='lower left',bbox_to_anchor=(-.14,1.13),ncol=2,frameon=False,columnspacing=1.1,borderaxespad=0)
        export(fig,'figure3-severe-path',2.65,
            'Figure 3. Fixed Balanced\'s predeclared severe-case rule selects final scenario 172 (H=30, fee 0.25%). Annual thirds is shown on that same path. Drawdowns are 62.44% and 44.17%, respectively. Curves connect initial, post-fee and year-end observations; they do not reveal intra-year market movements. [E8]',data)
    manifest=dict(schema_version=1,producer_commit=COMMIT,source_sha256=SOURCES,
        figures=FIGURES,original_observations_opened=False,simulation_rerun=False,
        transformations='Filter fixed accepted cases/horizons; plot saved summaries and same-scenario ledgers; recompute running drawdown for display; no smoothing or fitting.',
        matplotlib_version=matplotlib.__version__,status='generated_pending_visual_review')
    (DEST/'figure-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['status'],'figures':len(FIGURES),'output':str(DEST),'source_files':len(SOURCES)}))

if __name__=='__main__':main()
