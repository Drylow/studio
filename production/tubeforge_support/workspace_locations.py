"""Named locations and explicit camera views; execution never chooses another view."""
import copy
from collections import Counter, defaultdict

from fastapi import HTTPException
from app import llm, store
from app.util import parse_json
from . import workspace_api as api

SHOT_TYPES = {'wide', 'medium', 'close_up', 'insert', 'over_shoulder', 'pov', 'top_down', 'low_angle'}
SCENE_KEYS = ('location_view', 'shot_type', 'visual_beat', 'location_contract')
ROLES = {'location-master', 'location-view'}
MODES = {'free', 'consistent'}
CAMERA_POLICIES = {'stable', 'varied'}


def mode(p):
    """The project freezes its style choice. Older projects keep free scenery."""
    return (p.get('settings', {}).get('visuals', {}).get('background_mode')
            or p.get('style_snapshot', {}).get('background_mode') or 'free')


def camera_policy(p):
    return (p.get('settings', {}).get('visuals', {}).get('camera_policy')
            or p.get('style_snapshot', {}).get('camera_policy') or 'varied')


RULES = (
    'Plan spatial continuity AND cinematic variety for the entire narrated story before image prompts. '
    'A location is a concrete space, not the whole building: deck, cabin, engine room and waterline '
    'are distinct spaces. Include all spaces the narrated actions need; no arbitrary location cap. '
    'Describe permanent geometry using world-space anchors (bow/stern, north/south walls), '
    'NOT screen-left/screen-right, which change with camera position. Doors, windows, furnishings '
    'and colours stay fixed. Moving props, damage, weather and time follow the narrative. '
    'A different physical camera position needs an explicitly named, inspected image view. '
    'A crop, zoom, day/night change or shot-size change is NOT a new viewpoint. '
    'Keep backgrounds shallow and simple; camera variety must not add decorative architecture. '
    'Every shot shows a new narrated action, detail, reaction or consequence; camera rotation alone '
    'does not count as new story information. Return exact requested shot IDs in order. '
    'Use only registry spaces/views when supplied. No images are generated here. Return JSON: '
    '{locations:{exact_location_id:{description,layout,anchors:[fixed spatial facts],'
    'views:{exact_view_id:{description,angle}}}},'
    'shots:[{id,location_id,location_view,shot_type,visual_beat}]}. '
    'shot_type is wide|medium|close_up|insert|over_shoulder|pov|top_down|low_angle. '
    'angle states the physical camera position and viewing direction, not lens size.'
)


def rules(p):
    if camera_policy(p) == 'stable':
        return RULES + (' CAMERA POLICY: STABLE. Keep one established camera axis during a continuous '
            'scene. Use framing, foreground action and inserts for variety. No minimum viewpoints '
            'and no forced rotation after repeated shots. Change axis only for an authored transition '
            'or a different established space; never mirror the room.')
    return RULES + (' CAMERA POLICY: VARIED. For a space used in at least six shots, use at least '
        'three distinct physical viewpoints. Never use one viewpoint more than twice consecutively '
        'in the same space. Every view preserves the same world-space geometry and needs an '
        'inspected image before generation; a reverse angle is not a different room.')


def registry(p):
    entries = p.get('workspace_location_registry') or {}
    if not isinstance(entries, dict) or len(entries) > 100:
        raise HTTPException(422, 'The location registry must contain at most 100 named spaces')
    for name, entry in entries.items():
        if (not isinstance(name, str) or not name.strip() or name != name.strip()
                or not isinstance(entry, dict) or not isinstance(entry.get('description'), str)
                or not entry['description'].strip() or not isinstance(entry.get('layout'), str)
                or not entry['layout'].strip() or not isinstance(entry.get('anchors'), list)
                or not entry['anchors'] or any(not isinstance(a, str) or not a.strip() for a in entry['anchors'])
                or not isinstance(entry.get('views'), dict) or not entry['views']
                or not isinstance(entry.get('master'), dict)):
            raise HTTPException(422, 'A location needs a layout, fixed anchors, master image and named views')
        for key, view in entry['views'].items():
            if (not isinstance(key, str) or not key.strip() or key != key.strip()
                    or not isinstance(view, dict) or any(not isinstance(view.get(k), str)
                    or not view[k].strip() for k in ('description', 'angle'))):
                raise HTTPException(422, 'Each location view needs a camera position and description')
    return copy.deepcopy(entries)


def _ref(p, value, location, view=None):
    role = 'location-view' if view is not None else 'location-master'
    if (not isinstance(value, dict) or value.get('owner') not in ('project', 'style')
            or value.get('role') != role or value.get('location_id') != location
            or value.get('review_state') != 'verified' or not isinstance(value.get('sha256'), str)
            or view is not None and value.get('location_view') != view):
        raise HTTPException(422, 'Location images must be explicitly bound, reviewed and fingerprinted')
    base = store.project_dir(p['id']) if value['owner'] == 'project' else store.style_dir(p['style_id'])
    if api._file_digest(base, value.get('path')) != value['sha256']:
        raise HTTPException(409, 'A location image is missing or changed')
    return {k: copy.deepcopy(v) for k, v in value.items() if k != 'url'}


def check_registry(p):
    for name, entry in registry(p).items():
        _ref(p, entry['master'], name)
        for key, view in entry['views'].items():
            if not view.get('reference'):
                raise HTTPException(422, 'Each camera view needs its own inspected image binding; the master view may bind the master file')
            _ref(p, view['reference'], name, key)


def summary(p):
    return {name: {k: copy.deepcopy(e[k]) for k in ('description', 'layout', 'anchors', 'views')}
            for name, e in registry(p).items()}


def audit(shots, policy='varied'):
    views, types = defaultdict(set), defaultdict(set)
    counts = Counter()
    warnings, run, previous = [], 0, None
    for s in shots:
        name, view = s.get('location_id'), s.get('location_view')
        counts[name] += 1
        if view:
            views[name].add(view)
        if s.get('shot_type'):
            types[name].add(s['shot_type'])
        pair = (name, view)
        run = run + 1 if pair == previous else 1
        if policy == 'varied' and view and run == 3:
            warnings.append(f'Shot {s["id"]}: the same location view appears three times in a row')
        previous = pair
    if policy == 'varied':
        for name, count in counts.items():
            if count >= 6 and len(views[name]) < 3:
                warnings.append(f'{name}: {count} shots use fewer than three named viewpoints')
            if count >= 6 and len(types[name]) < 2:
                warnings.append(f'{name}: use different shot sizes as well as viewpoints')
    return {'locations': {name: {'shots': count, 'views': sorted(views[name]),
            'shot_types': sorted(types[name])} for name, count in counts.items()}, 'warnings': warnings}


def validate_plan(data, shots, approved=None, policy='varied'):
    places, rows = data.get('locations'), data.get('shots')
    if (not isinstance(places, dict) or not places or not isinstance(rows, list)
            or [r.get('id') for r in rows if isinstance(r, dict)] != [s['id'] for s in shots]):
        raise ValueError('Invalid complete location/camera plan')
    for name, entry in places.items():
        if (not isinstance(name, str) or not name.strip() or not isinstance(entry, dict)
                or any(not isinstance(entry.get(k), str) or not entry[k].strip() for k in ('description', 'layout'))
                or not isinstance(entry.get('anchors'), list) or not entry['anchors']
                or any(not isinstance(a, str) or not a.strip() for a in entry['anchors'])
                or not isinstance(entry.get('views'), dict) or not entry['views']):
            raise ValueError('A planned location has no concrete geometry')
        for key, view in entry['views'].items():
            if not isinstance(key, str) or not key.strip() or not isinstance(view, dict) or any(
                    not isinstance(view.get(k), str) or not view[k].strip() for k in ('description', 'angle')):
                raise ValueError('A planned view has no physical camera position')
    for row in rows:
        entry = places.get(row.get('location_id'))
        if (not entry or row.get('location_view') not in entry['views'] or row.get('shot_type') not in SHOT_TYPES
                or not isinstance(row.get('visual_beat'), str) or len(row['visual_beat'].strip()) < 12):
            raise ValueError('Every shot needs a location, viewpoint, framing and narrated visual beat')
        if approved and (row['location_id'] not in approved
                or row['location_view'] not in approved[row['location_id']]['views']):
            raise ValueError('The plan cannot invent a replacement for a registered view')
    if approved:
        # Fixed geometry is authored outside this call; the text response cannot alter it.
        places = copy.deepcopy(approved)
    # Different names with the exact same angle do not qualify as different viewpoints.
    normalized = copy.deepcopy(rows)
    for row in normalized:
        angle = places[row['location_id']]['views'][row['location_view']]['angle']
        row['location_view'] = ' '.join(angle.casefold().split())
    for name, entry in places.items():
        angles = [' '.join(v['angle'].casefold().split()) for v in entry['views'].values()]
        if len(angles) != len(set(angles)):
            raise ValueError('Different view names cannot disguise the same camera position')
    if audit(normalized, policy)['warnings']:
        raise ValueError('Camera plan violates this preset\'s varied-view policy')
    return {'locations': places, 'shots': copy.deepcopy(rows)}


async def plan(p, shots, model):
    approved = summary(p)
    raw = await llm.chat([{'role': 'system', 'content': rules(p)}, {'role': 'user', 'content':
        __import__('json').dumps({'story': p['script'], 'location_registry': approved,
            'shots': [{'id': s['id'], 'narration': s['text']} for s in shots]}, ensure_ascii=False)}],
        model=model, effort='low', attempts=1, hedge=False, label='Locations and camera plan')
    return validate_plan(parse_json(raw), shots, approved, camera_policy(p))


def contract(plan, scene):
    entry = plan['locations'][scene['location_id']]
    view = entry['views'][scene['location_view']]
    return ('LOCATION AND CAMERA CONTRACT:\nSpace: ' + entry['description'] + '\nFixed layout: '
            + entry['layout'] + '\nPermanent world-space anchors: ' + '; '.join(entry['anchors'])
            + '\nCamera position and direction: ' + view['angle'] + '\nVisible view: ' + view['description']
            + '\nFraming: ' + scene['shot_type'] + '\nNew narrated information: ' + scene['visual_beat']
            + '\nPreserve this place\'s topology, object colours and permanent landmarks. Match the '
              'approved view\'s camera axis and left/right orientation; framing may crop or widen '
              'without rotating or mirroring the room. Do not invent windows, doors or furniture. '
              'Moving objects, damage and light change only when this scene explicitly calls for it.')


def selected(p, scene):
    if mode(p) != 'consistent':
        return []
    entries = registry(p)
    if not entries:
        return []
    entry = entries.get(scene.get('location_id'))
    view = (entry or {}).get('views', {}).get(scene.get('location_view'))
    if not entry or not view:
        raise HTTPException(422, 'Choose an explicit registered location and view')
    refs = [_ref(p, entry['master'], scene['location_id'])]
    if not view.get('reference'):
        raise HTTPException(422, 'The selected camera view has no inspected image; generate and review it before shots')
    ref = _ref(p, view['reference'], scene['location_id'], scene['location_view'])
    if (ref['owner'], ref['path']) != (refs[0]['owner'], refs[0]['path']):
        refs.append(ref)
    return refs


def binding(p, scene):
    if mode(p) != 'consistent' or not registry(p):
        return ''
    lines = []
    for index, ref in enumerate(scene.get('references') or [], 1):
        if ref.get('role') in ROLES:
            purpose = 'permanent geometry master' if ref['role'] == 'location-master' else 'approved requested camera view'
            lines.append(f'Image {index}: {scene["location_id"]}; {purpose}.')
    return ('LOCATION IMAGE BINDINGS (exact attachment order):\n' + '\n'.join(lines)
            + '\nThese images fix the same physical space AND the approved camera orientation, '
              'not the actor pose. Crop or widen on this axis; never mirror or invent the reverse side. '
              'Use the saved camera contract. Never import people from a location image.')


def author(p, scene, base_refs):
    if mode(p) != 'consistent':
        return [copy.deepcopy(r) for r in base_refs if r.get('role') not in ROLES | {'location'}]
    chosen = selected(p, scene)
    if not chosen:
        return copy.deepcopy(base_refs)
    return chosen + [copy.deepcopy(r) for r in base_refs if r.get('role') not in ROLES | {'location'}]


def validate(p, scene):
    if mode(p) != 'consistent':
        return
    if not registry(p):
        raise HTTPException(422, 'Consistent backgrounds require inspected location masters before image generation')
    if scene.get('shot_type') not in SHOT_TYPES or not isinstance(scene.get('visual_beat'), str):
        raise HTTPException(422, 'Save the shot framing and its new narrated action')
    required = selected(p, scene)
    actual = [r for r in scene.get('references') or [] if r.get('role') in ROLES]
    if actual != required:
        raise HTTPException(422, 'The exact ordered location master and selected view must be saved')
    expected = contract({'locations': summary(p)}, scene)
    if expected != scene.get('location_contract') or expected not in (scene.get('prompt') or ''):
        raise HTTPException(422, 'The saved prompt must match the registered layout and camera view')
    if binding(p, scene) not in (scene.get('prompt') or ''):
        raise HTTPException(422, 'The saved prompt must bind location images to their exact indices')
