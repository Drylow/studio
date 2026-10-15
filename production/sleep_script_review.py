"""Evidence-linked editorial review of completed sleep-script chapter batches.

Review is separate from drafting. A report is a set of quoted findings, not an
approval. Edits are applied only when an exact old string occurs once. Technical
checks and final editorial sign-off remain separate artifacts.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from services import ai, facelessos

if hasattr(sys.stdout,'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
LOCK=threading.Lock()

def digest(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def review_task(plan,base,start,count,round_no,anchor):
    out=base/plan['id']
    end=min(start+count,len(plan['chapters']))
    chapters=[]
    for i in range(start,end):
        path=out/'chapitres'/f'{i+1:02d}.txt'
        if not path.exists():
            return {'episode':plan['id'],'batch':start+1,'status':'not_ready'}
        text=path.read_text(encoding='utf-8').strip()
        chapters.append({'number':i+1,'assignment':plan['chapters'][i], 'text':text,'sha256':digest(text)})
    dest=out/'relecture'/f'passage-{round_no}-chapitres-{start+1:02d}-{end:02d}.json'
    if dest.exists():
        prior=json.loads(dest.read_text(encoding='utf-8'))
        if prior.get('input_hashes')=={str(c['number']):c['sha256'] for c in chapters}:
            return {'episode':plan['id'],'batch':start+1,'status':'already_reviewed'}
    system='''Act as a rigorous editor of ORIGINAL English sleep narration.
Read every supplied chapter fully. You are a prose/evidence reviewer, not an
uploader and not a source of newly invented lore. The editor's supplied proof bank
and specific release scope are authoritative, including released 2026 events.
Do NOT reject a supplied recent-season fact because it is absent from your own
training data. A plan's factual limit overrides a remembered novel/adaptation.

Apply the supplied FacelessOS files with the sleep adaptation: no aggressive
rehooks or suspense requirement, no forced last CTA. Local answers may close
within a chapter. One optional subscribe + listening location/day-or-night
request early in chapter one is expressly requested, and must not be repeated.

Find concrete errors or defects and quote their EXACT text. Empty approval is
not sufficient: also give a one-sentence factual summary and the concrete new
information delivered by EVERY chapter. Review structure and authorial intent:
does it answer its assigned question, contain distinct useful developments,
remain concrete and spoken, and avoid excessive methodological caveats?
Don't rewrite just to prefer your own style. Find repetition, awkward literal
instructions, trailer/aphorism patterns, invented scene details, unsupported
motives, theory stated as fact, adaptation mixing, spoiler violations, present
tense confusion, missing causal steps and copied-sounding stock phrases.

Narration should give the listener lore and thoughtful interpretation, not a
repeated lecture about what counts as evidence. If multiple paragraphs merely
repeat a point, identify the exact least useful passage and propose deletion
or a concise replacement. Do not replace it with new facts unless in the source
constraints. Don't fabricate exact dialogue, numbers, scenes or source citations.

Every replacement must be a local edit: one to three sentences, a full paragraph
only when needed. It must contain narration ONLY, no brackets, notes, reminders,
headings, URLs or labels. Use ASCII punctuation. Your replacement must be safe
to insert literally into the narration. A serious problem that needs more than
a local edit gets a rewrite_required finding with an explanation, not a fake fix.

Return JSON only with this schema:
{
 "chapters":[{"number":1,"summary":"...","new_information":["..."],
   "local_answer":"...","open_issues":["..."],"evidence_notes":"..."}],
 "findings":[{"chapter":1,"kind":"factual|scope|repetition|voice|artifact|structure",
   "severity":"major|minor","quote":"EXACT existing string",
   "reason":"specific violated rule or supplied evidence",
   "replacement":"complete exact replacement string, may be empty to delete",
   "rewrite_required":false}],
 "cross_chapter_repetition":[{"chapters":[1,2],"detail":"..."}],
 "scope_status":"...","limitations":"..."
}
For no defect, findings is empty, but chapter artifacts remain mandatory.
Do not claim you watched episodes, opened websites, measured narration audio,
performed a human read-aloud or verified every fictional fact independently.
'''
    system+='\nVOICE SAMPLE (register, never content or wording):\n'+anchor
    system+='\n'+facelessos.skill('humanizer-skill.md')+'\n'+facelessos.skill('voice-anchoring-skill.md')
    payload={'episode':{k:v for k,v in plan.items() if k!='chapters'},
             'outline':[{'number':i+1,'title':c['title'],'job':c['job']} for i,c in enumerate(plan['chapters'])],
             'chapters':chapters}
    if os.environ.get('AI_TEXT_MODEL'):
        os.environ['AI_TEXT_FALLBACK']=os.environ['AI_TEXT_MODEL']
    result=ai.chat_json([{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
                        reasoning='medium',temperature=0.25,timeout=360,tries=2)
    result['input_hashes']={str(c['number']):c['sha256'] for c in chapters}
    result['review_method']='Configured text review against editor-authored scope, source spine, full chapter text and FacelessOS; not independent viewing or audio measurement.'
    save(dest,result)
    with LOCK:
        print(f"REVIEW {plan['id']} {start+1:02d}-{end:02d} findings={len(result.get('findings',[]))}",flush=True)
    return {'episode':plan['id'],'batch':start+1,'status':'reviewed'}

def apply_reports(base,round_no):
    log=[]
    for report in sorted(base.glob(f'*/relecture/passage-{round_no}-chapitres-*.json')):
        data=json.loads(report.read_text(encoding='utf-8'))
        by={}
        for f in data.get('findings',[]):
            by.setdefault(int(f['chapter']),[]).append(f)
        for chapter,findings in by.items():
            path=report.parents[1]/'chapitres'/f'{chapter:02d}.txt'
            text=path.read_text(encoding='utf-8').strip()
            expected=data['input_hashes'].get(str(chapter))
            if digest(text)!=expected:
                log.append({'report':str(report.relative_to(base)),'chapter':chapter,'status':'stale_input_no_edit'})
                continue
            archive=report.parents[1]/'relecture'/'avant-corrections'/f'passage-{round_no}-{chapter:02d}.txt'
            if not archive.exists():
                archive.parent.mkdir(parents=True,exist_ok=True)
                archive.write_text(text+'\n',encoding='utf-8')
            for f in findings:
                quote=f.get('quote','')
                replacement=f.get('replacement','')
                unsafe=bool(re.search(r'(?i)\[(?:insert|note|verify|source)|^\s*(?:#|Chapter\s+\d)|https?://',replacement,re.M))
                if f.get('rewrite_required') or not quote or text.count(quote)!=1 or unsafe:
                    log.append({'report':str(report.relative_to(base)),'chapter':chapter,'status':'manual_review_required','finding':f})
                    continue
                text=text.replace(quote,replacement,1)
                log.append({'report':str(report.relative_to(base)),'chapter':chapter,'status':'applied','finding':f})
            text=re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+','\n\n',text).strip()
            path.write_text(text+'\n',encoding='utf-8')
    save(base/f'corrections-passage-{round_no}.json',log)
    print(json.dumps({'applied':sum(x['status']=='applied' for x in log),
                      'manual':sum(x['status']=='manual_review_required' for x in log),
                      'stale':sum(x['status']=='stale_input_no_edit' for x in log)}),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('plan',type=Path)
    p.add_argument('--anchor',type=Path)
    p.add_argument('--round',type=int,default=1)
    p.add_argument('--ids',nargs='*')
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--batch-size',type=int,default=4)
    p.add_argument('--through',type=int,default=24)
    p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    base=args.plan.parent
    if args.apply:
        apply_reports(base,args.round)
        return
    if not args.anchor:
        p.error('--anchor required for review')
    anchor=args.anchor.read_text(encoding='utf-8')
    plans=json.loads(args.plan.read_text(encoding='utf-8-sig'))['episodes']
    plans=[x for x in plans if not args.ids or x['id'] in args.ids]
    failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(review_task,plan,base,start,args.batch_size,args.round,anchor):(plan['id'],start+1)
                 for plan in plans for start in range(0,min(args.through,len(plan['chapters'])),args.batch_size)}
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                failures.append({'task':futures[f],'error_type':type(e).__name__,'http_status':getattr(e,'status',None)})
    save(base/f'relecture-execution-{args.plan.stem}-{args.round}.json',{'failures':failures})
    print('REVIEW_COMPLETE failures='+str(len(failures)),flush=True)

if __name__=='__main__':
    main()
