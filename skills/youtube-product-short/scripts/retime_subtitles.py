#!/usr/bin/env python3
"""Retime YouTube rolling or ordinary WebVTT using a frame-quantized edit plan.

Only the Python standard library is required. Produces draft subtitles for review.
"""
import argparse
import html
import json
import math
import re
import textwrap
from pathlib import Path

TIMESTAMP = r'(?:\d{2,}:)?\d{2}:\d{2}\.\d{3}'
INLINE = re.compile(r'<(' + TIMESTAMP + r')>')
RANGE = re.compile(r'^(' + TIMESTAMP + r')\s+-->\s+(' + TIMESTAMP + r')')


def seconds(value):
    parts = list(map(float, value.split(':')))
    return sum(n * (60 ** i) for i, n in enumerate(reversed(parts)))


def clean(value):
    return html.unescape(re.sub(r'<[^>]*>', '', value)).strip()


def read_vtt(path):
    content = Path(path).read_text(encoding='utf-8-sig')
    rolling = bool(INLINE.search(content))
    units = []
    for block in re.split(r'\n\s*\n', content.replace('\r\n', '\n')):
        lines = block.splitlines()
        idx = next((i for i, line in enumerate(lines) if RANGE.match(line)), None)
        if idx is None:
            continue
        match = RANGE.match(lines[idx])
        start, end = map(seconds, match.groups())
        payload = [line.strip() for line in lines[idx + 1:] if line.strip()]
        if not payload or end <= start:
            continue
        if not rolling:
            value = clean(' '.join(payload))
            if value:
                units.append({'start': start, 'end': end, 'text': value})
            continue
        # YouTube's very short stabilization cues repeat the previous line.
        if end - start <= .03:
            continue
        line = payload[-1]
        pieces = re.split(r'(<'+TIMESTAMP+r'>)', line)
        when = start
        cue_units = []
        for piece in pieces:
            marker = INLINE.fullmatch(piece)
            if marker:
                when = seconds(marker.group(1))
            else:
                value = clean(piece)
                if value:
                    cue_units.append({'start': when, 'end': end, 'text': value})
        for i, unit in enumerate(cue_units):
            if i + 1 < len(cue_units):
                unit['end'] = min(end, cue_units[i + 1]['start'])
            if unit['end'] > unit['start']:
                units.append(unit)
    units.sort(key=lambda unit: unit['start'])
    return units, rolling


def stamp(value):
    total = round(value * 1000)
    hours, total = divmod(total, 3600000)
    minutes, total = divmod(total, 60000)
    secs, millis = divmod(total, 1000)
    return f'{hours:02}:{minutes:02}:{secs:02},{millis:03}'


def wrap(value, width=47):
    words = value.split()
    if len(value) <= width:
        return value
    splits = [(' '.join(words[:i]), ' '.join(words[i:])) for i in range(1, len(words))]
    valid = [p for p in splits if max(map(len, p)) <= width]
    if valid:
        return '\n'.join(min(valid, key=lambda pair: abs(len(pair[0])-len(pair[1]))))
    return '\n'.join(textwrap.wrap(value, width=width, break_long_words=False,
                                   break_on_hyphens=False))


def build(vtt, plan):
    fps = float(plan.get('fps', 30))
    default_speed = float(plan.get('speed', 1.15))
    if not math.isfinite(fps) or not 0 < fps <= 240:
        raise ValueError('fps must be finite and between 0 and 240')
    units, rolling = read_vtt(vtt)
    if not units:
        raise ValueError('No usable VTT captions found')
    segments = plan.get('segments', [])
    if not segments:
        raise ValueError('The edit plan needs at least one segment')
    captions, timings, partials = [], [], []
    offset = 0.0
    selected_count = 0
    missing = []
    for index, segment in enumerate(segments):
        start, end = float(segment['start']), float(segment['end'])
        speed = float(segment.get('speed', default_speed))
        if not all(math.isfinite(v) for v in (start, end, speed)):
            raise ValueError('Times and speed must be finite')
        if start < 0 or end <= start or speed <= 0:
            raise ValueError('Require 0 <= start < end and speed > 0')
        frames = int(math.floor((end-start)/speed*fps + .5))
        if frames < 1:
            raise ValueError('A selected segment is shorter than one output frame')
        duration = frames/fps
        selected = []
        for unit in units:
            if unit['start'] < end and unit['end'] > start:
                if unit['start'] < start or unit['end'] > end:
                    partials.append({'segment': index+1, 'text': unit['text'],
                                     'source_start': unit['start'], 'source_end': unit['end']})
                # Rolling captions can hold an old word across silence. Select
                # timed words by onset; retain boundary warnings for review.
                if rolling and unit['start'] < start:
                    continue
                a = max(0, (unit['start']-start)/speed)
                b = min(duration, (unit['end']-start)/speed)
                if b > a:
                    selected.append({'start': offset+a, 'end': offset+b,
                                     'text': unit['text']})
        if not selected:
            missing.append(index+1)
        selected_count += len(selected)
        groups = []
        if rolling:
            group = []
            for unit in selected:
                proposed = ' '.join(x['text'] for x in group+[unit])
                too_long = group and (len(proposed)>82 or unit['end']-group[0]['start']>4.6)
                if too_long:
                    groups.append(group)
                    group = []
                group.append(unit)
                if re.search(r'[.!?]$', unit['text']) or (
                        unit['text'].endswith(',') and unit['end']-group[0]['start']>=2.4):
                    groups.append(group)
                    group = []
            if group:
                groups.append(group)
        else:
            groups = [[unit] for unit in selected]
        for group in groups:
            captions.append({'start': group[0]['start'], 'end': group[-1]['end'],
                             'text': wrap(' '.join(unit['text'] for unit in group)),
                             'segment': index+1})
        timings.append({'segment': index+1, 'source_start': start, 'source_end': end,
                        'speed': speed, 'frames': frames, 'duration': duration,
                        'timeline_start': offset})
        offset += duration
    if not captions:
        raise ValueError('The selected ranges contain no subtitles')
    for i, caption in enumerate(captions):
        if i+1 < len(captions):
            caption['end'] = min(caption['end'], captions[i+1]['start'])
        if caption['end'] <= caption['start']:
            raise ValueError('Overlapping source captions require manual review')
    report = {'fps': fps, 'duration_seconds': offset, 'caption_count': len(captions),
              'source_caption_units_selected': selected_count,
              'input_timing': 'YouTube inline timestamps' if rolling else 'cue-level timestamps',
              'segments': timings, 'partial_caption_units': partials,
              'segments_without_captions': missing,
              'captions_over_two_lines': [i+1 for i, c in enumerate(captions) if len(c['text'].splitlines())>2],
              'draft_requires_semantic_review': True}
    return captions, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vtt', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--report')
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
    captions, report = build(args.vtt, plan)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n\n'.join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}"
                                  for i,c in enumerate(captions))+'\n', encoding='utf-8-sig')
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'output': str(output), 'duration_seconds': report['duration_seconds'],
                      'captions': len(captions), 'review_required': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
