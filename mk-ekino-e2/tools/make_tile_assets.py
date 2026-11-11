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
im=Image.new('RGB',(200,300),(20,32,51));d=ImageDraw.Draw(im)
d.line([(48,105),(151,105)],fill=(70,210,255),width=10)
d.line([(117,70),(152,105),(117,140)],fill=(70,210,255),width=10)
font=ImageFont.truetype('DejaVuSans.ttf',27)
d.text((100,194),'Następna',font=font,fill='white',anchor='mt');d.text((100,231),'strona',font=font,fill='white',anchor='mt')
im.save(ROOT/'next_page.png',optimize=True)
q=QrCodeWidget('mailto:bimer535@wp.pl');q.draw();modules=q.qr.modules
scale=8;border=4;count=len(modules);im=Image.new('RGB',((count+2*border)*scale,)*2,'white');d=ImageDraw.Draw(im)
for y,row in enumerate(modules):
 for x,dark in enumerate(row):
  if dark:d.rectangle(((x+border)*scale,(y+border)*scale,(x+border+1)*scale-1,(y+border+1)*scale-1),fill='black')
im.save(ROOT/'contact_qr.png',optimize=True)
