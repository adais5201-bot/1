import sys; sys.path.insert(0,'/home/user/1/tools/shp')
from shpio import read_shp, palette, to_rgb
import numpy as np
from scipy import ndimage
import coasttwin as ct
pal=palette()
def load(f):
    return np.array([x['img'] for x in read_shp('x/m/%s.shp'%f)['frames']])
CNN=load('gggcnn_a'); TUR=load('ngturr_a')
cmode=np.load('kb/mode.npy'); tmode=np.load('kb/turr_mode.npy')
def tmask(img,mode,keepbelow=None):
    d=(img!=mode)&(img>0)
    d=ndimage.binary_opening(d,np.ones((2,2)))|(d&ndimage.binary_dilation(ndimage.binary_opening(d,np.ones((2,2))),iterations=1))
    lab,n=ndimage.label(d); sz=ndimage.sum(d,lab,range(1,n+1)); m=lab==1+np.argmax(sz)
    return ndimage.binary_fill_holes(m)
CPIV=np.array([99.5,104.3]); TPIV=np.array([121.1,81.2])
def paste(dst,src,mask,off):
    ys,xs=np.nonzero(mask); ty,tx=ys+off[1],xs+off[0]
    ok=(ty>=0)&(ty<dst.shape[0])&(tx>=0)&(tx<dst.shape[1])
    dst[ty[ok],tx[ok]]=src[ys[ok],xs[ok]]
def conceptA(i,frames,dz=0):
    """NATURR finned base + twin China-cannon turret"""
    out=np.zeros((140,240),np.uint8); out[:]=tmode
    img=frames[i]; m=tmask(img,cmode) & (np.arange(200)[:,None] < 120)
    off=np.round(TPIV-CPIV).astype(int)+np.array([0,dz])
    paste(out,img,m,off); return out

def seg_band(shape,a,b,hw):
    ys,xs=np.mgrid[0:shape[0],0:shape[1]]
    v=np.stack([xs-a[0],ys-a[1]],-1); d=np.array(b,float)-a; L=max(np.hypot(*d),1e-6); dn=d/L
    t=v@dn; q=v@np.array([-dn[1],dn[0]])
    return (t>=-1)&(t<=L+1)&(np.abs(q)<=hw)
def naturr_turret(i):
    img=TUR[i]; m=tmask(img,tmode)&(np.arange(140)[:,None]<100)
    return img,m
EXT=12
def twin_naturr(i,cnn_frames,length=1.0):
    """NATURR gun house, elevated barrel removed, two level guns fitted"""
    img,m=naturr_turret(i); img=img.copy()
    u=ct.u(i); R=np.array([120.5,71])+17.5*u; Tp=np.array([120.5,55])+46.5*u
    if not 13<=i<=17:
        ys,xs=np.nonzero(m); d=29*u+np.array([0,-16.0]); dn=d/np.hypot(*d)
        k=np.argmax((xs-120.5)*dn[0]+(ys-71)*dn[1]); tip=np.array([xs[k],ys[k]],float)
        R=R+(tip-Tp); Tp=tip
    band=(seg_band(img.shape,R+0.15*(Tp-R),Tp+2*(Tp-R)/np.hypot(*(Tp-R)),4.6)|seg_band(img.shape,R+0.05*(Tp-R),R+0.5*(Tp-R),7.0))&m
    body=m&~band
    idx=ndimage.distance_transform_edt(band,return_distances=False,return_indices=True)
    nb=body[idx[0],idx[1]]
    # a band pixel is inside the house when house pixels lie on both sides of it
    inside=band&ndimage.binary_closing(body,np.ones((7,7)))
    img[inside]=img[idx[0],idx[1]][inside]
    m=body|inside
    core=ndimage.binary_opening(m,np.ones((3,3)))
    lab,n=ndimage.label(core); sz=ndimage.sum(core,lab,range(1,n+1)); core=lab==1+np.argmax(sz)
    m=m&ndimage.binary_dilation(core,iterations=1)
    # level twin guns from the China Cannon art
    f=cnn_frames[i]; s=ct.SEP*ct.u(i+8)
    B=np.zeros(f.shape,bool)
    for o in (s,-s): B|=ct.band(i,o)
    B&=f>0
    root=ct.C+ct.R0*u
    off=np.round(R-root+np.array([0,2])).astype(int)
    away=np.cos(np.radians(i*11.25))>0.2
    ys,xs=np.nonzero(B); ty,tx=ys+off[1],xs+off[0]
    ok=(ty>=0)&(ty<140)&(tx>=0)&(tx<240); ty,tx,ys,xs=ty[ok],tx[ok],ys[ok],xs[ok]
    m0=m.copy()
    for e in (EXT,0):                      # a copy pushed outward first makes the guns longer
        eo=np.round(e*u).astype(int)
        ty2,tx2=ty+eo[1],tx+eo[0]
        ok=(ty2>=0)&(ty2<140)&(tx2>=0)&(tx2<240)
        a,b,c,d=ty2[ok],tx2[ok],ys[ok],xs[ok]
        if away:
            vis=~(m0[a,b]); a,b,c,d=a[vis],b[vis],c[vis],d[vis]
        img[a,b]=f[c,d]; m[a,b]=True
    return img,m
def conceptB(i,cnn_frames):
    out=cmode.copy()
    img,m=twin_naturr(i,cnn_frames)
    off=np.round(CPIV-TPIV).astype(int)
    paste(out,img,m,off); return out

GW=np.array([120,150]); CG=np.array([99,126]); TG=np.array([119,96])
def compose(i,base,turret,cnn_frames,sh=True):
    """base/turret in ('cnn','tur'); returns image and shadow on a 240x200 canvas, ground at GW"""
    out=np.zeros((200,240),np.uint8); shd=np.zeros((200,240),bool)
    bimg,bg=(cmode,CG) if base=='cnn' else (tmode,TG)
    bsh=(CNN[64+i] if base=='cnn' else TUR[64+i])>0
    paste(out,bimg,bimg>0,GW-bg); paste(shd,bsh,bsh,GW-bg)
    if turret=='cnn':
        img=cnn_frames[i]; m=tmask(img,cmode)&(np.arange(200)[:,None]<120); piv,g=CPIV,CG
    else:
        img,m=twin_naturr(i,cnn_frames); piv,g=TPIV,TG
    bpiv=(CPIV-CG) if base=='cnn' else (TPIV-TG)
    off=np.round(GW+bpiv-piv).astype(int)
    paste(out,img,m,off)
    return out,shd
