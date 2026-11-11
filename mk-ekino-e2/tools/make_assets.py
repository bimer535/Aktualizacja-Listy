"""Reproducible native UI artwork, no animation or runtime blur."""
from pathlib import Path
import math
from PIL import Image,ImageDraw,ImageFilter
ROOT=Path(__file__).resolve().parents[1]/'src/MKEkinoE2'
def card(name,size,focus=False,fill=(17,36,62,245)):
 w,h=size;im=Image.new('RGBA',size,(0,0,0,0));d=ImageDraw.Draw(im)
 d.rounded_rectangle((7,7,w-8,h-8),18,fill=fill,outline=(110,153,189,200),width=1)
 if focus:
  glow=Image.new('RGBA',size);g=ImageDraw.Draw(glow);g.rounded_rectangle((7,7,w-8,h-8),18,outline=(0,153,255,255),width=9)
  im=Image.alpha_composite(im,glow.filter(ImageFilter.GaussianBlur(4)));d=ImageDraw.Draw(im)
  d.rounded_rectangle((7,7,w-8,h-8),18,outline=(87,222,255,255),width=4)
  d.rounded_rectangle((11,11,w-12,h-12),14,outline=(228,251,255,255),width=1)
 im.save(ROOT/name,optimize=True)
card('card.png',(232,400));card('card_focus.png',(232,400),True)
card('source_card.png',(292,118));card('source_focus.png',(292,118),True)
card('nav_focus.png',(232,54),True,fill=(10,90,145,220))
card('header.png',(994,56),False,fill=(14,50,80,225))
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
