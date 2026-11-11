# SPDX-License-Identifier: GPL-3.0-only
"""Explicit in-plugin updates from MK's public GitHub repository."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import urllib.request

PACKAGE='enigma2-plugin-extensions-mkekinoe2'
BASE='https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-ekino-e2/'
MANIFEST=BASE+'update.json'
MAX_PACKAGE=10*1024*1024


class UpdateError(Exception):pass


def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}',value):
        raise UpdateError('invalid_version')
    return tuple(map(int,value.split('.')))


def validate(data):
    if not isinstance(data,dict):raise UpdateError('invalid_manifest')
    release=data.get('version');version(release)
    expected=BASE+'packages/MK_Ekino_E2_'+release+'.ipk'
    if data.get('package')!=PACKAGE or data.get('url')!=expected:raise UpdateError('invalid_manifest')
    if not isinstance(data.get('sha256'),str) or not re.fullmatch(r'[0-9a-f]{64}',data['sha256']):raise UpdateError('invalid_manifest')
    size=data.get('size')
    if type(size) is not int or not 1000<=size<=MAX_PACKAGE:raise UpdateError('invalid_manifest')
    notes=data.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000:raise UpdateError('invalid_manifest')
    return {k:data[k] for k in ('version','package','url','sha256','size')}|{'notes':notes}


class GitHubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if not newurl.startswith(BASE):raise UpdateError('unexpected_download_address')
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def download(url,limit):
    if not url.startswith(BASE):raise UpdateError('unexpected_download_address')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),GitHubRedirect())
    request=urllib.request.Request(url,headers={'User-Agent':'MK-Ekino-E2-Updater','Cache-Control':'no-cache','Accept-Encoding':'identity'})
    with opener.open(request,timeout=20) as response:
        if not response.geturl().startswith(BASE):raise UpdateError('unexpected_download_address')
        data=response.read(limit+1)
    if len(data)>limit:raise UpdateError('download_too_large')
    return data


def check(current):
    release=validate(json.loads(download(MANIFEST,16384)))
    return dict(release,status='available' if version(release['version'])>version(current) else 'current')


def verify_package(data,release):
    if len(data)!=release['size'] or hashlib.sha256(data).hexdigest()!=release['sha256']:
        raise UpdateError('checksum_mismatch')
    if data[:8]!=b'!<arch>\n':raise UpdateError('invalid_package')
    pos=8;members={}
    while pos<len(data):
        header=data[pos:pos+60]
        if len(header)!=60 or header[-2:]!=b'`\n':raise UpdateError('invalid_package')
        try:size=int(header[48:58]);name=header[:16].decode('ascii').strip().rstrip('/')
        except (ValueError,UnicodeError):raise UpdateError('invalid_package')
        if size<0 or pos+60+size>len(data) or name in members:raise UpdateError('invalid_package')
        members[name]=data[pos+60:pos+60+size];pos+=60+size+(size%2)
    if set(members)!={'debian-binary','control.tar.gz','data.tar.gz'} or members['debian-binary']!=b'2.0\n':raise UpdateError('invalid_package')
    with tarfile.open(fileobj=io.BytesIO(members['control.tar.gz'])) as archive:
        control=archive.getmembers()
        if len(control)!=1 or control[0].name.lstrip('./')!='control' or not control[0].isfile() or control[0].size>16384:
            raise UpdateError('invalid_package')
        fields=dict(line.split(': ',1) for line in archive.extractfile(control[0]).read().decode().splitlines() if ': ' in line)
        if fields.get('Package')!=PACKAGE or fields.get('Version')!=release['version']:raise UpdateError('wrong_package')
    prefix='usr/lib/enigma2/python/Plugins/Extensions/MKEkinoE2/'
    with tarfile.open(fileobj=io.BytesIO(members['data.tar.gz'])) as archive:
        files=archive.getmembers()
        if not files or len(files)>100:raise UpdateError('invalid_package')
        for entry in files:
            name=entry.name.removeprefix('./')
            if not entry.isfile() or not name.startswith(prefix) or '..' in name.split('/') or entry.size>MAX_PACKAGE:
                raise UpdateError('wrong_package')


def install(release,current,expected_version,expected_sha):
    if release['version']!=expected_version or release['sha256']!=expected_sha:
        raise UpdateError('release_changed')
    if version(release['version'])<=version(current):raise UpdateError('not_newer')
    data=download(release['url'],MAX_PACKAGE)
    verify_package(data,release)
    with tempfile.TemporaryDirectory(prefix='mk-ekino-update-') as folder:
        path=Path(folder)/('MK_Ekino_E2_'+release['version']+'.ipk');path.write_bytes(data);path.chmod(0o600)
        result=subprocess.run(['/usr/bin/opkg','install',str(path)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        if result.returncode:raise UpdateError('install_failed')
        status=subprocess.run(['/usr/bin/opkg','status',PACKAGE],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
        text=status.stdout.decode('utf-8','replace')
        if status.returncode or ('Version: '+release['version']) not in text.splitlines() or not any(line.startswith('Status: ') and line.split()[-1]=='installed' for line in text.splitlines()):
            raise UpdateError('installed_version_not_confirmed')
    return {'status':'installed','version':release['version']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--current',required=True)
    parser.add_argument('--install',action='store_true');parser.add_argument('--expected-version');parser.add_argument('--expected-sha')
    args=parser.parse_args()
    try:
        result=check(args.current)
        if args.install:result=install(result,args.current,args.expected_version,args.expected_sha)
        print(json.dumps(result,ensure_ascii=False),flush=True);return 0
    except Exception as exc:
        reason=str(exc) if isinstance(exc,UpdateError) else 'network_or_package_error'
        print(json.dumps({'status':'error','reason':reason}),flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
