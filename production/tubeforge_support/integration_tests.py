"""TubeForge-side integration contracts, deployed into its isolated test suite."""
import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import pipeline, studio_bridge, tts
from app.steps import render


def test_algrow_routing(tmp_path):
    with patch.object(studio_bridge, 'voice', new_callable=AsyncMock, return_value={'provider': 'algrow'}) as voice:
        result = asyncio.run(tts.synthesize('Authored text', {'provider': 'algrow'}, tmp_path))
    assert result['provider'] == 'algrow'
    voice.assert_awaited_once()


@pytest.mark.parametrize('function', [pipeline.do_script, pipeline.do_voiceover, pipeline.do_detect_characters,
                                      pipeline.do_prompts, pipeline.do_images])
def test_directed_project_not_reauthored(function):
    with pytest.raises(RuntimeError, match='Codex'):
        asyncio.run(function({'codex_directed': True}))


def test_missing_studio_is_explicit(tmp_path):
    with patch.object(studio_bridge.config, 'get', return_value=str(tmp_path)):
        with pytest.raises(RuntimeError, match='Python missing'):
            asyncio.run(studio_bridge.execute({}, tmp_path))


def project(tmp_path, captions=False, backend='ovni'):
    (tmp_path / 'scene.png').touch()
    return {'id': 'fixture', 'title': 'Test', 'voiceover': {'file': 'voice.mp3', 'duration': 10},
            'settings': {'visuals': {'aspect': '16:9', 'captions': captions, 'render_backend': backend}},
            'scenes': [{'id': 1, 'image': 'scene.png', 'start': 0, 'end': 10, 'motion': 'zoom_in'}]}


def test_gpu_does_not_drop_captions(tmp_path):
    with patch.object(render.store, 'project_dir', return_value=tmp_path), \
            patch.object(render.store, 'load_words', return_value=[]), \
            patch.object(studio_bridge, 'render', new_callable=AsyncMock) as gpu:
        with pytest.raises(RuntimeError, match='captions'):
            asyncio.run(render.render(project(tmp_path, captions=True)))
        gpu.assert_not_awaited()


def test_render_uses_measured_frame_clock(tmp_path):
    render._render_sem = None
    with patch.object(render.store, 'project_dir', return_value=tmp_path), \
            patch.object(render.store, 'load_words', return_value=[]), \
            patch.object(studio_bridge, 'render', new_callable=AsyncMock, return_value={'backend': 'ovni'}) as gpu:
        result = asyncio.run(render.render(project(tmp_path)))
        args = gpu.call_args.args
        assert args[2:6] == (240, 1920, 1080, 24)
        assert args[1][0]['f0'] == 0
        assert args[1][0]['frames'] == 240
        assert result['backend'] == 'ovni'


def test_bad_frame_count_is_not_success(tmp_path):
    p = project(tmp_path)
    p['settings']['visuals']['motion_strength'] = 1
    with patch.object(studio_bridge.store, 'project_dir', return_value=tmp_path), \
            patch.object(studio_bridge, 'execute', new_callable=AsyncMock, return_value={'video_frames': 239}):
        with pytest.raises(RuntimeError, match='frame count'):
            asyncio.run(studio_bridge.render(p, [], 240, 1920, 1080, 24, tmp_path))


def test_csv_algrow_override_is_preserved():
    rows = pipeline.parse_csv(b'title,provider,voice_id\nOne,algrow,existing\nTwo,algrow,existing\n')
    with patch.object(pipeline.store, 'list_styles', return_value=[{'id': 'fixture', 'name': 'Fixture'}]), \
            patch.object(pipeline.store, 'create_project', side_effect=lambda *a, **kw: {'id': a[0], 'settings': kw['overrides']}), \
            patch.object(pipeline.store, 'save_project'):
        projects = pipeline.create_from_rows(rows, 'review', 'fixture')
    assert len(projects) == 2
    assert all(p['settings']['voice.provider'] == 'algrow' for p in projects)


def test_failure_never_falls_back_to_native(tmp_path):
    render._render_sem = None
    with patch.object(render.store, 'project_dir', return_value=tmp_path), \
            patch.object(render.store, 'load_words', return_value=[]), \
            patch.object(studio_bridge, 'render', new_callable=AsyncMock, side_effect=RuntimeError('GPU failed')):
        with pytest.raises(RuntimeError, match='GPU failed'):
            asyncio.run(render.render(project(tmp_path)))
