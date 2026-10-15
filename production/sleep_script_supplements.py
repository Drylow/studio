"""Execute editor-assigned supplementary chapters on the configured provider.

No outline invention, publication, speech synthesis or automatic approval.
"""
import concurrent.futures
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sleep_script_batch import request, system_prompt, wc

base = Path(sys.argv[1])
anchor = Path(sys.argv[2]).read_text(encoding='utf-8')
plans = {}
for name in ['plans-editoriaux.json', 'plans-quiet.json']:
    for p in json.loads((base/name).read_text(encoding='utf-8'))['episodes']:
        plans[p['id']] = p

def execute(job):
    p = plans[job['episode']]
    dest = base/p['id']/'relecture'/'supplements'/f"{job['key']}.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    messages = [
        {'role': 'system', 'content': system_prompt(anchor) +
         '\nFor THIS supplementary section, use the editor target_words below instead of the standard chapter length. Every paragraph must add concrete fictional detail or a distinct original interpretation, not a methodological caveat. No greetings, CTA, spoiler disclaimer, overview or closing recap. This is an internal body section in an existing video.'},
        {'role': 'user', 'content': json.dumps({
            'job': job, 'scope': p['scope'], 'forbidden': p['forbidden'],
            'proof_bank': p['proof'],
            'existing_outline_do_not_repeat': p['chapters'],
            'source_use': 'Paraphrase no source extensively. Scenes are book/episode locators; commentary must be original. Never fabricate quoted dialogue or embellish staging.'
        }, ensure_ascii=False)}]
    text = request(messages, tokens=6500)
    if wc(text) < job['target_words']-120:
        messages += [{'role':'assistant','content':text}, {'role':'user','content':
            f"This has {wc(text)} words. Deliver {job['target_words']} substantive words through the assigned distinct movements. No repeated conclusion, generic cautions or invented scenes. Complete revised narration only."}]
        text = request(messages, tokens=6500)
    dest.write_text(text+'\n', encoding='utf-8')
    print(p['id'],job['key'],wc(text),flush=True)

jobs=json.loads((base/'supplements-editoriaux.json').read_text(encoding='utf-8'))['jobs']
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(execute,jobs))
