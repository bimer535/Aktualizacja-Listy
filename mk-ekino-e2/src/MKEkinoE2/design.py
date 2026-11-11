# SPDX-License-Identifier: GPL-3.0-only
"""Native Enigma2 skins in a 1280x720 design, scaled to the actual OSD."""
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parent
NAV=('Główna','Filmy','Seriale','Szukaj','Ulubione','Oglądaj dalej','Opcje')

def dimensions():
    try:
        from enigma import getDesktop
        size=getDesktop(0).size();w,h=int(size.width()),int(size.height())
        if 960<=w<=3840 and 540<=h<=2160:return w,h
    except (ImportError,AttributeError,TypeError,ValueError):pass
    return 1280,720

def scale_skin(text,size=None):
    w,h=size or dimensions();root=ET.fromstring(text)
    root.set('size','%d,%d'%(w,h))
    for element in root.iter():
        if element is root:continue
        for attr in ('position','size'):
            value=element.get(attr,'')
            if ',' in value:
                x,y=map(int,value.split(','));element.set(attr,'%d,%d'%(round(x*w/1280),round(y*h/720)))
        for attr in ('itemHeight','borderWidth'):
            if element.get(attr):element.set(attr,str(max(1,round(int(element.get(attr))*h/720))))
        if element.get('font'):
            face,n=element.get('font').rsplit(';',1);element.set('font',face+';'+str(max(12,round(int(n)*min(w/1280,h/720)))))
    return ET.tostring(root,encoding='unicode')

def label(name,x,y,w,h,font=22,extra=''):
    return '<widget name="%s" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#ffffff" transparent="1" zPosition="4" %s />'%(name,x,y,w,h,font,extra)

def pix(name,x,y,w,h,path=None,z=1):
    return '<widget name="%s" position="%d,%d" size="%d,%d" alphatest="blend" zPosition="%d" %s />'%(name,x,y,w,h,z,('pixmap="%s" scale="1"'%(ROOT/path)) if path else '')

def header():
    p=[pix('header',224,33,994,56,'header.png',3),pix('logo',38,35,50,50,'icon.png',5),label('brand',96,46,120,32,26)]
    for i,name in enumerate(NAV):
        x=230+i*140
        p += [pix('navmark%d'%i,x,38,138,46,'nav_focus.png',3),label('nav%d'%i,x+5,49,128,30,20,'halign="center"')]
    return p

def grid_skin(mode='catalogue',size=None):
    compact=mode in ('sources','seasons');home=mode=='home'
    p=['<screen name="MKKinoCinema" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#0b1429">',pix('wallpaper',0,0,1280,720,'background.png',0),pix('backdrop',0,0,1280,720,z=1),pix('shade',0,0,1280,720,'shade.png',2)]
    p+=header()
    if home:
        p += [label('hero_meta',48,165,680,30,20),label('hero_title',48,210,780,105,42),label('hero_desc',48,321,710,84,22),pix('hero_focus',42,421,232,54,'nav_focus.png',3),label('hero_action',57,436,250,30,23),label('hero_count',1080,435,150,30,22,'halign="right"')]
        p += [label('heading',48,499,1175,36,27)]
    elif compact:
        p += [pix('cover0',48,140,170,255,z=3),label('hero_meta',250,139,960,30,20),label('hero_title',250,181,960,68,34),label('hero_desc',250,263,960,147,22),label('heading',48,446,1170,36,26)]
    else:p += [label('heading',48,116,1165,42,30)]
    columns=4 if compact else 5
    for i in range(columns):
        x=42+i*(300 if compact else 240)
        y=500 if compact else (550 if home else 177)
        height=118 if compact else (370 if home else 400)
        p += [pix('cardbg%d'%i,x,y,292 if compact else 232,height,'source_card.png' if compact else 'card.png',2),pix('mark%d'%i,x,y,292 if compact else 232,height,'source_focus.png' if compact else 'card_focus.png',3)]
        if compact:
            p += [label('title%d'%i,x+17,y+22,256,64,25),label('rating%d'%i,x+17,y+87,256,25,18)]
        else:
            cover_height=300 if home else 302
            p += [label('empty%d'%i,x+8,y+8,216,cover_height,28,'halign="center" valign="center"'),pix('cover%d'%i,x+8,y+8,216,cover_height,z=3),label('title%d'%i,x+12,y+cover_height+17,208,56,20),label('rating%d'%i,x+12,y+cover_height+76,208,25,17)]
    # Home shelf is intentionally partly below the fold; Down expands it to the catalogue layout.
    p += [label('detail',48,625,1170,28,18),label('hint',48,669,1175,27,18),'</screen>']
    return scale_skin(''.join(p),size)

def main_skin(size=None):
    p=['<screen name="MKKinoMain" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#0b1429">',pix('wallpaper',0,0,1280,720,'background.png',0)]
    p += [label('heading',48,39,850,40,30),label('version',1050,46,180,24,18,'halign="right"'),label('path',48,91,1180,25,19),pix('poster',48,147,200,300,z=2),label('poster_hint',56,230,184,100,24,'halign="center"'),label('selected_title',280,143,930,65,34),label('rating',280,217,450,35,23),label('metadata',740,217,470,35,21)]
    p += ['<widget name="description" position="280,270" size="930,176" font="Regular;23" foregroundColor="#eff5ff" backgroundColor="#142538" transparent="1" zPosition="4" />','<widget name="list" position="48,480" size="1180,126" font="Regular;25" itemHeight="42" foregroundColor="#eff5ff" backgroundColor="#142538" foregroundColorSelected="#ffffff" backgroundColorSelected="#1261a1" scrollbarMode="showOnDemand" zPosition="4" />']
    p += [label('status',48,616,980,30,20),label('counter',1040,616,190,30,20,'halign="right"'),label('options_hint',48,651,1180,22,17)]
    for i,name in enumerate(('red','green','yellow','blue')):p.append(label(name,48+i*298,686,290,27,18))
    p.append('</screen>');return scale_skin(''.join(p),size)

def description_skin(size=None):
    return scale_skin('<screen name="MKKinoDescription" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#0b1429">'+pix('wallpaper',0,0,1280,720,'background.png',0)+label('title',60,50,1160,75,30)+'<widget name="body" position="60,145" size="1160,475" font="Regular;25" foregroundColor="#ffffff" backgroundColor="#142538" transparent="1" zPosition="3" />'+label('hint',60,661,1160,32,21)+'</screen>',size)
