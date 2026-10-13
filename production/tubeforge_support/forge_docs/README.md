# TubeForge API and CLI

Use **https://tools.kanye.studio/api/forge/v1**. The existing VPS generates the
voice, prepares timestamped shots, generates images and renders the final MP4.
The client runs only HTTPS requests. It needs Python 3.10+ and no packages.

Give the colleague `forge.py`, `LLM.txt`, this README and their **own** portal
member access key privately. Never give the owner's session or worker trust token.
The live [LLM guide](https://tools.kanye.studio/api/forge/v1/LLM.txt),
[endpoint inventory](https://tools.kanye.studio/api/forge/v1/endpoints) and
[OpenAPI schemas](https://tools.kanye.studio/api/forge/v1/openapi.json) require login.
`LLM.txt` contains the production order, review rules, retry behavior, maintenance
paths and endpoint descriptions. Its served copy appends every installed route.

## First production

```bash
python forge.py login
python forge.py presets
python forge.py create --channel CHANNEL_ID --title "Your title" --script script.txt --key unique-episode-01
python forge.py action VIDEO_ID voice
python forge.py status VIDEO_ID
python forge.py transcript VIDEO_ID
python forge.py action VIDEO_ID prepare
python forge.py status VIDEO_ID
python forge.py project VIDEO_ID
python forge.py action VIDEO_ID preview
# Inspect the three resulting images and submit their reviews before continuing.
python forge.py action VIDEO_ID images
# Inspect all shots, verify audio/timings, then submit reviews.
python forge.py action VIDEO_ID render
python forge.py outputs VIDEO_ID
python forge.py download VIDEO_ID --out final.mp4
```

Poll every five seconds until the selected step completes. A 202 response only
accepts a job. The CLI never automatically starts another stage or posts reviews.
Default login reads the key without echoing; optional `FORGE_ACCESS_KEY` allows
noninteractive login. Sessions are saved to `~/.tubeforge-session.json` with
mode 0600 on Unix. `FORGE_SESSION_FILE` changes that private path;
`FORGE_SESSION_TOKEN` uses an already issued portal session. Windows users must
keep that file in their own private user directory. No secrets belong in Git.

The session Bearer token comes from the `kt_session` cookie returned by
`POST /api/auth` with `{"accessKey":"YOUR_MEMBER_ACCESS_KEY"}`. A key beginning
with `kt_` is a login credential, **not** a Bearer session. On 401 log in again.

### Raw HTTPS example

```bash
curl -H "Authorization: Bearer $FORGE_SESSION_TOKEN" \
  https://tools.kanye.studio/api/forge/v1/presets
curl -X POST -H "Authorization: Bearer $FORGE_SESSION_TOKEN" \
  -H "Content-Type: application/json" --data-binary @create.json \
  https://tools.kanye.studio/api/forge/v1/videos
curl -X POST -H "Authorization: Bearer $FORGE_SESSION_TOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  https://tools.kanye.studio/api/forge/v1/videos/VIDEO_ID/actions/voice
```

Create JSON: `channel_id`, `title`, `script` (optional), `brief` (optional),
`minutes` (default 15; ignored for supplied narration duration) and required
`idempotency_key`. Reuse the same key only for the exact same creation payload.
Channel choice freezes its style, provider, cast and voice settings. Style changes
later do not silently change an existing production. The optional production queue
orchestrates ready stages and parks for inspections: `POST /queue` with
`{"project_ids":["VIDEO_ID"],"automatic_plans":true}`; `GET /queue`;
`POST /queue/JOB_ID/resume` or `/cancel`. Jobs persist on VPS, share resource limits
and never fabricate inspections or replay uncertain paid requests after restart.
The colleague's AI still inspects assets and authors missing references.

## Native authoring contracts

Native workspace prefix: `https://tools.kanye.studio/api/2d/api/workspace`.
Use `forge.py request METHOD COMPLETE_PUBLIC_PATH --json payload.json` for any
JSON endpoint. Endpoint inventory gives every complete public path, including
management and original vendor routes. Legacy auto-generation is not the supported
authored-video workflow. Extended native calls may return model IDs as private
runtime configuration; read them from the snapshot, never hardcode alternatives.

| Operation after the native prefix | Request |
|---|---|
| `GET /channels`, `GET /styles` | Shared library; `GET /management` includes detailed shared style/cast settings. |
| `PUT /projects/ID/script` | `{"text":"Exact narration"}`; invalidates stale voice/render reviews. |
| `PUT /projects/ID/title` | `{"title":"Updated title"}`. |
| `PUT /projects/ID/voice` | `provider` (`algrow` or `ai33`), `voice_id`, `voice_name`, `speed` (0.7–1.2). |
| `POST /projects/ID/voice/channel-default` | Same voice body; also saves shared channel default. |
| `PUT /projects/ID/scenes` | `{"scenes":[...]}`; complete ordered shot list, not a partial update. Preserve existing image/reference/receipt fields. |
| `PUT /projects/ID/locations` | `{"previous_hash":"Current location_registry_hash","locations":{...}}`; complete registry. |
| `POST /projects/ID/references` | Multipart `file`, `role` (location/character/pose/style), `label`. Max 10 MB. Returned uploaded reference is initially unreviewed. |
| `POST /projects/ID/scenes/SHOT/generate` | `confirm_prompt` equals saved prompt; `image_model` and `image_provider` from saved model_snapshot. Existing image is retained on failure. |
| `POST /projects/ID/review` | `scope` (scene/script/voiceover/render), optional `scene_id`, `state` (verified/correct/unreviewed), `reviewer`, `notes`, `source` (explicit_human_review/delegated_ai_inspection). |
| `POST /projects/ID/script/apply-draft` | `draft_id`, current `script_hash`; protects existing media/script. |
| `GET /performance`, `PUT /performance` | Shared concurrency; changes require idle jobs. Preserve owner limits. |

Shot fields: positive unique integer `id`, exact narration excerpt `text`, authored
`prompt`, `location_id`, named `characters` array, ordered `references` array and
actual audio `start`/`end` seconds. Each reference has `owner` (project/style/studio),
relative `path`, and original `sha256`; studio references require a digest.
Preserve `character_variants`, view metadata and selected images when editing.
Image calls enforce the drawing guide, actual reference files, hashes, style and
frame ratio. Do not remove those guards to make a rejected request succeed.

Consistent registry shape: each location includes `description`, `layout`,
`anchors`, `master`, and `views`. Each view includes `description`, `angle`
(physical camera position/direction), and optionally `reference`. Masters use
owner/path/sha256, `role:location-master`, `location_id` and
`review_state:verified`; view references use `role:location-view` plus
`location_view`. Bind those fields only after actual inspection. Check the preset's actual shape
and `workspace_locations.py` for allowed optional fields. Free backgrounds do
not impose this registry. Neither mode disables character identity references.

```bash
python forge.py upload /api/2d/api/workspace/projects/ID/references master.png --field role=location --field label=Airport-terminal
python forge.py request PUT /api/2d/api/workspace/projects/ID/scenes --json scenes.json
python forge.py request POST /api/forge/v1/videos/ID/review --json review.json
python forge.py request GET /api/forge/v1/LLM.txt
```

Example review JSON after **actual** image inspection:

```json
{"scope":"scene","scene_id":1,"state":"verified","reviewer":"Colleague AI","source":"delegated_ai_inspection","notes":"Inspected the generated image: one hero, correct bandage and white hands; landscape frame and terminal layout match the references."}
```

Render validates current file hashes, reference evidence, every scene review,
audio review and timings. A saved MP4 can still await final QA. Outputs reports
that distinction. Download URLs accept the same authorization header and Range
requests. Stop cancels a main stage or drains the current image batch; submitted
provider requests can finish and incur charges. Reconnect and inspect progress
before retrying a timed-out action. Creation is keyed/idempotent; paid stage
requests are explicit, not an exactly-once durable queue.

## VPS and source maintenance

The colleague already has separately supplied VPS SSH details; API production
does not need SSH or Docker permissions.

| Host | Role | Maintained runtime |
|---|---|---|
| `185.249.225.176` | Portal/auth/gateway | `/opt/elevenlabs-studio`, container `elevenlabs-studio` |
| `13.140.129.97` | TubeForge generation/render | Container `drylow-tubeforge`, app `/opt/studio/work/TubeForge` |

Worker data persists on host `/opt/tubeforge/data`; repository is
`/opt/tubeforge/repository`; immutable builds are under `/opt/tubeforge/releases`;
backups under `/opt/tubeforge/backups`; private config under `/opt/tubeforge/config`.
Sources: `production/tubeforge_support`, installer `production/tubeforge_workspace.py`,
base `production/tubeforge_base`, gateway `production/tubeforge_portal/2d.js`.
GitHub repository: https://github.com/Drylow/studio. Read CLAUDE.md/AGENTS.md first.

Deploy using `bash /opt/tubeforge/repository/production/tubeforge_host/update.sh`
only after checking active jobs. Do not restart during paid generations. Never
reseed existing styles/channels or overwrite the data volume. Portal changes
must preserve its existing auth and other tools. Worker CPU rendering uses the
existing shared limits; no desktop/cloud rendering fallback. SSH private keys,
provider credentials and connection tokens are deliberately outside this kit.
