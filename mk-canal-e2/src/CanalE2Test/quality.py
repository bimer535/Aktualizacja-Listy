"""DASH quality menu data. No URLs, DRM material or account identifiers."""
from fractions import Fraction
import json
import re

import player_runtime as runtime
from canal_stream_test_v2 import StreamError


def fps(value):
    try:
        result = float(Fraction(str(value)))
        return round(result, 3) if 0 < result <= 240 else 0
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0


def codec(value):
    value = value.split('.', 1)[0].lower()
    return value if value in ('mp4a', 'ec-3', 'ac-3', 'avc1', 'avc3', 'hvc1', 'hev1', 'av01', 'vp09', 'opus') else 'other'


def variants(root):
    for videos, audios in runtime.track_groups(root):
        result = []
        for video in videos:
            if not 0 < video['height'] <= 4320:
                continue
            for audio in audios:
                lang = audio['lang']
                meta = {'height': video['height'], 'width': min(video['width'], 8192),
                        'video_bitrate': min(video['bandwidth'], 1000000000),
                        'audio_bitrate': min(audio['bandwidth'], 1000000000),
                        'fps': fps(video['frame_rate']), 'video_codec': codec(video['codec']),
                        'audio_codec': codec(audio['codec']),
                        'language': lang if re.fullmatch(r'[a-z]{2,3}(?:-[a-z]{2})?', lang) else 'und'}
                result.append((meta, video, audio))
        if result:
            return sorted(result, key=lambda x: (x[0]['height'], x[0]['video_bitrate'],
                          x[0]['fps'], x[0]['language'] in ('pl', 'pol', 'pl-pl'),
                          x[0]['audio_codec'] == 'mp4a', x[0]['audio_bitrate']), reverse=True)
    raise StreamError('quality_variants_missing')


def label(meta):
    bitrate = meta['video_bitrate'] + meta['audio_bitrate']
    rate = (' %g kl./s' % meta['fps']) if meta['fps'] else ''
    return '[%s] bitrate: %d  %dx%d  %s,%s%s' % (
        meta['language'], bitrate, meta['width'], meta['height'],
        meta['audio_codec'], meta['video_codec'], rate)


def preferred_index(options, preference):
    """Match the next channel by properties, never by stale representation IDs."""
    indices = list(range(len(options)))
    for key in ('language', 'audio_codec', 'video_codec'):
        matches = [i for i in indices if options[i][0][key] == preference.get(key)]
        if matches:
            indices = matches
    height = preference.get('height', 1080)
    below = [i for i in indices if options[i][0]['height'] <= height]
    target = max(options[i][0]['height'] for i in below) if below else min(options[i][0]['height'] for i in indices)
    indices = [i for i in indices if options[i][0]['height'] == target]
    return min(indices, key=lambda i: (abs(options[i][0]['fps'] - preference.get('fps', 50)),
                                      abs(options[i][0]['video_bitrate'] - preference.get('video_bitrate', 1000000000))))


def choose(root, emit, input_stream, preference=None):
    options = variants(root)
    if preference is None:
        emit('quality_choices', quality_choices=[{'label': label(meta), 'preference': meta}
                                                for meta, _, _ in options])
        while True:
            line = input_stream.readline(4097)
            if not line:
                raise StreamError('quality_selection_cancelled')
            if len(line) > 4096:
                continue
            try:
                value = json.loads(line)
            except (ValueError, TypeError):
                continue
            index = value.get('quality_index') if isinstance(value, dict) else None
            if type(index) is int and 0 <= index < len(options):
                break
    else:
        index = preferred_index(options, preference)
    meta, video, audio = options[index]
    emit('quality_chosen', selected_quality=meta)
    return video, audio
