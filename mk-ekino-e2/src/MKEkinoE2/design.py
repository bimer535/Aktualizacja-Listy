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
    p=[pix('header',244,48,972,62,'header.png',3),pix('logo',64,55,44,44,'icon.png',5),label('brand',116,62,122,32,24)]
    for i,name in enumerate(NAV):
        x=250+i*136
        p += [pix('navmark%d'%i,x,55,132,48,'nav_focus.png',6),label('nav%d'%i,x+4,66,124,28,18,'halign="center"')]
    return p

def grid_skin(mode='catalogue',size=None):
    compact=mode in ('sources','seasons');home=mode=='home'
    p=['<screen name="MKKinoCinema" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#0b1429">',pix('wallpaper',0,0,1280,720,'background.png',0),pix('backdrop',0,0,1280,720,z=1),pix('shade',0,0,1280,720,'shade.png',2)]
    p+=header()
    if home:
        p += [label('hero_meta',64,134,680,28,18),label('hero_title',64,170,750,80,34),label('hero_desc',64,255,740,56,20),pix('hero_focus',56,324,244,54,'hero_focus.png',6),label('hero_action',76,339,210,29,22),label('hero_count',1064,340,144,28,21,'halign="right"'),label('heading',64,386,1152,32,25)]
    elif compact:
        p += [pix('cover0',64,142,168,252,z=3),label('hero_meta',264,142,944,28,19),label('hero_title',264,182,944,76,32),label('hero_desc',264,270,944,136,22),label('heading',64,436,1152,36,26)]
    else:p += [label('heading',64,132,1152,38,28)]
    columns=4 if compact else 5
    for i in range(columns):
        x=56+i*(292 if compact else 232)
        y=484 if compact else (424 if home else 184)
        width,height=(284,120) if compact else (224,216) if home else (224,408)
        bg='source_card.png' if compact else 'home_card.png' if home else 'card.png'
        focus='source_focus.png' if compact else 'home_focus.png' if home else 'card_focus.png'
        # The outline is a transparent overlay ABOVE pictures and text.
        p += [pix('cardbg%d'%i,x,y,width,height,bg,2),pix('mark%d'%i,x,y,width,height,focus,6)]
        if compact:
            p += [label('title%d'%i,x+20,y+20,244,57,24),label('rating%d'%i,x+20,y+84,244,24,17)]
        elif home:
            p += [pix('cover%d'%i,x+54,y+12,116,174,z=3),label('title%d'%i,x+14,y+188,196,20,16,'halign="center"')]
        else:
            p += [pix('cover%d'%i,x+16,y+16,192,288,z=3),label('title%d'%i,x+18,y+315,188,54,20),label('rating%d'%i,x+18,y+375,188,23,17)]
    if not home:p.append(label('detail',64,614,1152,26,18))
    p += [label('hint',64,648,1152,24,17),'</screen>']
    return scale_skin(''.join(p),size)

def main_skin(size=None):
    p=['<screen name="MKKinoMain" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#0b1429">',pix('wallpaper',0,0,1280,720,'background.png',0)]
    p += [label('heading',64,54,850,40,30),label('version',1040,61,168,24,18,'halign="right"'),label('path',64,105,1152,25,19),pix('poster',48,147,200,300,z=2),label('poster_hint',56,230,184,100,24,'halign="center"'),label('selected_title',280,143,930,65,34),label('rating',280,217,450,35,23),label('metadata',740,217,470,35,21)]
    p += ['<widget name="description" position="280,270" size="930,176" font="Regular;23" foregroundColor="#eff5ff" backgroundColor="#142538" transparent="1" zPosition="4" />','<widget name="list" position="48,480" size="1180,126" font="Regular;25" itemHeight="42" foregroundColor="#eff5ff" backgroundColor="#142538" foregroundColorSelected="#ffffff" backgroundColorSelected="#1261a1" scrollbarMode="showOnDemand" zPosition="4" />']
    p += [label('status',64,602,956,26,19),label('counter',1030,602,178,26,19,'halign="right"'),label('options_hint',64,630,1152,18,16)]
    for i,name in enumerate(('red','green','yellow','blue')):p.append(label(name,64+i*288,650,280,22,17))
    p.append('</screen>');return scale_skin(''.join(p),size)

def description_skin(size=None):
    return scale_skin('<screen name="MKKinoDescription" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#0b1429">'+pix('wallpaper',0,0,1280,720,'background.png',0)+label('title',60,50,1160,75,30)+'<widget name="body" position="60,145" size="1160,475" font="Regular;25" foregroundColor="#ffffff" backgroundColor="#142538" transparent="1" zPosition="3" />'+label('hint',60,661,1160,32,21)+'</screen>',size)
