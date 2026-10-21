"""Allowlisted HTTP error metadata; no response strings, tokens or URLs leave here."""
import json
import re

ERROR_FIELDS = {'error', 'errors', 'errorCode', 'error_code', 'code', 'status', 'Status',
                'message', 'description', 'detail', 'error_description'}


def error_shape(raw):
    result = {'response_bytes_read': len(raw)}
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        result['response_format'] = 'non_json'
        return result
    result['response_format'] = 'json'
    names, hints, codes = set(), set(), {}
    def walk(node, depth=0):
        if depth > 3:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in ERROR_FIELDS:
                    continue
                names.add(key)
                if key in ('errorCode', 'error_code', 'code', 'status', 'Status'):
                    if isinstance(value, int) and not isinstance(value, bool):
                        codes[key] = value
                    elif isinstance(value, str) and re.fullmatch(r'-?\d{1,8}', value):
                        codes[key] = int(value)
                if isinstance(value, str) and key in ('message', 'description', 'detail', 'error_description'):
                    text = value[:4000].casefold()
                    for tag, terms in [('user_agent_mentioned', ('user-agent', 'user agent', 'useragent')),
                                       ('token_mentioned', ('token', 'oauth')),
                                       ('device_mentioned', ('device', 'equipment')),
                                       ('expired_mentioned', ('expired', 'expiration')),
                                       ('subscription_mentioned', ('subscription', 'entitlement'))]:
                        if any(term in text for term in terms): hints.add(tag)
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:10]: walk(value, depth + 1)
    walk(data)
    result['known_error_fields'] = sorted(names)
    if codes: result['service_codes'] = codes
    if hints: result['message_hint_tags'] = sorted(hints)
    return result
