"""Exercise the real project queue on identical reviewed media, without generation."""
import asyncio
import json
from pathlib import Path
import time

from . import config, pipeline, store
from .import_review import import_review


async def main():
    directory = Path(config.get('STUDIO_ROOT')) / 'work/historical-01-2026-10-08/edo-daily/review-excerpt'
    projects = []
    for backend in ('native', 'ovni'):
        p = import_review(directory)
        p['title'] = 'TEST technique rendu ' + backend
        p['archived'] = True
        p['settings']['visuals']['render_backend'] = backend
        store.save_project(p)
        projects.append(p)
    batch = pipeline.save_batch([p['id'] for p in projects], 'review', 'Test rendu natif / OVNI')
    started = time.perf_counter()
    for p in projects:
        pipeline.start(p['id'], pipeline.do_render)
    while pipeline.running_ids():
        await asyncio.sleep(1)
    results = []
    for p in projects:
        if p['error'] or not p.get('render'):
            raise RuntimeError(p['error'] or 'Missing render')
        step = p['steps']['render']
        results.append({'id': p['id'], 'backend': p['settings']['visuals']['render_backend'],
                        'file': str((store.project_dir(p['id']) / p['render']['file']).resolve()),
                        'step_seconds_with_queue': step['took'], 'render': p['render']})
    receipt = {'batch': batch['id'], 'total_seconds': time.perf_counter() - started,
               'duration': projects[0]['voiceover']['duration'], 'shots': len(projects[0]['scenes']),
               'results': results, 'note': 'Different camera curves and encoder settings, not equal-quality codec benchmark.'}
    (config.DATA / 'benchmark.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
