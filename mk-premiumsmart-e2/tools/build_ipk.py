#!/usr/bin/env python3
"""Build plugin-only Enigma2 IPK and a complete corresponding source archive."""
import ast
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.3'
PACKAGE='enigma2-plugin-extensions-mkpremiumsmarte2'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/MKPremiumSmartE2/'


def tarball(files,mtime):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz',format=tarfile.GNU_FORMAT) as archive:
        for name,body in files:
            info=tarfile.TarInfo('./'+name);info.size=len(body);info.mode=0o644;info.mtime=mtime
            archive.addfile(info,io.BytesIO(body))
    return output.getvalue()


def main():
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    files=[]
    for path in sorted((ROOT/'src/MKPremiumSmartE2').iterdir()):
        if not path.is_file() or (path.suffix not in ('.py','.png','.txt','.so','.xml') and path.name!='LICENSE'):continue
        data=path.read_bytes()
        if path.suffix=='.py':ast.parse(data)
        files.append((PREFIX+path.name,data))
    control=('Package: '+PACKAGE+'\nVersion: '+VERSION+'\nArchitecture: all\n'
             'Description: MK PremiumSmart E2 - standalone movies and series client (test release)\n'
             'Maintainer: MK\nSection: extra\nPriority: optional\nLicense: GPL-3.0\n'
             'Depends: enigma2, python3-core, python3-html, python3-ctypes, python3-pycryptodome\n').encode()
    data=bytearray(b'!<arch>\n')
    for name,body in [('debian-binary',b'2.0\n'),('control.tar.gz',tarball([('control',control)],0)),('data.tar.gz',tarball(files,int(time.time())))]:
        header=((name+'/').ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'100644'.ljust(8)+str(len(body)).ljust(10)+'`\n')
        data.extend(header.encode());data.extend(body)
        if len(body)%2:data.extend(b'\n')
    package=output/('MK_PremiumSmart_E2_'+VERSION+'.ipk');package.write_bytes(data)
    manifest={'package':PACKAGE,'version':VERSION,
              'url':'https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-premiumsmart-e2/packages/'+package.name,
              'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),
              'notes':'Przewijanie na OpenPLi i OpenATV: kółko lewo/prawo i przyciski ⏪/⏩ wykonują skoki po 10 sekund; długie ⏪/⏩ po 60 sekund. Ochrona przed skokiem poza koniec filmu. Po aktualizacji uruchom ponownie interfejs Enigma2.'}
    manifest_file=output/'update.json';manifest_file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    source=output/('MK_PremiumSmart_E2_'+VERSION+'_source.zip')
    with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for folder in ['src','tools','tests','reference','native']:
            for path in sorted((ROOT/folder).rglob('*')):
                if not path.is_file() or '__pycache__' in path.parts:continue
                if path.suffix in ('.py','.png','.txt','.json','.c','.so','.xml') or path.name=='LICENSE':
                    archive.write(path,arcname='MK_PremiumSmart_E2/'+str(path.relative_to(ROOT)))
        archive.write(ROOT/'README.md',arcname='MK_PremiumSmart_E2/README.md')
        archive.write(manifest_file,arcname='MK_PremiumSmart_E2/update.json')
    report={p.name:{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [package,source]}
    (output/'release.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'version':VERSION,'plugin_files':len(files),'artifacts':report},indent=2))


if __name__=='__main__':main()
