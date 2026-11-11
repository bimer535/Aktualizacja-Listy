"""Generate fixed-size focus overlay, next-page card and correct contact QR."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageFont
from reportlab.graphics.barcode.qr import QrCodeWidget
ROOT=Path(__file__).resolve().parents[1]/'src/MKEkinoE2'
size=(216,316);w,h=size
im=Image.new('RGBA',size);d=ImageDraw.Draw(im)
d.rounded_rectangle((4,4,w-5,h-5),8,outline=(0,165,255,255),width=4)
im=im.filter(ImageFilter.GaussianBlur(2));d=ImageDraw.Draw(im)
d.rounded_rectangle((4,4,w-5,h-5),8,outline=(28,192,255,255),width=3)
d.rounded_rectangle((7,7,w-8,h-8),5,outline=(220,251,255,255),width=1)
d.rectangle((8,8,w-9,h-9),fill=(0,0,0,0))
im.save(ROOT/'poster_focus.png',optimize=True)
# Supersampling keeps the rounded arrow smooth at native 200x300.
scale=4;im=Image.new('RGB',(200*scale,300*scale));px=im.load()
for y in range(300*scale):
 for x in range(200*scale):
  t=y/(300*scale);px[x,y]=(int(18+5*t),int(34+7*t),int(55+12*t))
d=ImageDraw.Draw(im)
def box(values):return tuple(round(v*scale) for v in values)
d.ellipse(box((40,43,160,163)),fill=(23,57,84),outline=(57,132,174),width=scale)
def stroke(points,color,width):
 points=[(round(x*scale),round(y*scale)) for x,y in points];w=round(width*scale)
 d.line(points,fill=color,width=w,joint='curve')
 r=w/2
 for x,y in (points[0],points[-1]):d.ellipse((int(x-r),int(y-r),int(x+r),int(y+r)),fill=color)
stroke([(72,103),(129,103)],(218,247,255),6)
stroke([(108,82),(130,103),(108,124)],(100,218,255),6)
font=ImageFont.truetype('DejaVuSans.ttf',25*scale)
d.text((100*scale,193*scale),'Następna',font=font,fill=(246,250,255),anchor='mt')
d.text((100*scale,228*scale),'strona',font=font,fill=(246,250,255),anchor='mt')
d.rounded_rectangle(box((79,270,121,273)),radius=scale,fill=(65,181,224))
im.resize((200,300),Image.Resampling.LANCZOS).save(ROOT/'next_page.png',optimize=True)
q=QrCodeWidget('mailto:bimer535@wp.pl');q.draw();modules=q.qr.modules
scale=8;border=4;count=len(modules);im=Image.new('RGB',((count+2*border)*scale,)*2,'white');d=ImageDraw.Draw(im)
for y,row in enumerate(modules):
 for x,dark in enumerate(row):
  if dark:d.rectangle(((x+border)*scale,(y+border)*scale,(x+border+1)*scale-1,(y+border+1)*scale-1),fill='black')
im.save(ROOT/'contact_qr.png',optimize=True)
