"""Bounded playback diagnostics without stream addresses or native error text."""
import json
import os
from pathlib import Path
import re
import tempfile

PATH=Path('/tmp/mk_ekino_player.json')


def error_summary(message):
    if not isinstance(message,str) or not message.strip():return {'native_error_present':False}
    lower=message.lower()
    category='unclassified'
    for name,patterns in (
        ('http_denied',('403','401','forbidden','unauthorized')),
        ('not_found',('404','not found')),
        ('connection_refused',('connection refused',)),
        ('timeout',('timed out','timeout')),
        ('invalid_media',('invalid data','invalid argument','demux','invalid format')),
        ('unsupported_codec',('codec','decoder','not supported')),
        ('connection_failed',('connection','network','resolve host','dns')),
        ('process_failed',('process','execute','executable','permission denied')),
    ):
        if any(pattern in lower for pattern in patterns):category=name;break
    # Extract only labelled signed numeric codes. Never save arbitrary native text.
    codes=re.findall(r'(?:error|code|status|retval|errno)\s*[:=]?\s*(-?\d{1,12})\b',message,re.I)[:6]
    return {'native_error_present':True,'native_error_category':category,'native_error_codes':codes}


def write(data):
    """Failure to write a diagnostic must never interrupt playback."""
    name=None
    try:
        fd,name=tempfile.mkstemp(prefix='mk-ekino-player-',dir=PATH.parent)
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out,ensure_ascii=False)
        os.replace(name,PATH)
    except (OSError,ValueError,TypeError):pass
    finally:
        if name:
            try:os.unlink(name)
            except OSError:pass
