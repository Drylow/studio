"""Validate local SRT and place editable native titles only over dialogue scenes."""
import html
import re
import textwrap
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import xml.etree.ElementTree as ET


TIMESTAMP = re.compile(r'^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})$')


def timestamp_ms(value):
    match = TIMESTAMP.fullmatch(value.strip())
    if not match:
        raise ValueError('SRT timestamps must use HH:MM:SS,mmm with valid minute/second bounds.')
    hours, minutes, seconds, millis = map(int, match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def parse_srt(path, source_duration):
    path = Path(path).resolve(strict=True)
    if path.suffix.lower() != '.srt' or not path.is_file():
        raise ValueError('Supply an existing local .srt file, explicitly timed against the edited source.')
    cues, previous_end, identities = [], 0, set()
    text = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').strip()
    for block in re.split(r'\n\s*\n', text) if text else []:
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit() or int(lines[0]) in identities:
            raise ValueError('Each SRT cue requires a unique numeric identifier, timing and text.')
        identities.add(int(lines[0]))
        timing = lines[1].split(' --> ')
        if len(timing) != 2:
            raise ValueError('SRT cue timing requires exactly one arrow and no VTT settings.')
        start, end = map(timestamp_ms, timing)
        if start < previous_end or end <= start or end > source_duration * 1000 + 1:
            raise ValueError('SRT cues must be ordered, nonoverlapping, positive and inside the edited source.')
        # Native titles use plain text. Keep punctuation/entities, remove only
        # conventional subtitle emphasis tags rather than interpreting HTML.
        caption = html.unescape(re.sub(r'</?(?:i|b|u)>', '', ' '.join(lines[2:]), flags=re.I))
        caption = ' '.join(caption.split())
        if not caption or '<' in caption or '>' in caption or any(ord(c) < 32 for c in caption):
            raise ValueError('Subtitle cues require nonempty plain text or basic i/b/u emphasis.')
        wrapped = textwrap.wrap(caption, width=64, break_long_words=False, break_on_hyphens=False)
        if len(wrapped) > 2 or any(len(line) > 64 for line in wrapped):
            raise ValueError('Split long captions into at most two short readable lines before exporting.')
        cues.append({'index': int(lines[0]), 'start_ms': start, 'end_ms': end, 'text': '\n'.join(wrapped)})
        previous_end = end
    if not cues:
        raise ValueError('The supplied SRT has no cues.')
    return cues


def frame_at(seconds, fps):
    return int((Decimal(str(seconds)) * fps).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def map_dialogue_cues(cues, segments, fps, total):
    """Split captions at pauses, leaving guide, replay and outro completely clear."""
    mapped = []
    frame_cues = []
    for cue in cues:
        start = frame_at(Decimal(cue['start_ms']) / 1000, fps)
        end = frame_at(Decimal(cue['end_ms']) / 1000, fps)
        if end <= start:
            raise ValueError('A subtitle cue is shorter than one frame after alignment; correct its timing.')
        frame_cues.append((cue, start, end))
    for segment_index, segment in enumerate(segments):
        if segment['kind'] != 'source':
            continue
        source_start = frame_at(segment['source_in'], fps)
        source_end = frame_at(segment['source_out'], fps)
        final_start, final_end = segment['start_frame'], segment['end_frame']
        if not 0 <= final_start < final_end <= total or source_end <= source_start:
            raise ValueError('Subtitle mapping needs valid source and final segment bounds.')
        if abs((source_end - source_start) - (final_end - final_start)) > 1:
            raise ValueError('Subtitle mapping cannot compensate for a changed scene playback rate.')
        for cue, cue_start, cue_end in frame_cues:
            start = max(source_start, cue_start)
            end = min(source_end, cue_end)
            if end <= start:
                continue
            mapped_start = min(final_end, final_start + start - source_start)
            mapped_end = min(final_end, final_start + end - source_start)
            if mapped_end <= mapped_start:
                continue
            row = {'start_frame': mapped_start, 'end_frame': mapped_end,
                   'duration_frames': mapped_end - mapped_start, 'text': cue['text'],
                   'source_cue_index': cue['index'], 'source_start_frame': start,
                   'source_end_frame': end, 'segment_index': segment_index}
            if mapped and row['start_frame'] < mapped[-1]['end_frame']:
                raise ValueError('Subtitles overlap after frame alignment; correct the source SRT.')
            mapped.append(row)
    return mapped


def native_title_xml(text, length):
    """Native Kdenlive text and rectangle, both editable in its title editor."""
    lines = text.count('\n') + 1
    height = 58 if lines == 1 else 102
    top = 1020 - height
    root = ET.Element('kdenlivetitle', width='1920', height='1080', out=str(length - 1))
    box = ET.SubElement(root, 'item', {'z-index': '0', 'type': 'QGraphicsRectItem'})
    position = ET.SubElement(box, 'position', x='208', y=str(top))
    ET.SubElement(position, 'transform').text = '1,0,0,0,1,0,0,0,1'
    ET.SubElement(box, 'content', pencolor='0,0,0,0', rect=f'0,0,1576,{height}',
                  penwidth='0', brushcolor='0,0,0,136')
    item = ET.SubElement(root, 'item', {'z-index': '1', 'type': 'QGraphicsTextItem'})
    position = ET.SubElement(item, 'position', x='224', y=str(top + 2))
    ET.SubElement(position, 'transform').text = '1,0,0,0,1,0,0,0,1'
    content = ET.SubElement(item, 'content', {'font-color': '255,255,255,255',
        'font-outline-color': '0,0,0,255', 'font-pixel-size': '36', 'font-italic': '0',
        'font-underline': '0', 'font-weight': '50', 'font': 'DejaVu Sans',
        'font-outline': '1.2', 'alignment': '2', 'textwidth': '1544'})
    content.text = text
    ET.SubElement(root, 'startviewport', rect='0,0,1920,1080')
    ET.SubElement(root, 'endviewport', rect='0,0,1920,1080')
    ET.SubElement(root, 'background', color='0,0,0,0')
    return ET.tostring(root, encoding='unicode')


def srt_timestamp(frame, fps):
    millis = frame_at(Decimal(frame) / fps, 1000)
    seconds, millis = divmod(millis, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'


def final_srt(cues, fps):
    return '\n\n'.join(f'{i}\n{srt_timestamp(c["start_frame"], fps)} --> '
                       f'{srt_timestamp(c["end_frame"], fps)}\n{c["text"]}'
                       for i, c in enumerate(cues, 1)) + '\n'
