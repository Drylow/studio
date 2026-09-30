#!/usr/bin/env python3
# FacelessOS v5 scanner. Run this over your voiceover script before recording.
# Catches "trailer voice" and hard-banned AI-slop phrases before you hit record on the voiceover.
"""
trailer-voice-scan.py: pre-recording voice check for your FacelessOS scripts.

Flags candidate MOVIE TRAILER / WISE NARRATOR / STACCATO-ROBOTIC / READING-NOT-SPEAKING
shapes in the likely-spoken paragraphs of your script files.

DOCTRINE (do not skip): this scanner FLAGS, it does not FAIL. Every hit gets judged by
the shape test: "have you ever actually said a sentence with this shape?"
Expected FALSE POSITIVES that are real speech, leave them alone:
  - enumerations ("Save up. Pay cash. Stay out of debt." / "Number nine. Graz, in Austria.")
  - live-demo narration ("Now listen. This is before." / "Checks done. Now the satisfying part.")
  - natural self-correction ("I'm not. I'm wrong constantly.")
  - a verified verbal tic that's genuinely how you talk
Real POSITIVES look like: "Not smaller. Gone." / "The exhaustion is daily." /
"Monitoring is the thermometer. Execution is the medicine." / "you'll never look at X the same way"

The scanner reads plain text paragraphs and skips bullets, headers, and bold-prefixed
lines. Format your voiceover copy as plain paragraphs when scanning.

Usage: python3 trailer-voice-scan.py your-script.md [more files or globs...]
"""
import re, sys, glob as g

# HARD-BAN SLOP. These are ABSOLUTE in spoken copy. A verified verbal tic NEVER licenses one
# of these. Quirky personal tics stay, but phrases on THIS list never get written even if you
# say them in every recording. The ONLY sanctioned pivot is the literal "Let's get into it",
# max once, where it is your channel's earned convention.
HARD_BAN = [
 (r"\blet'?s dive(?: in| into)?\b|\bdive into it\b", 'HARD-BAN: let\'s dive in/into'),
 (r"\blet'?s break (?:this|it) down\b", 'HARD-BAN: let\'s break this down'),
 (r"\bwithout further ado\b", 'HARD-BAN: without further ado'),
 (r"\blet'?s unpack\b", 'HARD-BAN: let\'s unpack'),
 (r"\blet'?s jump (?:in|into)\b", 'HARD-BAN: let\'s jump in'),
 (r"\bbuckle up\b", 'HARD-BAN: buckle up'),
 (r"\bhere'?s the kicker\b", 'HARD-BAN: here\'s the kicker'),
 (r"\bdelve\b|\btapestry\b|\bunleash\b|\brobust\b", 'HARD-BAN: slop vocab'),
 (r"\bgame.?changer\b", 'HARD-BAN: game-changer'),
 (r"\bin today'?s (?:world|day and age)\b", 'HARD-BAN: dated-opener slop'),
 (r"\b(?:evolving|shifting|changing|ever[- ]changing|current|modern|competitive|digital)\s+landscape\b", 'HARD-BAN: landscape-metaphor slop'),
]
# v5 divergences (deliberate): (A) hard-ban matching is case-insensitive so sentence-initial
# capitals ("Let's dive in.") still fire. The TELLS below stay case-sensitive on purpose.
# The capital "In" of the trailer-open pattern is load-bearing against false positives.
# (D) restored robust / "in today's world" / landscape-metaphor hard-bans that the source
# prose (humanizer H4, greenlist banned-words) declared but the gate scanner omitted; the
# landscape ban is metaphor-only, so bare literal "landscape" (nature/history/travel) passes.
HARD_BAN = [(re.compile(rx, re.IGNORECASE), name) for rx, name in HARD_BAN]

TELLS = HARD_BAN + [
 (r'\bNot [a-z]+\. [A-Z]', 'not-X-period beat'),
 (r'\. Not [a-z][^.]{0,30}\.', 'trailing "Not Y." beat'),
 (r'\btells you everything\b', 'aphoristic "tells you everything"'),
 (r'\bchanges everything\b', 'aphoristic "changes everything"'),
 (r'\bsays everything about\b', 'aphoristic "says everything"'),
 (r'\bnothing would ever be the same\b|\bnever the same again\b', 'narrator prophecy'),
 (r"\byou'?ll never look at\b|\byou will never look at\b", 'second-person prophecy'),
 (r'\bIn a world\b', 'trailer open'),
 (r'\bThis is the story of\b', 'narrator open'),
 (r'\bwhat happens next\b', 'narrator tease'),
 (r'\bone at a time\b', 'parallel-fall cadence (judge in context)'),
 (r'\bThe rest, as they say\b', 'narrator cliche'),
 (r'\bis the (thermometer|medicine|engine|fuel|currency|architecture) of\b|\bis the \w+\. \w+ is the \w+\.', 'clever written pair'),
 (r"(?i)\b(countless|numerous|myriad|innumerable|a plethora of|vast (?:amounts|majority|swaths)(?: of)?|tons of|huge amounts of)\b", 'vague-quantity hedge (H19: use the real number)'),
]

# ANTITHESIS/REFRAME FLOOR (v5.1). Mechanical minimum for the greenlight audit's D6-Pattern-4 /
# D7 family count. Field report (Jul 2026): an audit run from memory reported D7 "clean" while
# the script actually held 5 constructions; only a mechanical count caught it. This floor gives
# the D7 ledger a number it can never undercut: if the audit's ledger lists FEWER instances than
# the floor found, the ledger is wrong, redo the scan.
# FLOOR SEMANTICS: these hits are a MINIMUM, not the whole family. Most antithesis is
# machine-invisible (mirrored clauses share no fixed tokens), so a floor of 0 clears nothing.
FLOOR = [
 (r"(?i)\b(?:is|was|are|were|do|does|did|has|had)n['’]?t\b[^.!?\n]{2,50}?[.,;]\s*(?:it|that|this)\b(?:['’]s|\s+(?:is|was))\b", "reframe: isn't X, it's Y"),
 (r"(?i)\bnot\s+(?:about|just|only|merely)\b[^.!?\n]{0,50}?[.,;]\s*(?:it['’]?s|it\s+(?:is|was)|that['’]?s|this is|but)\b", "reframe: not just X, it's Y"),
 (r"(?i)\bless\s+\w+[^.!?\n]{0,25},\s*more\s+\w+\b", "reframe: less X, more Y"),
 (r"\bNot [a-z]+\. [A-Z]", "not-X-period beat"),
 (r"\. Not [a-z][^.]{0,30}\.", 'trailing "Not Y." beat'),
 (r'\bis the (thermometer|medicine|engine|fuel|currency|architecture) of\b|\bis the \w+\. \w+ is the \w+\.', "clever written pair"),
]
FLOOR = [(re.compile(rx), name) for rx, name in FLOOR]

# ECHO CHECK (v5.1, H18). Mechanical floor for the document-scale echo tell: the script getting
# stuck on one fact or phrase and re-stating it with nothing new attached. Two detectors:
# (1) a distinctive 4-word phrase appearing 3+ times verbatim, (2) a specific number or dollar
# amount appearing 4+ times. Same floor semantics as everything here: flags, not fails; a year
# that anchors a timeline can legitimately repeat, so judge each hit. But a fact echoed five
# times with no new information each time is the H18 tell, cut or advance it.
ECHO_STOP = set(("the a an and or but so of to in on at for from with that this those these it its is was are "
                 "were has had have will would could been being as by he she they we you his her their our not").split())

def echo_check(text):
    from collections import Counter
    grams = Counter()
    numbers = Counter()
    for para in spoken_paras(text):
        words = [w.strip(".,'\"") for w in re.findall(r"[A-Za-z0-9$.,'\"]+", para.lower())]
        words = [w for w in words if w]
        for i in range(len(words) - 3):
            gram = tuple(words[i:i+4])
            if all((w in ECHO_STOP or len(w) < 5) and not any(c.isdigit() for c in w) for w in gram):
                continue
            grams[gram] += 1
        for tok in re.findall(r"\$[\d][\d,.]*|\b\d[\d,.]*\b", para):
            numbers[tok.rstrip('.,')] += 1
    hits, seen = [], []
    for gram, n in grams.most_common():
        if n < 3:
            break
        if any(len(set(gram) & set(g)) >= 3 for g in seen):
            continue
        seen.append(gram)
        hits.append(f"  [echo H18: phrase repeated {n}x] \"{' '.join(gram)}\"")
    for tok, n in numbers.most_common():
        if n >= 4:
            hits.append(f"  [echo H18: fact repeated {n}x] \"{tok}\" (each mention past the second must add something new)")
    return hits

def antithesis_floor(text):
    """Count machine-catchable antithesis/reframe shapes in spoken paragraphs.
    Overlapping matches across patterns are deduped so one construction = one hit."""
    hits = []
    for para in spoken_paras(text):
        spans = []
        for rx, name in FLOOR:
            for m in rx.finditer(para):
                if any(m.start() < e and m.end() > s for s, e in spans):
                    continue
                spans.append((m.start(), m.end()))
                ctx = para[max(0, m.start()-30):m.end()+30].replace('\n', ' ')
                hits.append(f"  [floor: {name}] ...{ctx}...")
    return hits

def spoken_paras(text):
    """plain paragraphs = likely word-for-word blocks (not bullets/headers/italic notes)"""
    for para in text.split('\n\n'):
        s = para.strip()
        if not s:
            continue
        first = s.lstrip()[0]
        if first in '-#*(>|`[':
            continue
        if s.startswith('**'):
            continue
        yield s

def short_sents(para):
    sents = [x.strip() for x in re.split(r'(?<=[.!?]) +', para) if x.strip()]
    shorts = [x for x in sents if len(x.split()) <= 4 and x[-1:] in '.!'
              and not x.lower().startswith(('let', 'so', 'ok', 'okay', 'yeah', 'yes', 'no,', 'go.', 'now,'))]
    return shorts, len(sents)

def scan(path):
    text = open(path, encoding='utf8', errors='ignore').read()
    if 'SUPERSEDED' in text[:200]:
        return []
    hits = []
    for para in spoken_paras(text):
        for rx, name in TELLS:
            for m in re.finditer(rx, para):
                ctx = para[max(0, m.start()-40):m.end()+40].replace('\n', ' ')
                hits.append(f"  [{name}] ...{ctx}...")
        shorts, total = short_sents(para)
        if len(shorts) >= 2:
            head = para[:70].replace(chr(10), ' ')
            hits.append(f"  [staccato x{len(shorts)}/{total}] " + " | ".join(f'"{s}"' for s in shorts[:4]) + f"  << {head}...")
    return hits

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 trailer-voice-scan.py your-script.md [more files or globs...]")
        sys.exit(0)
    files = sorted(set(f for a in args for f in (g.glob(a) or [a])))
    total = 0
    floor_total = 0
    for f in files:
        try:
            hits = scan(f)
            text = open(f, encoding='utf8', errors='ignore').read()
            superseded = 'SUPERSEDED' in text[:200]
            fhits = [] if superseded else antithesis_floor(text)
            ehits = [] if superseded else echo_check(text)
        except OSError as e:
            print(f"!! {f}: {e}"); continue
        if hits or fhits or ehits:
            total += len(hits)
            floor_total += len(fhits)
            print('=' * 100); print(f)
            for h in hits[:12]:
                print(h)
            if fhits:
                print(f"  -- ANTITHESIS/REFRAME FLOOR: {len(fhits)} hit(s) (greenlight D6-P4/D7 ledger minimum)")
                for h in fhits[:8]:
                    print(h)
            if ehits:
                print(f"  -- ECHO CHECK (H18): {len(ehits)} hit(s)")
                for h in ehits[:8]:
                    print(h)
    print(f"\n{total} candidate flags across {len(files)} files. Judge each flag by the shape test in voice-anchoring-skill.md: have you ever actually said a sentence with this shape? Enumerations are real speech, leave them alone.")
    print(f"Antithesis/reframe floor: {floor_total} mechanical hit(s). This is the MINIMUM for the greenlight D7 ledger: a ledger listing fewer instances than the floor is wrong. A floor of 0 clears nothing; most of the family is machine-invisible, so the audit still scans by eye.")
