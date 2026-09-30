import struct, numpy as np
def read_shp(path):
    d=open(path,'rb').read()
    z,w,h,n=struct.unpack('<4H',d[:8])
    frames=[]
    for i in range(n):
        o=8+i*24
        x,y,fw,fh,flags,r,g,b,a,res1,off=struct.unpack('<4HI4BII',d[o:o+24])
        img=np.zeros((h,w),np.uint8)
        if fw and fh and off:
            if flags==3:
                p=off; buf=np.zeros((fh,fw),np.uint8)
                for row in range(fh):
                    ln,=struct.unpack('<H',d[p:p+2]); q=p+2; c=0; end=p+ln
                    while q<end:
                        v=d[q]; q+=1
                        if v==0:
                            c+=d[q]; q+=1
                        else:
                            buf[row,c]=v; c+=1
                    p=end
            elif flags==2:
                p=off; buf=np.zeros((fh,fw),np.uint8)
                for row in range(fh):
                    ln,=struct.unpack('<H',d[p:p+2]); buf[row,:ln-2]=np.frombuffer(d[p+2:p+ln],np.uint8); p+=ln
            else:
                buf=np.frombuffer(d[off:off+fw*fh],np.uint8).reshape(fh,fw)
            img[y:y+fh,x:x+fw]=buf
        frames.append(dict(img=img,x=x,y=y,w=fw,h=fh,flags=flags,rgb=(r,g,b)))
    return w,h,frames
def write_shp(path,w,h,imgs,compress=True):
    # imgs: list of HxW uint8 arrays full-canvas
    hdr=struct.pack('<4H',0,w,h,len(imgs)); entries=[]; data=b''; base=8+24*len(imgs)
    for img in imgs:
        ys,xs=np.nonzero(img)
        if len(ys)==0:
            entries.append(struct.pack('<4HI4BII',0,0,0,0,0,0,0,0,0,0,0)); continue
        y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
        crop=img[y0:y1,x0:x1]
        if compress:
            out=bytearray()
            for row in crop:
                rb=bytearray(); c=0; W=len(row)
                while c<W:
                    if row[c]==0:
                        k=0
                        while c<W and row[c]==0 and k<255: k+=1; c+=1
                        rb+=bytes([0,k])
                    else:
                        rb.append(row[c]); c+=1
                out+=struct.pack('<H',len(rb)+2)+rb
            blob=bytes(out); flags=3
        else:
            blob=crop.tobytes(); flags=1
        entries.append(struct.pack('<4HI4BII',x0,y0,x1-x0,y1-y0,flags,0,0,0,0,0,base+len(data)))
        data+=blob
    open(path,'wb').write(hdr+b''.join(entries)+data)
