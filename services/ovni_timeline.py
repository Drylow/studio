"""Frame clock and camera math shared by the OVNI wrapper, worker and tests."""
import math

MOTIONS = {'none', 'static', 'zoom_in', 'zoom_out', 'pan_right', 'pan_left',
           'pan_up', 'pan_down', 'zoom_in_tl', 'zoom_in_br'}


def frame_plan(scenes, duration, fps, transition='fade', transition_dur=0.15):
    if not scenes or not math.isfinite(fps) or int(fps) != fps or fps <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError('A positive duration, frame rate and nonempty timeline are required')
    if transition not in ('fade', 'none', 'cut') or not math.isfinite(transition_dur) or transition_dur < 0:
        raise ValueError('Unsupported transition')
    starts = [float(s['start']) for s in scenes]
    if any(not math.isfinite(start) or start < 0 for start in starts):
        raise ValueError('Scene starts must be finite and nonnegative')
    total = round(duration * fps)
    bounds = [round(start * fps) for start in starts] + [total]
    if bounds[0] != 0 or any(b <= a for a, b in zip(bounds, bounds[1:])):
        raise ValueError('Timeline must start at zero and have distinct increasing frame boundaries')
    fade = round(transition_dur * fps) if transition == 'fade' and len(scenes) > 1 else 0
    counts = [b - a for a, b in zip(bounds, bounds[1:])]
    plan = []
    for i, (scene, count) in enumerate(zip(scenes, counts)):
        motion = scene.get('motion', 'none')
        if motion not in MOTIONS:
            raise ValueError(f'Unsupported camera movement: {motion}')
        plan.append({**scene, 'start_frame': bounds[i], 'frames': count,
                     'motion_frames': count + (fade if i < len(scenes) - 1 else 0),
                     'fade_frames': min(fade, count - 1) if i else 0, 'motion': motion})
    return plan


def camera(kind, frame, count, strength, width, height):
    if kind not in MOTIONS:
        raise ValueError(f'Unsupported camera movement: {kind}')
    if not math.isfinite(strength):
        raise ValueError('Camera strength must be finite')
    if kind in ('none', 'static'):
        return 1.0, 0.0, 0.0
    p = max(0, min(1, frame / max(1, count - 1)))
    s = max(0.02, min(0.35, float(strength)))
    zoom = 1 + s * (1 - p) if kind == 'zoom_out' else 1 + s * p
    if kind.startswith('pan_'):
        zoom = 1 + s
    mx, my = width - width / zoom, height - height / zoom
    cx, cy = width / 2, height / 2
    if kind == 'pan_right':
        cx = width / (2 * zoom) + mx * p
    elif kind == 'pan_left':
        cx = width / (2 * zoom) + mx * (1 - p)
    elif kind == 'pan_down':
        cy = height / (2 * zoom) + my * p
    elif kind == 'pan_up':
        cy = height / (2 * zoom) + my * (1 - p)
    elif kind in ('zoom_in_tl', 'zoom_in_br'):
        offset = 0.5 + (-0.17 if kind == 'zoom_in_tl' else 0.17) * p
        cx, cy = width / (2 * zoom) + mx * offset, height / (2 * zoom) + my * offset
    return zoom, width / 2 - cx * zoom, height / 2 - cy * zoom


def fade_weight(local_frame, fade_frames):
    return min(1, local_frame / fade_frames) if fade_frames > 0 else 1.0
