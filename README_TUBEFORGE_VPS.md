# TubeForge / 2D Studio on tools.kanye.studio

Open **https://tools.kanye.studio/2d**. TubeForge uses the portal’s existing
access-key login, session cookie, member IDs, navigation and light/dark theme.
There is no second login, password database or team-management system. Existing
portal authentication and permissions on other tools are unchanged.

## Colleague AI / command-line production API

The simple authenticated API is **https://tools.kanye.studio/api/forge/v1**.
Read [the API and CLI guide](production/tubeforge_support/forge_docs/README.md)
and [LLM.txt](production/tubeforge_support/forge_docs/LLM.txt). The served guide
adds the complete live endpoint inventory; `/endpoints` and `/openapi.json`
provide the machine-readable inventory and schemas. The dependency-free
`forge.py` client logs in with the colleague's own portal access key.

Creation freezes shared presets and uses a member-scoped idempotency key.
Voice, timestamped planning, preview, remaining images and rendering are
asynchronous actions on VPS2. The persistent production queue shares voice,
planning, image and rendering capacity, reuses saved outputs, and parks for
authoring/reviews without blocking other videos. Two image batches share the
global provider limit. Interrupted dispatches need explicit inspection/resume.
Progress polling is lightweight; no reviews or publication approvals are invented.

## Team workflow

Create members with the existing **Channels & Team** page. Any signed-in member
can use every TubeForge capability, including settings, shared channels/styles,
character references, generation, verification and exports. TubeForge adds no
owner/admin/worker permission gates. **My videos** shows the member’s own videos;
**Team videos** lets any member open and edit all team productions. Existing
videos are mapped to the existing studio owner’s portal identity. A copied video belongs to its creator.

Channels/styles are a shared TubeForge library, not a copy per member. They are
not duplicated into the portal’s separate script/voice channel database. Each
new video freezes its style and cast settings, preserving existing productions.

### References belong to the episode

Keep the shared drawing guide neutral: a character sheet describes rendering and
proportions, never a station, supermarket, boat or other inherited setting. The
shared cast retains identity files; each episode owns its location masters and
explicit camera views. A hospital story needs hospital rooms and exits; a cruise
needs ship spaces. Free backgrounds still preserve cast identity. Consistent
backgrounds preserve a room within its scene, while allowing different places,
camera positions and narrated damage. A pristine master must not reset a broken
walkway, lost prop or injury later in the story.

The storyboard authoring contract takes anatomy and colours from the chosen
style and cast. The warrior-specific tattoo/body contract applies only to that
style, rather than overriding survival stick figures, green infected or mint
aliens. Generation sends the saved prompt and ordered references unchanged;
current image inspection is still required before the queue renders an episode.

## Architecture and sources

- VPS1 `185.249.225.176`: existing Node portal, `/opt/elevenlabs-studio`, container
  `elevenlabs-studio`. Gateway `routes/2d.js`, native page `public/2d.html`, shared
  workspace assets `public/2d-workspace.js` and `.css`. The source is bind-mounted;
  restart only this container after editing. Never replace its existing auth module.
- VPS2 `13.140.129.97`: TubeForge worker, container `drylow-tubeforge`, one web process.
- The browser talks only to authenticated, same-origin `/api/2d/*` endpoints.
  VPS1 supplies the immutable portal member identity and private worker token.
  Browser-supplied identity/auth headers cannot override that identity. VPS2 rejects
  direct unauthenticated calls to its APIs, media and HTML. `/healthz` reveals only health.
- Portal integration sources: `production/tubeforge_portal/{2d.js,2d.html,install.py}`.
  The installer preserves other tools, adds the rail link everywhere and a Hub card,
  and backs up changed files. It writes the bind-mounted server file in place.
- TubeForge base: `production/tubeforge_base`; maintained extensions/UI:
  `production/tubeforge_support`; editable presets: `production/tubeforge_presets`.

Private connection data:

- VPS1 volume `/app/data/tubeforge-worker.json`: worker HTTPS base URL and shared token.
- VPS2 `/opt/tubeforge/config/worker.env`: `TUBEFORGE_PROXY_TOKEN`, loaded by Compose.
- VPS2 `/opt/tubeforge/config/app.env` and `studio.env`: private provider settings.
- Tokens, portal sessions, provider keys and model IDs never belong in Git.

## Production speed

**Settings → Production speed** controls the team-wide limits: 24 CLI Proxy
images, 8 text requests, 6 planning batches, 3 voice requests, 6 projects and 1
native render. Google Flow has a separate limit of up to 3 images. Provider queues
and quotas affect throughput; concurrency is not a fixed completion-time promise.
Change limits when jobs are idle. The three-image preview is separate from the
remaining batch. Every shot keeps its own prompt, ordered references and receipt.
Stopping drains already-started requests; it does not issue duplicate paid retries.

The VPS2 container keeps its 6-CPU/12-GB limit and 4 native rendering workers.
Previous desktop GPU render timings do not benchmark this CPU host.

## Persistent data and updates

`/opt/tubeforge/data` preserves all existing videos, voiceovers, images, references,
styles and channels. `/opt/tubeforge/releases` contains immutable source releases;
`/opt/tubeforge/backups` holds private backups. The PC is an archive, without
bidirectional synchronization. Its desktop shortcut opens the portal.

For a worker update after pushing sources:

```bash
bash /opt/tubeforge/repository/production/tubeforge_host/update.sh
```

The worker update requires its existing private connection file, checks active
jobs, backs up private state and replaces only TubeForge. When changing portal
sources, copy the published release to VPS1, run the portal installer against
`/opt/elevenlabs-studio`, verify no active in-process portal jobs, then restart
`elevenlabs-studio`. Never put the private connection JSON in the release.

After updating, verify owner/member sessions, personal/team video history, shared
styles, uploads, voice/image/video Range streaming, native rendering, dark mode
and mobile layout. Keep other services and volumes unchanged. Roll back with the
saved Compose image/release and the portal installer backup; preserve newer data.
