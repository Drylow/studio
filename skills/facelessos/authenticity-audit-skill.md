---
name: authenticity-audit
description: YouTube policy safety for faceless channels — the channel-level layer. Per-script authenticity is enforced by Group E of greenlight-audit-skill.md on every script automatically; open THIS file when the question is bigger than one script: auditing an existing channel or backlog, reading a warning or denial from YouTube, planning publishing cadence across channels, appealing a monetization rejection, or deciding how far to push AI video tools safely.
---

# Authenticity Audit — Channel-Level

> **PURPOSE:** Catch YouTube policy violations BEFORE the platform does. This is NOT about writing quality (the anti-slop patterns in `faceless-scripts-os-master.md` and `humanizer-skill.md` cover that). This is about whether YouTube's automated systems will read your video, or your whole channel, as inauthentic or reused content.

> **HOW THIS SPLITS IN v5:** every script that goes through the workflow already gets the per-script authenticity check as **Group E of `greenlight-audit-skill.md`** — the 7 uniqueness signals, the 4 red flags, the reference-clone check, and the AI-video checks run on every script, every time, and land on the verdict block's E line. You do not run those twice. This file is the layer ABOVE that: the channel, the backlog, the publishing pattern, and what to do when YouTube pushes back.

---

## Why This Exists

YouTube's policies on "inauthentic content" target mass-produced, template-based videos with no creative input. Channels built on pure automation are getting:

- **Demonetized** (ads removed from videos)
- **Monetization applications denied** for "reused content"
- **Channels terminated** under the "inauthentic content" policy
- **AdSense applications rejected** even on first attempt

This hits faceless channels harder than any other format. If your scripts are indistinguishable from thousands of other AI-generated videos, YouTube will catch it — and it judges the channel, not just the video.

## The Two Threats

### Threat 1: "Inauthentic Content" (Channel-Level)

Content that is mass-produced with minimal creative input, often using templates or automation to generate large volumes of similar videos.

**What triggers it:**
- Multiple channels producing near-identical content
- Template-based scripts with only topic names swapped
- No unique perspective, commentary, or analysis
- AI-generated narration with no human review or editing
- Bulk publishing (5+ videos/day across multiple channels)

### Threat 2: "Reused Content" (Monetization-Level)

Your video doesn't add enough original value on top of what already exists. This blocks AdSense approval and can remove monetization from a running channel.

**What triggers it:**
- Scripts that closely mirror existing videos on the same topic
- No original research, analysis, or unique angle
- Generic narration that could apply to any video on the topic
- Visuals identical to other channels (common with AI video tools)
- No editorial voice or perspective in the narration

**The per-script defense against both is Group E** — run it via the greenlight audit on every script. Everything below is what Group E cannot see from inside one script.

---

## Channel-Level Audit

Run this when: you're taking over or reviving a channel, applying for monetization, publishing across multiple channels, or you've seen any watch signal from the table below. Group E clears scripts one at a time; these patterns only show up when you look across uploads.

### Cross-Upload Checks

- [ ] **Structure variety across the last 10 uploads.** Pull the openings and section skeletons of your last 10 videos. If 3+ share the same skeleton (same hook shape, same section order, same closer move), you have a template pattern that no single script would flag. Fix with `variety-rotation-skill.md` before the next upload.
- [ ] **No near-duplicate pairs in the backlog.** No two published videos where one is the other with the nouns swapped. If found: the weaker one is a candidate for removal before a monetization review, not after.
- [ ] **Publishing cadence under the bulk threshold.** Not 5+ similar videos/day across your channels. Volume itself is a signal YouTube reads at the account level.
- [ ] **Cross-channel separation.** If you run multiple channels: no script, or near-identical version, published on more than one. Different channels need different angles, not different thumbnails.
- [ ] **Voice consistency is YOURS, not a template's.** A consistent editorial voice across uploads is a positive signal. Ten videos that all sound like the same stock AI narrator with no opinions is the negative version of the same thing. `voice-anchoring-skill.md` is the fix.

### Backlog Audit (before a monetization application or appeal)

1. List every published video. Sort oldest first.
2. Run the Group E checklist (`greenlight-audit-skill.md`) against the 5 weakest — the ones closest to their reference or to competitors' videos. Score them honestly: E1 signals out of 7, red flags out of 4.
3. Any video scoring under 5/7 with a red flag: remove or rework it BEFORE applying. A denied application creates a record; a cleaned backlog doesn't.
4. Keep the scores. They're your evidence pack if you need to appeal (below).

---

## Mitigation Strategies

### For AI Video Tool Users (VidRush and similar)

1. **Always use custom scripts** — built-in script generators produce generic content. FacelessOS scripts are significantly more unique.
2. **Use human-narrated reference videos** — this teaches the tool a human style instead of an AI style. AI mimicking AI produces the most flaggable content.
3. **Edit the timeline** — even small edits (swapping a clip, adjusting a transition) signal human involvement.
4. **Custom voiceover** — recording your own VO (or using a distinct ElevenLabs voice) differentiates your content from other channels on the same tool.
5. **Avoid trending-only content** — pure trend-chasing produces maximum overlap with other channels. Mix trending with evergreen.

### For All Faceless Channels

1. **Add editorial commentary** — don't just report facts. React to them. "That's insane when you think about it" is human. A dry recitation of events is AI.
2. **Include original analysis** — "Here's what nobody is connecting: X happened because of Y, not because of Z" shows unique thinking.
3. **Vary your structure** — use `variety-rotation-skill.md` so your scripts don't follow the same pattern every time.
4. **Research beyond page 1** — if all your facts come from the first Google result, your script sounds like everyone else's. The research-and-ideation PROOF BANK exists for this.
5. **Review and edit** — a script you personally edited for 15-30 minutes is dramatically more unique than raw AI output, and it flips Group E's human-review signal from claimed to true.

---

## Channel Health Indicators

Monitor these. If you see multiple, act before YouTube does.

| Signal | Risk Level | Action |
|--------|-----------|--------|
| Monetization application denied for "reused content" | 🔴 HIGH | Run the backlog audit above, increase uniqueness, appeal with evidence of original work |
| Comments saying "this sounds AI" or "heard this before" | 🟡 MEDIUM | Review recent scripts for template patterns, add more editorial voice |
| Multiple videos getting the same view count (suspiciously uniform) | 🟡 MEDIUM | YouTube may be suppressing distribution — vary your content more |
| "Inauthentic content" warning in YouTube Studio | 🔴 CRITICAL | Stop publishing immediately. Audit the entire channel. Remove flagged videos. |
| Sudden drop in impressions across all videos | 🟡 MEDIUM | Could be algorithmic suppression — check for policy notifications before assuming the algorithm moved |

## If You're Denied or Warned: the Appeal Path

1. **Stop publishing** until you understand which threat fired (inauthentic = channel pattern; reused = per-video value).
2. **Run the backlog audit.** Remove or rework the videos that fail Group E scoring. Do this before appealing, not after a second denial.
3. **Build the evidence pack:** your research notes, PROOF BANK pulls, source lists, and edit history are proof of original creative input — the exact thing the policy tests for. The greenlight verdict blocks you kept ARE this evidence.
4. **Appeal with specifics:** name the original research, the unique angle, and the editing you personally did. "I write custom scripts" is a claim; "video X cites these 3 sources not found in any competing video, and here are my drafts" is evidence.
5. **Change the pattern that fired** before resuming: cadence, structure variety, or cross-channel duplication.

---

## The Authenticity Spectrum

```
MOST FLAGGABLE ←————————————————————→ MOST SAFE

AI script +          FacelessOS +      FacelessOS +         FacelessOS +
AI video +           AI video +        AI video +           custom VO +
no edits +           reference video + edited timeline +    edited timeline +
bulk publish         custom script     custom elements      original research +
                                                            editorial voice
```

**Your goal:** be as far right on this spectrum as possible. Every step right reduces your risk significantly.

## Output Format

For a **per-script** audit, use the greenlight verdict block (`greenlight-audit-skill.md`) — the E line is the per-script authenticity result. For a **channel-level** audit, output:

```
🛡️ **Channel Authenticity Audit**

**Cross-upload checks:** [X/5 passing]
- ✅/❌ Structure variety (last 10): [status]
- ✅/❌ No near-duplicate pairs: [status]
- ✅/❌ Cadence under bulk threshold: [status]
- ✅/❌ Cross-channel separation: [status]
- ✅/❌ Editorial voice (not template voice): [status]

**Weakest-5 backlog scores:** [video → E1 score/7, red flags/4]

**Watch signals present:** [none / list]

**Risk Level:** [LOW / MEDIUM / HIGH / CRITICAL]
**Action order:** [numbered, most urgent first]
```

---

**FacelessOS v5** — Scripts that YouTube can't flag. Channels it can't either.
