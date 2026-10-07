// One 216 x 384 pixel grid for the scene AND the type. No web fonts or blur.
export const PIXEL_WIDTH=216,PIXEL_HEIGHT=384;
const palette=['f1e7d6','203c2a','244c37','47714a','6e9852','a5bb76','ef5867','ff8291','b93751','f9af9f','f2f0c4','c79565','dfb27e','eacd9b','b4ac91','6b6c51','b7c2ba','def2e1','352922'];
const rgb=palette.map(hex=>[0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)));
const glyphs={
 '0':['01110','10001','10011','10101','11001','10001','01110'],
 '1':['00100','01100','00100','00100','00100','00100','01110'],
 '2':['01110','10001','00001','00010','00100','01000','11111'],
 '3':['11110','00001','00001','01110','00001','00001','11110'],
 '7':['11111','00001','00010','00100','01000','01000','01000'],
 A:['01110','10001','10001','11111','10001','10001','10001'],
 C:['01111','10000','10000','10000','10000','10000','01111'],
 E:['11111','10000','10000','11110','10000','10000','11111'],
 L:['10000','10000','10000','10000','10000','10000','11111'],
 M:['10001','11011','10101','10101','10001','10001','10001'],
 N:['10001','11001','11001','10101','10011','10011','10001'],
 O:['01110','10001','10001','10001','10001','10001','01110'],
 R:['11110','10001','10001','11110','10100','10010','10001'],
 S:['01111','10000','10000','01110','00001','00001','11110'],
 T:['11111','00100','00100','00100','00100','00100','00100'],
 U:['10001','10001','10001','10001','10001','10001','01110'],
 W:['10001','10001','10001','10101','10101','10101','01010'],
 ' ':['00000','00000','00000','00000','00000','00000','00000']
};
function text(ctx,value,x,y,scale,color='#203c2a'){
 const width=(value.length*6-1)*scale;
 x=Math.round(x-width/2);ctx.fillStyle=color;
 for(const letter of value){const rows=glyphs[letter];if(!rows)throw Error('Missing pixel glyph: '+letter);
  rows.forEach((row,j)=>[...row].forEach((cell,i)=>{if(cell==='1')ctx.fillRect(x+i*scale,y+j*scale,scale,scale);}));x+=6*scale;
 }
}
export function createPixelView(canvas){
 canvas.width=PIXEL_WIDTH;canvas.height=PIXEL_HEIGHT;
 const back=document.createElement('canvas');back.width=PIXEL_WIDTH;back.height=PIXEL_HEIGHT;
 const ctx=back.getContext('2d',{willReadFrequently:true,alpha:false});ctx.imageSmoothingEnabled=false;
 const display=canvas.getContext('2d',{willReadFrequently:true,alpha:false,desynchronized:false});display.imageSmoothingEnabled=false;
 const bayer=[-6,2,6,-2];
 return (source,count,index)=>{
  ctx.drawImage(source,0,0,PIXEL_WIDTH,PIXEL_HEIGHT);
  const frame=ctx.getImageData(0,0,PIXEL_WIDTH,PIXEL_HEIGHT),a=frame.data;
  for(let p=0;p<a.length;p+=4){
   const pixel=p/4,x=pixel%PIXEL_WIDTH,y=Math.floor(pixel/PIXEL_WIDTH),d=bayer[(y%2)*2+x%2];
   let best=0,distance=Infinity;
   for(let i=0;i<rgb.length;i++){const c=rgb[i],r=a[p]+d-c[0],g=a[p+1]+d-c[1],b=a[p+2]+d-c[2];const dist=r*r*2+g*g*3+b*b;
    if(dist<distance){best=i;distance=dist;}
   }
   a[p]=rgb[best][0];a[p+1]=rgb[best][1];a[p+2]=rgb[best][2];
  }
  ctx.putImageData(frame,0,0);
  text(ctx,'WATERMELON',108,28,1);
  text(ctx,count===1?'1 CUT':count+' CUTS',108,48,3);
  ['01','03','07'].forEach((label,i)=>{
   const x=72+i*36;text(ctx,label,x,350,1,i===index?'#203c2a':'#6b6c51');
   if(i===index){ctx.fillStyle='#203c2a';ctx.fillRect(x-8,363,16,1);}
  });
  // Publish one complete frame. Screenshot capture must never see the
  // intermediate palette image before all bitmap glyphs have been drawn.
  display.drawImage(back,0,0);
  display.getImageData(0,0,1,1);
  canvas.setAttribute('aria-label',`WATERMELON — ${count} ${count===1?'CUT':'CUTS'}`);
 };
}
