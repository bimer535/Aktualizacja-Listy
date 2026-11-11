"""Ekino catalogue and filters from normal public HTML. No E2i imports."""
import html
import json
import re
from pathlib import Path
from urllib.parse import quote_plus, urljoin

BASE = 'https://ekino.ws/'
EPISODE = re.compile(r'/serie/watch/([^/+"\[\]]+)\+season\[(\d+)\]\+episode\[(\d+)\]')


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value))).strip()


def group(pattern, text, flags=re.S):
    match = re.search(pattern, text, flags)
    return match[1] if match else ''


def block(text, cls):
    return group(r'<ul\b[^>]*class="'+re.escape(cls)+r'"[^>]*>(.*?)</ul>', text)


def item(title, action, **kwargs):
    return dict(title=title, action=action, **kwargs)


def menu():
    return [item('Filmy','categories'), item('Seriale','series'),
            item('Kontynuuj oglądanie','continue'),item('Ulubione','favourites'),
            item('Dla dzieci','versions',cat='2,3,5,6'),
            item('Wyszukaj','search'), item('Historia wyszukiwania','history')]


def fetch(client, url):
    ok, text = client.getPage(url, {'header': {'Referer':BASE}})
    if not ok:
        raise ValueError('catalogue_http_error')
    if 'Attention Required! | Cloudflare' in text or 'cf-chl-' in text:
        raise ValueError('catalogue_verification_required')
    return str(text)


def filters(text, kind, current):
    common = {k:current[k] for k in ('cat','version','year') if k in current}
    if kind=='categories':
        out=[item('--Wszystkie--','versions')]
        text=re.sub(r'<!--.*?-->','',block(text,'movieCategories'),flags=re.S)
        for code,title in re.findall(r'<a[^>]+href="[^\"]*kategoria\[(\d+)\][^\"]*"[^>]*>(.*?)</a>',text,re.S):
            out.append(item(clean(title),'versions',cat=code))
    elif kind=='versions':
        out=[item('--Wszystkie--','years',**common)]
        for code,title in re.findall(r'<li[^>]+data-id="([^\"]+)"[^>]*>(.*?)</li>',block(text,'quality'),re.S):
            out.append(item(clean(title),'years',**dict(common,version=code)))
    else:
        out=[item('--Wszystkie--','movies',**common)]
        for year in re.findall(r'data-id="(\d{4})"',block(text,'filtyear')):
            out.append(item(year,'movies',**dict(common,year=year)))
    if len(out)<2:
        raise ValueError('catalogue_filters_missing')
    return out


def movie_url(current):
    result=BASE+'movie/cat/strona[%d]+sort[add]+method[desc]+' % int(current.get('page',1))
    for key,name in [('cat','kategoria'),('version','wersja'),('year','rok')]:
        value=current.get(key)
        if value:
            if not re.fullmatch(r'[A-Za-z0-9,]{1,50}',str(value)):
                raise ValueError('invalid_filter')
            result+=name+'['+str(value)+']+'
    return result


def card_rating(part):
    score=clean(group(r'class=["\']sum-vote["\'][^>]*>\s*<div\b[^>]*>(.*?)</div>',part))
    votes=clean(group(r'>\s*Ocen\s*</font>\s*<br\s*/?>\s*<font\b[^>]*>(.*?)</font>',part))
    if not re.fullmatch(r'\d{1,2}(?:[.,]\d{1,2})?',score):return {}
    value=float(score.replace(',','.'))
    if not 0<=value<=10:return {}
    count=int(votes) if re.fullmatch(r'\d{1,9}',votes) else None
    # Zero votes means unrated, rather than an actual score of zero.
    label='Ekino: brak ocen' if count==0 else 'Ekino: '+score.replace('.',',')+'/10'
    if count is not None and count>0:label+=' · głosów: '+str(count)
    return {'rating':value,'rating_votes':count,'rating_label':label}


def cards(text, url, episodes=False):
    result=[];seen=set()
    for part in re.split(r'<div[^>]*class="movies-list-item[^\"]*"',text)[1:]:
        href=group(r'href="([^\"]*/(?:movie|serie)/show/[^\"]+)"',part)
        if not href:
            continue
        target=urljoin(url,html.unescape(href))
        if target in seen:
            continue
        seen.add(target)
        title_block=group(r'class="title"[^>]*>(.*?)</div>',part)
        title=clean(group(r'<a[^>]*>(.*?)</a>',title_block)) or clean(group(r'alt="([^\"]+)"',part)).split(' / ')[0]
        if not title:
            continue
        original=clean(group(r'<a[^>]*class="blue"[^>]*>(.*?)</a>',title_block))
        year=clean(group(r'class="cates">\s*(\d{4})',part))
        version=clean(group(r'<i title="([^\"]+)"',part))
        desc=clean(group(r'class="movieDesc">(.*?)</div>',part))
        rating=card_rating(part)
        description=' | '.join(x for x in [rating.get('rating_label'),original,year,version] if x)
        description+='\n'+desc if desc else ''
        movie='/movie/show/' in target
        ep=EPISODE.search(part) if episodes else None
        extra={}
        if ep:
            extra={'series_url':target,'series_title':title,'season':ep[2],'episode':int(ep[3])}
            target=BASE+'serie/watch/%s+season[%s]+episode[%s]+' % ep.groups()
            title+=' S%02dE%02d' % (int(ep[2]),int(ep[3]))
        result.append(item(title,'sources' if movie or ep else 'seasons',url=target,
                           desc=description,synopsis=desc,original_title=original,year=year,language_version=version,
                           icon=urljoin(url,group(r'<img[^>]+src="([^\"]+)"',part)),**rating,**extra))
    return result


def paged(text,url,current,episodes=False):
    out=cards(text,url,episodes)
    next_url=group(r'<a[^>]*title="Nast[^\"]*pna strona"[^>]*href="([^\"]+)"',text)
    if not next_url:
        next_url=group(r'<a[^>]*href="([^\"]+)"[^>]*title="Nast[^\"]*pna strona"',text)
    if out and next_url:
        follow=dict(current,title='Następna strona',url=urljoin(url,html.unescape(next_url)),action='page',pagination=True)
        out.append(follow)
    return out


def series_menu(text):
    out=[]
    for index,part in enumerate(re.split(r'<h4[^>]*>',text)[1:]):
        title=clean(part.split('</h4>',1)[0])
        if title and ('movies-list-item' in part or 'class="b"' in part):
            out.append(item(title,'series_section',section=index))
    out.append(item('Seriale A–Z','series_az'))
    return out


def seasons(text,current):
    out=[]
    desc=clean(group(r'class="descriptionMovie">(.*?)</div>',text))
    for number,_ in re.findall(r'<p>Sezon (\d+)</p>\s*<ul class="list-series">(.*?)</ul>',text,re.S):
        extra={k:current[k] for k in ('icon','rating','rating_label','rating_votes') if k in current}
        out.append(item('Sezon '+number,'episodes',url=current['url'],season=number,
                        series_title=current.get('title',''),desc=desc,**extra))
    return sorted(out,key=lambda x:int(x['season']))


def episodes(text,current):
    out=[]
    for season,body in re.findall(r'<p>Sezon (\d+)</p>\s*<ul class="list-series">(.*?)</ul>',text,re.S):
        if season!=current['season']:
            continue
        for href,title in re.findall(r'<a[^>]+href="([^\"]+)"[^>]*>(.*?)</a>',body,re.S):
            match=EPISODE.search(href)
            if match:
                extra={k:current[k] for k in ('icon','rating','rating_label','rating_votes') if k in current}
                out.append(item('S%02dE%02d — %s' % (int(match[2]),int(match[3]),clean(title)),
                                'sources',url=urljoin(BASE,html.unescape(href)),desc=current.get('series_title',''),
                                series_title=current.get('series_title',''),series_url=current.get('url',''),
                                season=match[2],episode=int(match[3]),**extra))
    return sorted(out,key=lambda x:x['episode'])


def source_items(text,current):
    labels={}
    for identifier,body in re.findall(r'<a[^>]+href="#([^\"]+)"[^>]*>(.*?)</a>',block(text,'players'),re.S):
        labels[identifier]=', '.join(clean(x) for x in re.findall(r'title="([^\"]+)"',body))
    out=[];seen=set();ordinals={}
    for provider,key in re.findall(r"ShowPlayer\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\)",text):
        if provider not in ('player','voe','mix'):
            continue
        if (provider,key) in seen:
            continue
        seen.add((provider,key))
        index=ordinals.get(provider,0);ordinals[provider]=index+1
        label=labels.get(key+'-'+provider,'')
        name=provider+(' (%d)' % (index+1) if index else '')
        extra={k:v for k,v in current.items() if k in ('icon','rating','rating_label','rating_votes','desc','synopsis','series_title','series_url','season','episode','year','language_version')}
        out.append(item(name+(' — '+label if label else ''),'resolve',provider=provider,provider_index=index,
                        url=current['url'],movie_title=current.get('title','Film'),**extra))
    return sorted(out,key=lambda x:('player','voe','mix').index(x['provider']))


def browse(client,current):
    action=current.get('action','main')
    if action=='main':return menu()
    if action in ('categories','versions','years'):
        return filters(fetch(client,BASE+'movie/cat/+'),action,current)
    if action=='movies':
        url=movie_url(current);return paged(fetch(client,url),url,current)
    if action=='page':
        return paged(fetch(client,current['url']),current['url'],current)
    if action=='search_results':
        url=BASE+'search/qf/?q='+quote_plus(current['query'])
        return paged(fetch(client,url),url,current)
    if action in ('seasons','episodes','sources'):
        text=fetch(client,current['url'])
        return {'seasons':seasons,'episodes':episodes,'sources':source_items}[action](text,current)
    if action=='next_episode':
        series_url=current.get('series_url','')
        if not series_url.startswith(BASE+'serie/show/'):raise ValueError('next_episode_unavailable')
        text=fetch(client,series_url)
        seasons_found=seasons(text,dict(current,url=series_url,title=current.get('series_title','Serial')))
        all_episodes=[]
        for season in seasons_found:all_episodes.extend(episodes(text,season))
        number=(int(current.get('season',0)),int(current.get('episode',0)))
        return next(([entry] for entry in all_episodes if (int(entry['season']),int(entry['episode']))>number),[])
    text=fetch(client,BASE+'serie/')
    if action=='series':return series_menu(text)
    if action=='series_section':
        sections=re.split(r'<h4[^>]*>',text)[1:]
        index=int(current['section'])
        if not 0<=index<len(sections):return []
        part=sections[index]
        out=cards(part,BASE+'serie/',episodes=True)
        if not out:
            seen=set()
            for href,title in re.findall(r'<a class="b"\s+href="([^\"]+)">([^<]+)</a>',part):
                if href not in seen:
                    seen.add(href);out.append(item(clean(title),'seasons',url=urljoin(BASE,href)))
        return out
    if action=='series_az':
        out=[]
        for href,letter,count in re.findall(r'href="([^\"]+)"><span class="name">([^<]+)</span><span\s+class="count">(\d+)<',block(text,'serialsmenu')):
            if count!='0':out.append(item(clean(letter)+' ('+count+')','page',url=urljoin(BASE,href)))
        return out
    raise ValueError('unknown_catalogue_action')
