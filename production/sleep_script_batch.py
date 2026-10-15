"""Execute the manually authored sleep-series editorial plans, with checkpoints.

The plan owns topics, chapters, evidence and scope. This runner only calls the
configured text facade, saves drafts, and reports measurable checks. It never
uploads, synthesizes speech, invents chapter plans, or declares editorial approval.
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
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from services import ai, facelessos

LOCK = threading.Lock()
WORDS = re.compile(r"\b[\w]+(?:['-][\w]+)*\b")

def wc(text):
    return len(WORDS.findall(text))

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def clean(text):
    text = text.strip().replace('\r\n', '\n')
    if text.startswith('```'):
        text = re.sub(r'^```[^\n]*\n|\n```$', '', text).strip()
    for src, dst in {'\u2019':"'", '\u2018':"'", '\u201c':'"', '\u201d':'"', '\u00a0':' '}.items():
        text = text.replace(src, dst)
    return text

def request(messages, *, tokens=6500):
    # Keep the existing provider and configured writing selection. No substitute.
    if os.environ.get('AI_TEXT_MODEL'):
        os.environ['AI_TEXT_FALLBACK'] = os.environ['AI_TEXT_MODEL']
    return clean(ai.chat(messages, max_tokens=tokens, temperature=0.65,
                         reasoning='low', timeout=360, tries=3))

def system_prompt(anchor):
    skills = '\n\n'.join(facelessos.skill(f) for f in [
        'voice-anchoring-skill.md', 'humanizer-skill.md',
        'variety-rotation-skill.md', 'greenlight-audit-skill.md'])
    return '''Write original English spoken narration for a long sleep-lore channel.
You execute an editor-authored, source-constrained chapter plan. Do not create or
change the plan. Output narration only, no headings, labels, notes, markdown,
URLs, citations, camera directions, chapter numbers, word counts or disclaimers
about being an AI. Use contractions, concrete examples, varied natural sentences.
This is a patient analytical conversation, not a trailer or plot transcript.

SLEEP ADAPTATION overrides the generic high-energy retention rules below:
No shouted hooks, urgency, countdown, excessive questions, repeated teasers,
requests to stay awake or wait for a reveal. Resolve local questions in the same
chapter. A gentle transition can join chapters, but do not promise the next one
will explain everything. No stock soothing paragraphs to fill space, no repeated
bedtime instructions, no recap at each section, no concluding sales pitch.
The narrator does not claim personal experiences, interviews, fandom consensus,
having watched footage, scientific expertise or access to unreleased material.

EVIDENCE DISCIPLINE:
Use the checked facts in this plan and established events of the specifically
named works that directly explain the assigned topic. The proof bank is a
starting spine, not permission to turn a scene into a lecture on epistemology.
Do not invent dialogue,
tiny props, blocking, weather, dates, quantities, historical details, production
intent, unseen scenes, hidden motives or future answers. Give specific scene or
book context in ordinary prose. A character's claim is testimony, not truth.
State an inference as an inference in the sentence where you make it. An
alternative interpretation must respect the shown facts and must have a reason
for being considered. Avoid empty lists of equally unlikely possibilities.
Do not summarize a critic's article. Tell the lore and explain the fictional
situations in your own words. No verbatim dialogue from the works or sources.
Most of the chapter should be concrete worldbuilding, character experience and
what actually happens. Discuss the implications in natural language. Make a
caution only where a viewer could otherwise mistake a theory for a shown fact.
Do not repeat 'the scene establishes', 'the evidence supports', 'we can infer',
'this doesn't prove', 'we don't need to invent', 'a reasonable competing reading',
or lectures on evidence standards. These are EDITOR instructions, never a
recurring narrator voice. Ordinary confirmed plot facts can be stated directly.
Give specific people, objects, places and actions, rather than abstract accounts
of power, authority, control, dependence or relationships without a scene.
The audience wants to spend time in these fictional worlds with an informed,
relaxed narrator. It does not want a philosophy class about judging information.
STYLE CALIBRATION, original editor examples:
Good: 'The Guild carries ships belonging to rival Houses inside the same enormous
heighliner. Those Houses may be enemies, but while their vessels are aboard, the
Guild controls the conditions of passage. Leto can command his own soldiers. He
still needs someone else to carry them to Arrakis.'
Bad: 'This gives us a useful way to separate ownership from reach. The scene
doesn't establish every detail, and we don't need to invent the loading process.'
Good: 'Gurney teaches Paul to slow the blade as it meets a shield. A fast strike
will stop at the barrier. In a real fight, the move that feels most urgent can
leave him unable to reach the man standing in front of him.'
Bad: 'The result has a narrower meaning. We should distinguish training from an
automatic guarantee. The lesson establishes a particular capacity in a student.'
The good examples are a register target, not text to copy into unrelated chapters.
When detail is unverified, omit it without telling the listener about the omission.
You do NOT need to narrate all the 'do not' cautions written in the editor's plan.
At least two thirds of paragraphs should contain specific fictional actions,
setting facts, or character interactions. No paragraph whose only purpose is to
repeat that a scene proves less than it appears, information is incomplete, or
knowledge differs from control. A chapter may have ONE short caveat for an actual
unconfirmed theory. Don't spend half its runtime on epistemic caution.
No generic hypothetical customer, teacher, student, organization or witness when
the fictional person or institution can be named and their actual situation told.
Never borrow the anchor's words, biography, greetings, content or personal tics.
Follow the chapter's exact job; don't retell material assigned to other chapters.

LENGTH:
Write 900-1,040 substantive words per chapter. Count carefully. Expand through
different concrete details and relevant examples from the named work, not restatement. A
chapter should develop several distinct movements of the local story, the
worldbuilding involved, a relevant comparison and the character consequence.
Most chapters do not need a competing reading or a discussion of a boundary.
Use these flexibly, not as a recurring visible formula. Do not announce them.
Use 10-16 natural paragraphs, mostly 55-110 words. Each paragraph must add
information, an implication, a specific comparison or an evidence-based objection.

LANGUAGE:
ASCII punctuation only. No em/en dash or double-hyphen substitute. No mirrored
antithesis slogans such as 'not X but Y', 'this isn't X, it's Y', 'less X, more Y'.
No headings. Never use machine-banned words/phrases from the skill pack. Do not
reuse the same abstract takeaway across chapters, especially 'control', 'trust',
'memory', 'choice', unless you explain a new particular mechanism or scene.

The supplied genuine transcript is a register sample only; its errors and claims
are NOT evidence, and its phrases must not be copied.
RAW REGISTER SAMPLE:
''' + anchor + '\n\nAPPLIED SKILLS (read as supplied):\n' + skills

def write_episode(plan, base, anchor, only_chapter=None):
    out = base / plan['id']
    chapters = out / 'chapitres'
    chapters.mkdir(parents=True, exist_ok=True)
    sysmsg = system_prompt(anchor)
    outline = '\n'.join(f"{i+1:02d}. {c['title']}: {c['job']}" for i,c in enumerate(plan['chapters']))
    previous = ''
    completed = []
    for i, chapter in enumerate(plan['chapters']):
        dest = chapters / f'{i+1:02d}.txt'
        if dest.exists() and wc(dest.read_text(encoding='utf-8')) >= 850:
            text = dest.read_text(encoding='utf-8').strip()
            previous = text[-3200:]
            completed.append({'chapter':i+1, 'words':wc(text), 'sha256':hashlib.sha256(text.encode()).hexdigest()})
            continue
        if only_chapter is not None and i+1 != only_chapter:
            continue
        instructions = {
            'channel':plan['channel'], 'video_title':plan['title'],
            'angle':plan['angle'], 'scope':plan['scope'],
            'forbidden_claims':plan['forbidden'],
            'proof_bank':plan['proof'], 'whole_episode_outline':outline,
            'chapter_number':i+1, 'chapter_to_write':chapter,
            'previous_ending_do_not_repeat':previous,
        }
        special = ''
        if i == 0:
            special = '''The first paragraph is a concrete hook under 100 words,
matching this chapter's hook direction. It clearly promises the actual topic.
In the second paragraph name the spoiler boundary concisely. After the first
substantive observation, at 180-300 words, include ONE brief optional request to
subscribe to this channel and comment where the listener is and whether it is
day or night there. No Patreon, sponsors, like request, alarm or urgency.
No generic 'hello and welcome' intro. Don't promise an exact audio runtime.'''
        elif i == len(plan['chapters'])-1:
            special = '''This is the final chapter. Complete the final substantive
insight and finish naturally on a concrete image or consequence grounded in the
allowed facts. No recap of all chapters, thanks, CTA, 'in conclusion', 'goodnight',
future upload promise or abrupt new mystery.'''
        else:
            special = '''Continue within the same video. No new greeting, title,
scope disclaimer, subscribe/comment request, bedtime invitation or episode recap.
Open directly on this chapter's particular detail. Don't restate the last ending.'''
        messages = [{'role':'system','content':sysmsg},
                    {'role':'user','content':json.dumps(instructions,ensure_ascii=False)+'\n'+special}]
        text = request(messages)
        before = wc(text)
        if before < 870 or before > 1250:
            messages += [{'role':'assistant','content':text}, {'role':'user','content':
                f'This draft has {before} words. Revise to 900-1040 words. Add concrete lore, relevant established scene details and character consequences from the named works if short; remove redundant explanations if long. Never add a repetitive lecture about how evidence works. Preserve evidence boundaries. Output complete revised narration only.'}]
            text = request(messages)
        scan = facelessos.scan([(chapter['title'],text)])
        if scan['hard'] or scan['mech'] or re.search(r'^\s*(?:#|\*\*|\[|Chapter\s+\d)',text,re.M):
            messages += [{'role':'assistant','content':text}, {'role':'user','content':
                'Rewrite this chapter, preserving its length and substance, to fix these exact mechanical findings. No headings. Output the COMPLETE revised narration only. '+json.dumps({'hard':scan['hard'],'mech':scan['mech']})}]
            text = request(messages)
        dest.write_text(text+'\n', encoding='utf-8')
        previous = text[-3200:]
        completed.append({'chapter':i+1,'words':wc(text),'sha256':hashlib.sha256(text.encode()).hexdigest()})
        save_json(out/'progression.json',{'state':'drafting','completed':completed,'planned_chapters':len(plan['chapters'])})
        with LOCK:
            print(f"DRAFT {plan['id']} {i+1:02d}/{len(plan['chapters'])} {wc(text)} words",flush=True)
    if only_chapter is None:
        parts = [(c['title'],(chapters/f'{i+1:02d}.txt').read_text(encoding='utf-8').strip()) for i,c in enumerate(plan['chapters'])]
        body = '\n\n\n'.join(t for _,t in parts)+'\n'
        (out/'script-voix.txt').write_text(body, encoding='utf-8')
        (out/'titre.txt').write_text(plan['title']+'\n', encoding='utf-8')
        scan = facelessos.scan(parts)
        (out/'scan.txt').write_text(facelessos.scan_report(scan), encoding='utf-8')
        save_json(out/'controle-technique.json',{
            'status':'draft_complete_editorial_review_pending','words':wc(body),
            'whitespace_words':len(body.split()),'chapters':completed,
            'estimated_minutes_at_wpm':{str(w):round(wc(body)/w,1) for w in [145,150,160,170]},
            'measured_audio_duration':None,'scan_counts':{k:len(v) for k,v in scan.items()},
            'narration_sha256':hashlib.sha256(body.encode()).hexdigest()})
        save_json(out/'progression.json',{'state':'draft_complete_editorial_review_pending','completed':completed,'planned_chapters':len(plan['chapters'])})
    return plan['id']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('plan',type=Path)
    p.add_argument('--ids',nargs='*')
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--chapter',type=int)
    p.add_argument('--anchor',type=Path,required=True)
    args=p.parse_args()
    data=json.loads(args.plan.read_text(encoding='utf-8-sig'))
    anchor=args.anchor.read_text(encoding='utf-8')
    plans=[x for x in data['episodes'] if not args.ids or x['id'] in args.ids]
    failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending={pool.submit(write_episode,x,args.plan.parent,anchor,args.chapter):x['id'] for x in plans}
        for future in concurrent.futures.as_completed(pending):
            episode=pending[future]
            try:
                future.result()
                print('COMPLETE '+episode,flush=True)
            except Exception as e:
                # Network errors may contain credentials or provider identifiers.
                failures.append({'episode':episode,'error_type':type(e).__name__,'http_status':getattr(e,'status',None)})
                print('FAILED '+episode+' '+type(e).__name__+' status='+str(getattr(e,'status',None)),flush=True)
    save_json(args.plan.parent/'execution.json',{'failures':failures,'episodes_requested':[x['id'] for x in plans]})
    return bool(failures)

if __name__=='__main__':
    raise SystemExit(main())
