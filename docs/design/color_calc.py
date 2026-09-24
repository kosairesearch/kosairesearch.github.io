import math
def srgb_to_lin(c):
    c=c/255
    return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def lin_to_srgb(v):
    v=max(0,min(1,v))
    return 12.92*v if v<=0.0031308 else 1.055*v**(1/2.4)-0.055
def hex2rgb(h):
    h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))
def rgb2hex(r,g,b): return '#%02x%02x%02x'%(round(r),round(g),round(b))
def lum(rgb):
    r,g,b=[srgb_to_lin(c) for c in rgb]; return 0.2126*r+0.7152*g+0.0722*b
def contrast(a,b):
    la,lb=lum(a),lum(b); hi,lo=max(la,lb),min(la,lb); return (hi+0.05)/(lo+0.05)
def blend(fg,alpha,bg): return tuple(fg[i]*alpha+bg[i]*(1-alpha) for i in range(3))
# OKLab/OKLCH
def rgb2oklch(rgb):
    r,g,b=[srgb_to_lin(c) for c in rgb]
    l=0.4122214708*r+0.5363325363*g+0.0514459929*b
    m=0.2119034982*r+0.6806995451*g+0.1073969566*b
    s=0.0883024619*r+0.2817188376*g+0.6299787005*b
    l_,m_,s_=l**(1/3),m**(1/3),s**(1/3)
    L=0.2104542553*l_+0.7936177850*m_-0.0040720468*s_
    a=1.9779984951*l_-2.4285922050*m_+0.4505937099*s_
    bb=0.0259040371*l_+0.7827717662*m_-0.8086757660*s_
    C=math.hypot(a,bb); H=math.degrees(math.atan2(bb,a))%360
    return L,C,H
def oklch2rgb(L,C,H):
    a=C*math.cos(math.radians(H)); bb=C*math.sin(math.radians(H))
    l_=L+0.3963377774*a+0.2158037573*bb
    m_=L-0.1055613458*a-0.0638541728*bb
    s_=L-0.0894841775*a-1.2914855480*bb
    l,m,s=l_**3,m_**3,s_**3
    r=+4.0767416621*l-3.3077115913*m+0.2309699292*s
    g=-1.2684380046*l+2.6097574011*m-0.3413193965*s
    b=-0.0041960863*l-0.7034186147*m+1.7076147010*s
    return tuple(lin_to_srgb(v)*255 for v in (r,g,b))
def fmt(rgb): return rgb2hex(*rgb)
BG0=hex2rgb('#f9f8f6'); BG1=hex2rgb('#ffffff'); INK=hex2rgb('#141414')
print("bg0 #f9f8f6 oklch", ["%.3f"%v for v in rgb2oklch(BG0)])
print("ink #141414 oklch", ["%.3f"%v for v in rgb2oklch(INK)])
print("ink on bg0 %.2f, on white %.2f"%(contrast(INK,BG0),contrast(INK,BG1)))
H=rgb2oklch(BG0)[2]
print("\n== light neutral ramp (hue %.0f, C small) =="%H)
for L,C,label in [(0.985,0.003,'bg-0 page(ref)'),(0.965,0.004,'bg-2 subdued'),(0.94,0.005,'bg-3 pressed'),(0.90,0.006,'line-strong-ish'),(0.72,0.008,'fg-3 solid?'),(0.53,0.010,'fg-2 solid?'),(0.20,0.004,'ink ref')]:
    rgb=oklch2rgb(L,C,H); print("  L%.3f C%.3f -> %s  vs bg0 %.2f vs white %.2f  %s"%(L,C,fmt(rgb),contrast(rgb,BG0),contrast(rgb,BG1),label))
print("\n== alpha text over bg0 / white ==")
for a in (0.7,0.62,0.6,0.58,0.55,0.5):
    b0=blend((0,0,0),a,BG0); b1=blend((0,0,0),a,BG1)
    print("  rgba(0,0,0,%.2f): over bg0 %s %.2f | over white %s %.2f"%(a,fmt(b0),contrast(b0,BG0),fmt(b1),contrast(b1,BG1)))
print("\n== lines alpha over white (for 3:1 UI boundary) ==")
for a in (0.06,0.08,0.10,0.12,0.30,0.34,0.38):
    b1=blend((0,0,0),a,BG1); print("  rgba(0,0,0,%.2f) %s vs white %.2f vs bg0 %.2f"%(a,fmt(b1),contrast(b1,BG1),contrast(b1,BG0)))
print("\n== accent / up / down candidates (light) ==")
for h in ['#0d69d4','#1d4ed8','#1b64da','#1e5fbf','#1a5fb4','#2456b5','#2a5bd7','#e5383b','#d1293d','#c8102e','#c62828','#d12f33','#cf2e3a','#d42a36','#c9262f','#1f9d57','#15803d','#0f7a3d','#b42318','#5fc5ff','#9747ff']:
    rgb=hex2rgb(h); L,C,HH=rgb2oklch(rgb)
    print("  %s oklch(%.2f %.3f %.0f) vs bg0 %.2f vs white %.2f | white text on it %.2f"%(h,L,C,HH,contrast(rgb,BG0),contrast(rgb,BG1),contrast(rgb,BG1)))
print("\n== dark ==")
for dbg in ['#0e0e16','#141414','#121212','#161514','#131312']:
    rgb=hex2rgb(dbg); L,C,HH=rgb2oklch(rgb); print("  dark bg %s oklch(%.3f %.3f %.0f)"%(dbg,L,C,HH))
DBG=hex2rgb('#141414')
Hd=rgb2oklch(BG0)[2]
for L,C,label in [(0.24,0.003,'surface-1'),(0.28,0.003,'surface-2'),(0.32,0.003,'surface-3'),(0.955,0.003,'fg-1 dark'),(0.93,0.003,'fg-1 alt')]:
    rgb=oklch2rgb(L,C,Hd); print("  L%.3f -> %s vs #141414 %.2f  %s"%(L,fmt(rgb),contrast(rgb,DBG),label))
for a in (0.9,0.88,0.72,0.6,0.58,0.56,0.5):
    b=blend((255,255,255),a,DBG); print("  rgba(255,255,255,%.2f) over #141414 %s %.2f"%(a,fmt(b),contrast(b,DBG)))
for a in (0.08,0.10,0.12,0.3,0.36):
    b=blend((255,255,255),a,DBG); print("  line rgba(255,255,255,%.2f) %s %.2f"%(a,fmt(b),contrast(b,DBG)))
for h in ['#ff5b5e','#f26b72','#ff6b6e','#f0625f','#5fa8ff','#6ea3f5','#7aa2ff','#5c9dff','#0d69d4','#3d8bff','#4d95f0','#5fc5ff']:
    rgb=hex2rgb(h); L,C,HH=rgb2oklch(rgb); print("  %s oklch(%.2f %.3f %.0f) vs #141414 %.2f vs surface #1c1c1b %.2f"%(h,L,C,HH,contrast(rgb,DBG),contrast(rgb,hex2rgb('#1c1c1b'))))
