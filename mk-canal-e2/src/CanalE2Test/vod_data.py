"""CANAL+ public catalogue. Parses data, never evaluates website JavaScript."""
import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

SITE = 'https://www.canalplus.com'
HODOR = 'https://hodor.canalplus.pro/api/v2/'
MAX_BYTES = 12 * 1024 * 1024
ROOTS = [('Filmy', '/pl/film/'), ('Seriale', '/pl/seriale/'),
         ('Dokumentalne', '/pl/dokumenty/'), ('Dzieci', '/pl/dzieci/'),
         ('Produkcje oryginalne', '/pl/produkcje-oryginalne/'),
         ('Kolekcje', '/pl/kolekcje/'), ('Sport', '/pl/sport/')]


class VodError(Exception):
    def __init__(self, reason, **details):
        super().__init__(reason)
        self.reason, self.details = reason, details


def mapping(value):
    return value if isinstance(value, dict) else {}


def text(value, limit=5000):
    if isinstance(value, dict):
        value = value.get('text', '')
    if not isinstance(value, (str, int)):
        return ''
    return html.unescape(re.sub('<[^>]*>', '', str(value))).strip()[:limit]


def public_url(value):
    if not isinstance(value, str) or len(value) > 24000:
        raise VodError('vod_invalid_catalogue_url')
    if value.startswith('/pl/'):
        value = SITE + value
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'https' or p.hostname not in ('www.canalplus.com', 'hodor.canalplus.pro')
            or p.port not in (None, 443) or p.username or p.password or p.fragment):
        raise VodError('vod_invalid_catalogue_url')
    if p.hostname == 'www.canalplus.com' and not p.path.startswith('/pl/'):
        raise VodError('vod_invalid_catalogue_url')
    if p.hostname == 'hodor.canalplus.pro' and not p.path.startswith('/api/v2/'):
        raise VodError('vod_invalid_catalogue_url')
    return value


class CatalogueRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(urllib.parse.urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    url = public_url(url)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), CatalogueRedirect())
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 MK-Canal-E2', 'Accept-Language': 'pl-PL,pl;q=0.9',
        'Accept-Encoding': 'identity', 'Origin': SITE, 'Accept': 'text/html,application/json'})
    try:
        with opener.open(request, timeout=25) as r:
            raw = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise VodError('vod_catalogue_http_error', http_status=e.code) from None
    except (urllib.error.URLError, OSError):
        raise VodError('vod_catalogue_connection_error') from None
    if len(raw) > MAX_BYTES:
        raise VodError('vod_catalogue_response_too_large')
    try:
        return raw.decode('utf-8')
    except UnicodeError:
        raise VodError('vod_catalogue_invalid_encoding') from None


def script_value(document, name):
    match = re.search(r'\bwindow\.' + re.escape(name) + r'\s*=\s*', document)
    if not match:
        raise VodError('vod_catalogue_format_changed')
    value = document[match.end():]
    # serialize-javascript emits undefined. Only replace it outside JSON strings.
    value = re.sub(r'"(?:\\.|[^"\\])*"|\bundefined\b',
                   lambda m: 'null' if m.group() == 'undefined' else m.group(), value)
    try:
        return json.JSONDecoder().raw_decode(value)[0]
    except (ValueError, RecursionError):
        raise VodError('vod_catalogue_format_changed') from None


def documents(document):
    if document.lstrip().startswith(('{', '[')):
        try:
            raw = json.loads(document)
        except ValueError:
            raise VodError('vod_catalogue_format_changed') from None
        return [raw] if isinstance(raw, dict) else []
    state = script_value(document, 'REACT_QUERY_STATE')
    result = []
    for q in state.get('queries', []):
        data = q.get('state', {}).get('data')
        if isinstance(data, dict):
            result.extend(data.get('pages', [data]))
    return [d for d in result if isinstance(d, dict)]


def content_id(value):
    return str(value) if re.fullmatch(r'[0-9]{1,15}(?:_[0-9]{1,10})?', str(value)) else ''


def click_of(node):
    if not isinstance(node, dict):
        return {}
    media = mapping(node.get('mediaData'))
    linker = mapping(media.get('linkerData'))
    return mapping(node.get('onClick') or linker.get('mainOnClick') or node.get('mainOnClick'))


def reference(click):
    if not isinstance(click, dict):
        return None
    for k in ('path', 'URLPage'):
        value = click.get(k)
        try:
            public_url(value)
            return {'url': value}
        except VodError:
            pass
    return None


def normalize_item(node, episode=False):
    if not isinstance(node, dict):
        return None
    click = click_of(node)
    media = mapping(node.get('mediaData'))
    title = text(node.get('title') or click.get('displayName') or node.get('ariaLabel')
                 or mapping(media.get('image')).get('alt') or media.get('ariaLabel') or node.get('altImage'), 250)
    cid = content_id(node.get('contentID'))
    if episode and cid:
        season, number = node.get('seasonNumber'), node.get('episodeNumber')
        prefix = ('S%s E%s · ' % (season, number)) if season and number else ''
        return {'title': prefix + (title or 'Odcinek'), 'kind': 'play', 'id': cid,
                'description': text(node.get('summary'))}
    ref = reference(click)
    if title and ref:
        return {'title': title, 'kind': 'folder', 'request': ref,
                'description': text(node.get('summary') or node.get('subtitle'))}
    return None


def unique(items):
    result, seen = [], set()
    for item in items:
        if item:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                result.append(item)
                seen.add(key)
    return result


def next_page(paging):
    if not isinstance(paging, dict) or not paging.get('hasNextPage'):
        return None
    url = paging.get('URLPage')
    try:
        public_url(url)
    except VodError:
        return None
    # Current Hodor already supplies after=<cursor> inside URLPage. Preserve it.
    return {'title': 'Dalej →', 'kind': 'folder', 'request': {'url': url}}


def normalize_page(data, source_url):
    title = text(data.get('currentPage', {}).get('displayName') or 'CANAL+ VOD', 250)
    description, items = '', []
    detail = data.get('detail')
    if isinstance(detail, dict):
        title = text(detail.get('title') or title, 250)
        description = text(detail.get('summary') or mapping(detail.get('informations')).get('summary'))
        cid = content_id(detail.get('contentID'))
        seasons = data.get('selector') or detail.get('seasons') or []
        tabs = data.get('tabs') or []
        is_show = any(isinstance(t, dict) and t.get('displayTemplate') == 'episodesList' for t in tabs)
        if not is_show:
            is_show = data.get('currentPage', {}).get('displayTemplate') == 'detailShow'
        if cid and not is_show and not seasons:
            items.append({'title': '▶ Odtwórz · ' + title, 'kind': 'play', 'id': cid,
                          'description': description})
        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            if tab.get('displayTemplate') == 'episodesList':
                ref = reference(tab)
                if ref:
                    items.append({'title': 'Sezony i odcinki', 'kind': 'folder', 'request': ref})
    selectors = data.get('selector') or []
    if isinstance(selectors, list):
        for season in selectors:
            item = normalize_item(season)
            if item:
                items.append(item)
    episodes = data.get('episodes')
    if isinstance(episodes, dict):
        items.extend(normalize_item(n, True) for n in episodes.get('contents', []))
        items.append(next_page(episodes.get('paging')))
    contents = data.get('contents')
    if isinstance(contents, list):
        items.extend(normalize_item(n) for n in contents)
        items.append(next_page(data.get('paging')))
    for row in data.get('strates', []):
        if not isinstance(row, dict):
            continue
        children = unique(normalize_item(n) for n in row.get('contents', []))
        row_title = text(row.get('title'), 250)
        more = reference(click_of(row.get('button') or {}))
        if more:
            children.append({'title': 'Zobacz wszystkie →', 'kind': 'folder', 'request': more})
        following = next_page(row.get('paging'))
        if following:
            children.append(following)
        if row_title and children:
            items.append({'title': row_title, 'kind': 'folder',
                          'request': {'inline': {'title': row_title, 'items': children, 'description': ''},
                                      'refresh': {'url': source_url, 'category': row_title}}})
        else:
            items.extend(children)
    return {'title': title, 'description': description, 'items': unique(items)}


def load_page(request, fetcher=fetch):
    if not isinstance(request, dict):
        raise VodError('vod_invalid_request')
    if 'inline' in request:
        return request['inline']
    url = public_url(request.get('url', '/pl/film/'))
    raw = fetcher(url)
    pages = documents(raw)
    if not pages:
        raise VodError('vod_catalogue_empty_response')
    # Detail SSR preloads episodes and related titles. Follow the requested page,
    # never confuse the recommendations with the selected movie's episodes.
    requested_path = urllib.parse.urlsplit(url).path.rstrip('/')
    matches = [p for p in pages if str(p.get('currentPage', {}).get('path', '')).rstrip('/') == requested_path]
    page = matches[0] if matches else pages[0]
    if request.get('category'):
        rows = [r for r in page.get('strates', []) if isinstance(r, dict)
                and text(r.get('title'), 250) == request['category']]
        if not rows:
            raise VodError('vod_category_no_longer_available')
        result = normalize_page({'strates': rows}, url)
        return result['items'][0]['request']['inline']
    result = normalize_page(page, url)
    return result


def search(query, fetcher=fetch):
    query = text(query, 160)
    if not query:
        raise VodError('vod_empty_search')
    root = fetcher(SITE + '/pl/')
    state = script_value(root, '__data')
    app = state.get('application', {})
    token = app.get('token')
    pattern = app.get('settings', {}).get('searchUrl')
    if not isinstance(token, str) or not token or not isinstance(pattern, str):
        raise VodError('vod_search_configuration_missing')
    url = pattern.replace('{cmsToken}', urllib.parse.quote(token, safe=''))
    url = url.replace('{searchKey}', urllib.parse.quote(query, safe=''))
    if not url.startswith('https://'):
        url = HODOR + 'mycanalint/' + url.lstrip('/')
    result = load_page({'url': public_url(url)}, fetcher)
    result['title'] = 'Szukaj: ' + query
    return result
