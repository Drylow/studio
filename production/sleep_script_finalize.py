"""Assemble existing chapter text and report verifiable delivery properties.

No text-generation calls. No approval inferred from a word count or scanner.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services import facelessos

if hasattr(sys.stdout,'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def count(text):
    return len(re.findall(r"\b[\w]+(?:['-][\w]+)*\b",text))

def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('base',type=Path)
    p.add_argument('--reference-file',type=Path)
    p.add_argument('--round',type=int,default=2)
    args=p.parse_args()
    base=args.base
    plans=[]
    for name in ['plans-editoriaux.json','plans-quiet.json']:
        plans+=json.loads((base/name).read_text(encoding='utf-8'))['episodes']
    refs=[]
    if args.reference_file:
        refs=json.loads(args.reference_file.read_text(encoding='utf-8'))['items']
    ref_grams={}
    for ref in refs:
        words=re.findall(r"[a-z]+(?:'[a-z]+)?",ref['text'].lower())
        for i in range(len(words)-11):
            ref_grams.setdefault(' '.join(words[i:i+12]),set()).add(ref['id'])
    summaries=[]
    all_paragraphs={}
    for plan in plans:
        out=base/plan['id']
        parts=[]
        chapter_data=[]
        offset=0
        missing=[]
        for i,c in enumerate(plan['chapters']):
            path=out/'chapitres'/f'{i+1:02d}.txt'
            if not path.exists():
                missing.append(i+1)
                continue
            text=path.read_text(encoding='utf-8').strip()
            parts.append((c['title'],text))
            words=count(text)
            chapter_data.append({'number':i+1,'title':c['title'],'file':f'chapitres/{i+1:02d}.txt',
                'words':words,'start_word':offset,'end_word':offset+words,
                'estimated_start_seconds_at_150_wpm':round(offset/150*60),
                'measured_timestamp':None,'sources':c['sources'],'sha256':sha(text)})
            offset+=words
        if missing:
            summaries.append({'id':plan['id'],'state':'missing_chapters','missing':missing})
            continue
        body='\n\n\n'.join(t for _,t in parts)+'\n'
        (out/'script-voix.txt').write_text(body,encoding='utf-8')
        (out/'titre.txt').write_text(plan['title']+'\n',encoding='utf-8')
        scan=facelessos.scan(parts)
        (out/'scan-final.txt').write_text(facelessos.scan_report(scan)+'\n',encoding='utf-8')
        save(out/'chapitres.json',{'timing_note':'Word offsets are exact under the documented regex. Times at 150 wpm are estimates, NOT publication timestamps. Generate YouTube chapters from the final measured audio/video.','chapters':chapter_data})
        repeated=[]
        for title,text in parts:
            for para in re.split(r'\n\s*\n',text):
                norm=' '.join(re.findall(r'\w+',para.lower()))
                if len(norm.split())<20:
                    continue
                key=sha(norm)
                if key in all_paragraphs:
                    repeated.append({'chapter':title,'previous':all_paragraphs[key]})
                else:
                    all_paragraphs[key]={'episode':plan['id'],'chapter':title}
        words_ref=re.findall(r"[a-z]+(?:'[a-z]+)?",body.lower())
        matches={}
        for i in range(len(words_ref)-11):
            gram=' '.join(words_ref[i:i+12])
            if gram in ref_grams:
                matches[gram]=sorted(ref_grams[gram])
        final_hashes={str(c['number']):c['sha256'] for c in chapter_data}
        covered={}
        unresolved=[]
        for report in sorted((out/'relecture').glob(f'passage-{args.round}-chapitres-*.json')):
            data=json.loads(report.read_text(encoding='utf-8'))
            for number,h in data.get('input_hashes',{}).items():
                if final_hashes.get(number)==h:
                    covered[number]=str(report.name)
            unresolved += [{'report':report.name,**f} for f in data.get('findings',[])]
        tech={
            'text_status':'assembled_not_an_editorial_approval',
            'words':count(body),'whitespace_words':len(body.split()),'chapters':len(parts),
            'duration_estimates_minutes':{str(w):round(count(body)/w,1) for w in [145,150,160,170]},
            'duration_measured_seconds':None,'audio_gate':'Measure final narration: at least 120 minutes before publishing. No padding, silence or loops.',
            'two_hours_at_170_wpm':count(body)>=20400,
            'scanner':{k:len(v) for k,v in scan.items()},
            'non_ascii_characters':sorted(set(c for c in body if ord(c)>127)),
            'headings_or_placeholders':re.findall(r'(?im)^\s*(?:#{1,6}\s|\*\*|chapter\s+\d|\[(?:visual|note|insert|todo|verify))[^\n]*',body),
            'subscribe_occurrences':len(re.findall(r'\bsubscribe\b',body,re.I)),
            'last_chapter_has_subscribe':bool(re.search(r'\bsubscribe\b',parts[-1][1],re.I)),
            'identical_long_paragraphs':repeated,
            'exact_12_word_reference_matches':[{'phrase':k,'reference_ids':v} for k,v in matches.items()],
            'review_round':args.round,'current_chapters_covered_by_review':len(covered),
            'review_findings_for_editor':unresolved,
            'narration_sha256':sha(body),
            'method':'Mechanical checks plus separate quoted editorial reports. Neither establishes actual audio duration or a complete independent episode/book viewing.'
        }
        approval_path=out/'validation-editoriale.json'
        if approval_path.exists():
            approval=json.loads(approval_path.read_text(encoding='utf-8'))
            if approval.get('narration_sha256')==tech['narration_sha256']:
                tech['editorial_validation']=approval
                tech['text_status']='final_text_editorially_reviewed_audio_pending'
                tech['review_findings_before_final_local_edits']=unresolved
                tech['review_findings_for_editor']=approval.get('remaining_findings',[])
                tech['review_coverage_note']='Hash matches count unchanged review inputs. Other chapters received recorded local edits after the integrated review; final editorial acceptance is bound to this narration hash.'
        save(out/'controle-final.json',tech)
        summaries.append({'id':plan['id'],'title':plan['title'],'channel':plan['channel'],
            'script':f"{plan['id']}/script-voix.txt",'words':tech['words'],
            'minutes_at_150_wpm':tech['duration_estimates_minutes']['150'],
            'minutes_at_170_wpm':tech['duration_estimates_minutes']['170'],
            'two_hours_at_170_wpm':tech['two_hours_at_170_wpm'],
            'hard_bans':len(scan['hard']),'mechanical_flags':len(scan['mech']),
            'non_ascii':len(tech['non_ascii_characters']),
            'review_coverage':len(covered),'review_findings':len(tech['review_findings_for_editor']),
            'final_text_editorially_validated':tech['text_status']=='final_text_editorially_reviewed_audio_pending',
            'sha256':tech['narration_sha256']})
    save(base/'livraison-mesures.json',{'date':'2026-10-15','measured_audio':False,'episodes':summaries})
    print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
