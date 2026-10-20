"""Add three evidence-bound figures to accepted manuscript text.

The old accepted PDF is preserved. Optionally apply the separately recorded
AI-disclosure wording revision. No policy, result or final exposure is changed.
"""
import argparse,hashlib,json,re,sys
from datetime import datetime,timezone
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'report'))
import build_submission as original

def sha(raw):return hashlib.sha256(raw).hexdigest()

def render(text,output,figures):
    from pypdf import PdfReader
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer,Table,TableStyle,Image,KeepTogether
    body=ParagraphStyle('body',fontName='Times-Roman',fontSize=11.2,leading=13.4,spaceAfter=6)
    heading=ParagraphStyle('heading',parent=body,fontName='Times-Bold',fontSize=13,leading=16,spaceBefore=9,spaceAfter=7,keepWithNext=True)
    title=ParagraphStyle('title',parent=heading,fontSize=19,leading=23)
    cell=ParagraphStyle('cell',parent=body,fontSize=11,leading=12.5,spaceAfter=0)
    caption=ParagraphStyle('caption',parent=body,fontSize=11,leading=12.2,spaceAfter=7)
    story=[];lines=text.splitlines();index=0;paragraph=[];usable=A4[0]-78
    def html(value):
        value=escape(value);value=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',value)
        return re.sub(r'\b[0-9a-f]{40}\b',lambda m:'<wbr/>'.join(m[0][i:i+10] for i in range(0,40,10)),value)
    def flush():
        if paragraph:story.append(Paragraph(html(' '.join(paragraph)),body));paragraph.clear()
    while index<len(lines):
        line=lines[index]
        if line.startswith('[[FIGURE:'):
            flush();ident=line[len('[[FIGURE:'):-2];f=figures[ident]
            raw=(ROOT/f['path']).read_bytes();assert sha(raw)==f['sha256']
            height=f['height_inches']*72
            image=Image(str(ROOT/f['path']),width=usable,height=height,hAlign='CENTER')
            story.append(KeepTogether([Spacer(1,4),image,Spacer(1,4),Paragraph(html(f['caption']),caption)]))
        elif line.startswith('<!--'):
            flush()
        elif line.startswith('|'):
            flush();rows=[]
            while index<len(lines) and lines[index].startswith('|'):
                values=[x.strip() for x in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',x) for x in values):rows.append([Paragraph(html(x),cell) for x in values])
                index+=1
            n=len(rows[0]);widths={8:[105,58,49,56,49,53,60,65],6:[43,41,70,64,54,223],5:[90,100,100,108,107],4:[205,100,100,100]}.get(n)
            if n==6 and rows[0][0].getPlainText()=='Candidate / control':widths=[185,65,65,80,65,50]
            if n==6 and rows[0][0].getPlainText()=='Fee %':widths=[70,90,80,85,100,100]
            if widths:widths=[usable*w/sum(widths) for w in widths]
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT',rowSplitRange=(3,-2))
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8edf1')),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#607483')),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.extend([table,Spacer(1,7)]);continue
        elif line.startswith('#'):
            flush();story.append(Paragraph(html(line.lstrip('# ')),title if line.startswith('# ') else heading))
        elif not line.strip():flush()
        else:paragraph.append(line)
        index+=1
    flush()
    def decorate(canvas,doc):
        canvas.saveState();canvas.setFont('Times-Roman',11);canvas.setFillColor(colors.HexColor('#5b6670'))
        canvas.drawString(39,817,'SafeInvest - development and frozen final evidence')
        canvas.drawString(39,25,'SafeInvest | Scenario study in purchasing power');canvas.drawRightString(A4[0]-39,25,str(doc.page));canvas.restoreState()
    def stable_canvas(*args,**kwargs):return Canvas(*args,**{**kwargs,'invariant':1})
    pdf=output/'SafeInvest-final-illustrated.pdf'
    SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=39,rightMargin=39,topMargin=43,bottomMargin=43,title='SafeInvest evidence-bound illustrated manuscript',author='SafeInvest project').build(story,onFirstPage=decorate,onLaterPages=decorate,canvasmaker=stable_canvas)
    reader=PdfReader(pdf);sizes=[];images=[];captions=[]
    for number,page in enumerate(reader.pages,1):
        page_text=page.extract_text(visitor_text=lambda t,cm,tm,font,size:sizes.append(float(size)) if t.strip() else None)
        assert abs(float(page.mediabox.width)-A4[0])<.02 and abs(float(page.mediabox.height)-A4[1])<.02
        assert 'REVIEW COPY' not in page_text
        images.append(len(list(page.images)))
        captions.extend((ident,number) for ident in (1,2,3) if 'Figure '+str(ident)+'.' in page_text)
    assert min(sizes)>=11 and sum(images)==3 and len(captions)==3
    return dict(pdf_sha256=sha(pdf.read_bytes()),pages=len(reader.pages),paper='A4',minimum_font_pt=min(sizes),within_page_limit=len(reader.pages)<=10,images_per_page=images,captions=captions,visual_review='pending')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True)
    p.add_argument('--revised-disclosure',action='store_true',help='Apply the user-requested team-centered AI disclosure after verifying the accepted manuscript.')
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--team-file');group.add_argument('--public',action='store_true');a=p.parse_args()
    output=(ROOT/a.output_dir).resolve();assert output.is_relative_to(ROOT/'.runtime') and not output.exists()
    output.mkdir(parents=True)
    if a.public:
        team=output/'public-display.json';team.write_text(json.dumps({'report_display':'Team members: [omitted in public reproduction].'}),encoding='utf-8')
    else:team=(ROOT/a.team_file).resolve()
    assert team.is_relative_to(ROOT/'.runtime')
    text,metadata=original.assemble(team);text,approval=original.release_evidence(text,team)
    old=ROOT/'.runtime/final-release-20261020/expanded-draft.md'
    if old.exists() and not a.public:assert text==old.read_text(encoding='utf-8'),'Accepted original text changed.'
    disclosure_revision=None
    if a.revised_disclosure:
        previous=text.rstrip().split('\n\n')[-1]
        assert previous.startswith('GPT-6 Astra xhigh, followed by GPT-6.1 Sol xhigh')
        revised=(ROOT/'report/ai-disclosure-revised.txt').read_text(encoding='utf-8').strip()
        assert text.count(previous)==1 and revised.startswith('Our team used ')
        text=text.replace(previous,revised,1)
        disclosure_revision={'old':previous,'new':revised,'scope':'Final AI-use paragraph only; no numerical or methodological changes.'}
    manifest=json.loads((ROOT/'report/figures/illustrated-final-v1/figure-provenance.json').read_bytes())
    figures={f['id']:f for f in manifest['figures']}
    anchors=[('figure1-final-comparison','The frozen B/C Conservative follow-ups use'),('figure2-client-validation','All four rows fail the unchanged loss screen'),('figure3-severe-path','An independently expressed stdlib audit passed')]
    augmented=text
    for ident,anchor in anchors:
        assert augmented.count(anchor)==1
        augmented=augmented.replace(anchor,'[[FIGURE:'+ident+']]\n\n'+anchor,1)
    assert re.sub(r'\[\[FIGURE:[^\]]+\]\]\n\n','',augmented)==text
    (output/'expanded-illustrated.md').write_text(augmented,encoding='utf-8')
    checks=render(augmented,output,figures)
    assert checks['within_page_limit'],checks
    record=dict(status='illustrated_revision_pending_visual_review',created_at=datetime.now(timezone.utc).isoformat(),old_pdf_sha256='1730702256151770090fad81aef16922c1f58064beda91c5ce57444a32853385',accepted_text_unchanged=True,added_captions=[f['caption'] for f in figures.values()],pdf_checks=checks,underlying_independent_reviews=approval,final_policy_changed=False,simulation_rerun=False,original_observations_opened=False,private_pdf_local_only=True,is_public_reproduction=a.public)
    record['accepted_text_unchanged']=not a.revised_disclosure
    record['disclosure_revision']=disclosure_revision
    (output/'build-provenance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':record['status'],**checks}))

if __name__=='__main__':main()
