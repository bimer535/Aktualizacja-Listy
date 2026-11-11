"""Reproducible native UI artwork, no animation or runtime blur."""
from pathlib import Path
import math
from PIL import Image,ImageDraw,ImageFilter
ROOT=Path(__file__).resolve().parents[1]/'src/MKEkinoE2'
def card(name,size,focus=False,fill=(17,36,62,245)):
 w,h=size;im=Image.new('RGBA',size,(0,0,0,0));d=ImageDraw.Draw(im)
 box=(8,8,w-9,h-9)
 if not focus:
  d.rounded_rectangle(box,16,fill=fill,outline=(110,153,189,210),width=1)
 else:
  # Overlay only: no opaque centre can cover either artwork or labels.
  glow=Image.new('RGBA',size);g=ImageDraw.Draw(glow)
  g.rounded_rectangle(box,16,outline=(0,153,255,255),width=7)
  im=glow.filter(ImageFilter.GaussianBlur(4));d=ImageDraw.Draw(im)
  d.rounded_rectangle(box,16,outline=(75,214,255,255),width=4)
  d.rounded_rectangle((12,12,w-13,h-13),12,outline=(235,252,255,255),width=1)
  # Completely transparent centre, including the blurred inner halo.
  d.rounded_rectangle((16,16,w-17,h-17),8,fill=(0,0,0,0))
 im.save(ROOT/name,optimize=True)
card('card.png',(224,408));card('card_focus.png',(224,408),True)
card('home_card.png',(224,216));card('home_focus.png',(224,216),True)
card('source_card.png',(284,120));card('source_focus.png',(284,120),True)
card('nav_focus.png',(132,48),True)
card('hero_focus.png',(244,54),True)
card('header.png',(972,62),False,fill=(14,50,80,225))
w,h=1280,720;im=Image.new('RGB',(w,h));p=im.load()
for y in range(h):
 for x in range(w):
  wave=(math.sin(x/270+y/140)+1)/2
  t=y/h
  p[x,y]=(int(10+18*t+3*wave),int(23+16*(1-t)+9*wave),int(47+32*t+10*wave))
im.save(ROOT/'background.png',optimize=True)
im=Image.new('RGBA',(w,h));p=im.load()
for y in range(h):
 for x in range(w):
  left=210*max(0,1-x/(w*.85))
  bottom=230*max(0,(y-h*.52)/(h*.48))
  a=int(max(left,bottom));p[x,y]=(4,10,30,a)
im.save(ROOT/'shade.png',optimize=True)
