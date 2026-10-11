"""Merge two edited SRTs on the source clock, before intro and analysis holds.

The second chapter offset is an integer frame count. Fraction arithmetic keeps
that clock exact until SRT timestamps are rounded once to milliseconds. This
does not produce final-export captions or change subtitle wording.
"""
import argparse
from collections import namedtuple
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import tempfile


Cue = namedtuple('Cue', 'start_ms end_ms text')
STAMP = r'([0-9]{2,}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})'
TIMING = re.compile(r'^' + STAMP + r'[ \t]+-->[ \t]+' + STAMP + r'$')


def positive_fps(value):
    """Accept a finite positive frame rate without a floating-point clock."""
    if isinstance(value, bool):
        raise ValueError('fps must be finite and positive.')
    try:
        fps = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError, TypeError) as error:
        raise ValueError('fps must be finite and positive.') from error
    if fps <= 0:
        raise ValueError('fps must be finite and positive.')
    return fps


def validate_cues(cues, label='SRT'):
    if not cues:
        raise ValueError(f'{label} must contain at least one cue.')
    previous_end = 0
    for cue in cues:
        if any(not isinstance(t, int) or isinstance(t, bool)
               for t in (cue.start_ms, cue.end_ms)):
            raise ValueError(f'{label} timestamps must be integer milliseconds.')
        if cue.start_ms < 0 or cue.end_ms <= cue.start_ms:
            raise ValueError(f'{label} cue timestamps must be positive intervals.')
        if cue.start_ms < previous_end:
            raise ValueError(f'{label} cues must be ordered and non-overlapping.')
        if not cue.text or not cue.text.strip():
            raise ValueError(f'{label} cue text cannot be empty.')
        previous_end = cue.end_ms


def parse_srt(text, label='SRT'):
    """Require numbered cues, strict HH:MM:SS,mmm times and nonempty text."""
    text = text.removeprefix('\ufeff').replace('\r\n', '\n')
    if '\r' in text:
        raise ValueError(f'{label} contains unsupported bare carriage returns.')
    blocks = re.split(r'\n(?:[ \t]*\n)+', text.strip('\n'))
    cues = []
    for index, block in enumerate(blocks, 1):
        lines = block.split('\n')
        if (len(lines) < 3 or not re.fullmatch(r'[1-9][0-9]*', lines[0])
                or int(lines[0]) != index):
            raise ValueError(f'{label} needs consecutive cue numbers starting at 1.')
        match = TIMING.fullmatch(lines[1])
        if match is None:
            raise ValueError(f'{label} cue {index} has an invalid SRT timestamp.')
        values = [int(n) for n in match.groups()]
        start, end = [((h * 60 + m) * 60 + s) * 1000 + ms
                      for h, m, s, ms in (values[:4], values[4:])]
        cues.append(Cue(start, end, '\n'.join(lines[2:])))
    validate_cues(cues, label)
    return cues


def round_milliseconds(value):
    """Round nonnegative rational milliseconds, with ties rounded up."""
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def merge_cues(first, second, second_offset_frames, fps=30):
    if (not isinstance(second_offset_frames, int)
            or isinstance(second_offset_frames, bool) or second_offset_frames < 0):
        raise ValueError('second-offset-frames must be a nonnegative integer.')
    fps = positive_fps(fps)
    validate_cues(first, 'First SRT')
    validate_cues(second, 'Second SRT')
    offset_ms = Fraction(second_offset_frames * 1000, 1) / fps
    if first[-1].end_ms > offset_ms:
        raise ValueError('First SRT extends beyond the second chapter offset.')
    shifted = [Cue(round_milliseconds(Fraction(c.start_ms) + offset_ms),
                   round_milliseconds(Fraction(c.end_ms) + offset_ms), c.text)
               for c in second]
    merged = list(first) + shifted
    validate_cues(merged, 'Merged SRT')
    return merged


def format_stamp(ms):
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'


def render_srt(cues):
    validate_cues(cues)
    return '\n\n'.join(
        f'{index}\n{format_stamp(c.start_ms)} --> {format_stamp(c.end_ms)}\n{c.text}'
        for index, c in enumerate(cues, 1)) + '\n'


def atomic_write_new(path, text):
    """Publish a complete same-directory temporary file without replacement."""
    path = Path(path)
    if os.path.lexists(path):
        raise FileExistsError(f'Output already exists: {path}')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix=f'.{path.name}.',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # Unlike replace(), link() refuses a destination created concurrently.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--second-offset-frames', type=int, required=True)
    clock = parser.add_mutually_exclusive_group()
    clock.add_argument('--fps', type=positive_fps)
    clock.add_argument('--fps30', dest='fps', action='store_const', const=Fraction(30))
    parser.set_defaults(fps=Fraction(30))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        first = parse_srt(args.first.read_text(encoding='utf-8'), 'First SRT')
        second = parse_srt(args.second.read_text(encoding='utf-8'), 'Second SRT')
        cues = merge_cues(first, second, args.second_offset_frames, args.fps)
        atomic_write_new(args.out, render_srt(cues))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({'out': str(args.out), 'cues': len(cues),
                      'second_offset_frames': args.second_offset_frames,
                      'fps': str(args.fps)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
