"""Renderer choice for Codex-authored historical episodes, never frontend routing."""
from services import render, render_ovni

CHANNELS = {'edo-daily', 'aztec-daily', 'babylon-daily',
            'imperial-china-daily', 'ottoman-daily'}


def render_video(episode, *args, **kwargs):
    backend = episode.get('render_backend', 'ovni' if episode.get('channel') in CHANNELS else 'studio')
    if backend == 'ovni':
        if episode.get('channel') not in CHANNELS:
            raise ValueError('OVNI production routing is limited to the five historical channels')
        return render_ovni.render_video(*args, **kwargs)
    if backend == 'studio':
        return {**render.render_video(*args, **kwargs), 'backend': 'studio'}
    raise ValueError(f'Unknown historical renderer: {backend}')
