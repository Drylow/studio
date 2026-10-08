import {drawCelebration} from './celebration.mjs';
// One 216 x 384 pixel grid for the scene AND the type. No web fonts or blur.
export const PIXEL_WIDTH=216,PIXEL_HEIGHT=384;
export const palette=['f1e7d6','203c2a','244c37','47714a','6e9852','a5bb76','ef5867','ff8291','b93751','f9af9f','f2f0c4','c79565','dfb27e','eacd9b','b4ac91','6b6c51','b7c2ba','def2e1','352922','16201f','efb07a','ffd09b','ffe59a','704530','a46b46','563426','885438'];
palette.push('d88f28','f4ba45','fff0a6');
const rgb=palette.map(hex=>[0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)));
const glyphs={
 '0':['01110','10001','10011','10101','11001','10001','01110'],
 '1':['00100','01100','00100','00100','00100','00100','01110'],
 '2':['01110','10001','00001','00010','00100','01000','11111'],
 '3':['11110','00001','00001','01110','00001','00001','11110'],
 '4':['00010','00110','01010','10010','11111','00010','00010'],
 '5':['11111','10000','10000','11110','00001','00001','11110'],
 '9':['01110','10001','10001','01111','00001','00001','01110'],
 Y:['10001','10001','01010','00100','00100','00100','00100'],
 Q:['01110','10001','10001','10001','10101','10010','01101'],
 Z:['11111','00001','00010','00100','01000','10000','11111'],
 '6':['01110','10000','10000','11110','10001','10001','01110'],
 '8':['01110','10001','10001','01110','10001','10001','01110'],
 '7':['11111','00001','00010','00100','01000','01000','01000'],
 A:['01110','10001','10001','11111','10001','10001','10001'],
 B:['11110','10001','10001','11110','10001','10001','11110'],
 G:['01111','10000','10000','10111','10001','10001','01111'],
 K:['10001','10010','10100','11000','10100','10010','10001'],
 C:['01111','10000','10000','10000','10000','10000','01111'],
 D:['11110','10001','10001','10001','10001','10001','11110'],
 H:['10001','10001','10001','11111','10001','10001','10001'],
 E:['11111','10000','10000','11110','10000','10000','11111'],
 F:['11111','10000','10000','11110','10000','10000','10000'],
 L:['10000','10000','10000','10000','10000','10000','11111'],
 M:['10001','11011','10101','10101','10001','10001','10001'],
 N:['10001','11001','11001','10101','10011','10011','10001'],
 O:['01110','10001','10001','10001','10001','10001','01110'],
 R:['11110','10001','10001','11110','10100','10010','10001'],
 P:['11110','10001','10001','11110','10000','10000','10000'],
 V:['10001','10001','10001','10001','10001','01010','00100'],
 I:['01110','00100','00100','00100','00100','00100','01110'],
 J:['00111','00010','00010','00010','10010','10010','01100'],
 X:['10001','10001','01010','00100','01010','10001','10001'],
 S:['01111','10000','10000','01110','00001','00001','11110'],
 T:['11111','00100','00100','00100','00100','00100','00100'],
 U:['10001','10001','10001','10001','10001','10001','01110'],
 W:['10001','10001','10001','10101','10101','10101','01010'],
 '!':['00100','00100','00100','00100','00100','00000','00100'],
 ' ':['00000','00000','00000','00000','00000','00000','00000']
};
function text(ctx,value,x,y,scale,color='#203c2a'){
 const width=(value.length*6-1)*scale;
 x=Math.round(x-width/2);ctx.fillStyle=color;
 for(const letter of value){const rows=glyphs[letter];if(!rows)throw Error('Missing pixel glyph: '+letter);
  rows.forEach((row,j)=>[...row].forEach((cell,i)=>{if(cell==='1')ctx.fillRect(x+i*scale,y+j*scale,scale,scale);}));x+=6*scale;
 }
}
function toolIcon(ctx,tool,x,y){
 const patterns={
  machete:['       MMMMMMMM','      MMMMMMMMM',' KKKKMMMMMMMMM ',' KKKKMMMMMMMM  ','     MMMMM     '],
  saw:['    M M M    ','  MMMMMMMMM  ',' MMMMMMMMMMM ',' MMMMMKMMMMM ',' M MMKKKMM M ',' MMMMMKMMMMM ',' MMMMMMMMMMM ','  MMMMMMMMM  ','    M M M    '],
  pistol:[' KKKKKKKKKKKKK ',' KKKKKKKKKKKKK ',' KKKKKKKKKKKKK ',' KKKKK K       ','  KKK  K       ','  KKKKK        ','  KKK          ','  KKK          ']
 };
 const colors={K:'#16201f',M:'#b7c2ba'};
 patterns[tool].forEach((row,j)=>[...row].forEach((c,i)=>{if(colors[c]){ctx.fillStyle=colors[c];ctx.fillRect(x+i,y+j,1,1);}}));
}
function watermelonIcon(ctx,x,y){
 const rows=['  GGGGGGGGGG  ',' GWRRRRRRRRWG ',' GWRRSRRSRRWG ',' GWRRRRRRRRWG ','  GWRRSRRRWG  ','  GWRRRRRRWG  ','   GWRRRRWG   ','    GWWWWG    ','     GGGG     '];
 const colors={G:'#244c37',W:'#f2f0c4',R:'#ef5867',S:'#352922'};
 rows.forEach((row,j)=>[...row].forEach((cell,i)=>{if(colors[cell]){ctx.fillStyle=colors[cell];ctx.fillRect(x+i,y+j,1,1);}}));
}
// Future tools are visible from frame zero; completion and selection are explicit.
function toolProgress(ctx,tool,outro){
 const tools=['fork','glove','jackhammer'],labels=['FORK','GLOVE','HAMMER'];
 const sprites=[
  [' M M M M ',' M M M M ',' M M M M ',' MMMMMMM ',' MMMMMMM ','   MMM   ','   MMM   ','   MMM   ','   MMM   ','   MMM   ','   MMM   ','   GGG   ','   GGG   '],
  ['   RRRRRRR   ','  RRRRRRRRR  ',' RRRRRRRRRRR ',' RRRRRRRRRRR ',' RRRRRRRRRRR ',' RRRRRRRRRRR ','  RRRRRRDRRR ','   RRRRRDRR  ','    RRRRRR   ','    IIIIII   ','    IIIIII   ',' M MMMMM M   ','  M M M M    '],
  ['     M      ','    MMM     ','     M      ','     M      ','   YYYYY    ','   YYYYY    ',' DYYYYYYYD  ',' DDYYYYYDD  ','   YYYYY    ','   YDDDY    ','   YYYYY    ','   YDDDY    ','    YYY     ']
 ];
 const colors={M:'#b7c2ba',G:'#244c37',R:'#ef5867',D:'#203c2a',I:'#def2e1',Y:'#ffe59a'};
 const active=tools.indexOf(tool);
 tools.forEach((name,i)=>{
  const cx=48+i*60,x=cx-21,y=340,w=42,h=36,done=outro||i<active,selected=!outro&&i===active;
  ctx.fillStyle='#b4ac91';ctx.fillRect(x+2,y+2,w,h);
  ctx.fillStyle=selected?'#203c2a':done?'#47714a':'#b4ac91';ctx.fillRect(x,y,w,h);
  ctx.fillStyle='#f1e7d6';ctx.fillRect(x+2,y+2,w-4,h-4);
  const sprite=sprites[i],sx=Math.round(cx-sprite[0].length*.75),sy=y+4;
  // Rounded cell boundaries keep the smaller sprites on the integer pixel grid.
  sprite.forEach((row,j)=>[...row].forEach((c,k)=>{if(colors[c]){
   ctx.fillStyle=colors[c];ctx.fillRect(sx+Math.round(k*1.5),sy+Math.round(j*1.5),Math.round((k+1)*1.5)-Math.round(k*1.5),Math.round((j+1)*1.5)-Math.round(j*1.5));
  }}));
  text(ctx,labels[i],cx,y+26,1,selected?'#203c2a':'#6b6c51');
  if(done){
   ctx.fillStyle='#47714a';ctx.fillRect(x+31,y+5,2,2);ctx.fillRect(x+33,y+7,2,2);ctx.fillRect(x+35,y+3,2,4);
  }
  if(selected){
   ctx.fillStyle='#203c2a';ctx.fillRect(cx-3,y-4,6,1);ctx.fillRect(cx-2,y-3,4,1);ctx.fillRect(cx-1,y-2,2,1);
  }
  if(i<2){
   ctx.fillStyle='#b4ac91';ctx.fillRect(cx+26,y+14,2,7);ctx.fillRect(cx+28,y+15,2,5);ctx.fillRect(cx+30,y+16,1,3);
  }
 });
}
function pressProgress(ctx,index,outro,pressure){
 text(ctx,outro?'CHEF APPROVED':'PRESSURE',108,329,1);
 ctx.fillStyle='#b4ac91';ctx.fillRect(55,339,106,3);
 ctx.fillStyle='#47714a';ctx.fillRect(55,339,Math.round(106*pressure),3);
 [48,96,192].forEach((n,i)=>{
  const x=28+i*60,y=349,done=outro||i<index,active=!outro&&i===index;
  ctx.fillStyle=active?'#203c2a':done?'#47714a':'#b4ac91';ctx.fillRect(x,y,40,27);
  ctx.fillStyle='#f1e7d6';ctx.fillRect(x+2,y+2,36,23);
  for(let j=0;j<4;j++){ctx.fillStyle=j%2?'#ffd09b':'#ffe59a';ctx.fillRect(x+11+j*4,y+4-(j%2),3,10+(j%2));ctx.fillStyle='#dfb27e';ctx.fillRect(x+11+j*4,y+12,1,2);}
  text(ctx,String(n),x+20,y+17,1,active?'#203c2a':'#6b6c51');
  if(done){ctx.fillStyle='#47714a';ctx.fillRect(x+31,y+5,2,2);ctx.fillRect(x+33,y+7,2,2);ctx.fillRect(x+35,y+3,2,4);}
 });
}
export function createPixelView(canvas){
 canvas.width=PIXEL_WIDTH;canvas.height=PIXEL_HEIGHT;
 const back=document.createElement('canvas');back.width=PIXEL_WIDTH;back.height=PIXEL_HEIGHT;
 const ctx=back.getContext('2d',{willReadFrequently:true,alpha:false});ctx.imageSmoothingEnabled=false;
 const display=canvas.getContext('2d',{willReadFrequently:true,alpha:false,desynchronized:false});display.imageSmoothingEnabled=false;
 const bayer=[-6,2,6,-2];
 // Cache exact nearest-palette results, including the four dither offsets.
 // Every repeat color avoids searching all palette colors again, with no change
 // to pixel values between preview and export.
 const nearestCache=new Map();
 return (source,count,index,outro=false,celebration=null,tool='press',state={compression:0})=>{
  ctx.drawImage(source,0,0,PIXEL_WIDTH,PIXEL_HEIGHT);
  const frame=ctx.getImageData(0,0,PIXEL_WIDTH,PIXEL_HEIGHT),a=frame.data;
  for(let p=0;p<a.length;p+=4){
   const pixel=p/4,x=pixel%PIXEL_WIDTH,y=Math.floor(pixel/PIXEL_WIDTH),pattern=(y%2)*2+x%2,d=bayer[pattern];
   const cacheKey=((a[p]<<16)|(a[p+1]<<8)|a[p+2])*4+pattern;
   let best=nearestCache.get(cacheKey);
   if(best===undefined){
    best=0;let distance=Infinity;
    for(let i=0;i<rgb.length;i++){const c=rgb[i],r=a[p]+d-c[0],g=a[p+1]+d-c[1],b=a[p+2]+d-c[2];const dist=r*r*2+g*g*3+b*b;
     if(dist<distance){best=i;distance=dist;}
    }
    nearestCache.set(cacheKey,best);
   }
   a[p]=rgb[best][0];a[p+1]=rgb[best][1];a[p+2]=rgb[best][2];
  }
  ctx.putImageData(frame,0,0);
  if(celebration)drawCelebration(ctx,celebration);
  // Keep the title field readable even when a thrown blade enters above it.
  ctx.fillStyle='#f1e7d6';ctx.fillRect(0,0,PIXEL_WIDTH,93);
  for(let i=0;i<4;i++){ctx.fillStyle=i%2?'#ffd09b':'#ffe59a';ctx.fillRect(80+i*3,25-(i%2)*2,2,11+(i%2)*2);}
  ctx.fillStyle='#ef5867';ctx.fillRect(79,32,14,6);
  text(ctx,'FRIES',115,28,1);
  text(ctx,outro?'SQUEEZED!':`${count} FRIES`,108,48,3);
  const label='HYDRAULIC PRESS';
  ctx.fillStyle='#244c37';ctx.fillRect(47,75,12,2);ctx.fillRect(47,75,2,12);ctx.fillRect(57,75,2,12);
  ctx.fillStyle='#b7c2ba';ctx.fillRect(52,77,2,5);ctx.fillRect(49,81,8,2);
  text(ctx,label,118,80,1);
  ctx.fillStyle='#f1e7d6';ctx.fillRect(0,328,PIXEL_WIDTH,56);
  pressProgress(ctx,index,outro,state.compression);
  // Publish one complete frame. Screenshot capture must never see the
  // intermediate palette image before all bitmap glyphs have been drawn.
  display.drawImage(back,0,0);
  display.getImageData(0,0,1,1);
  canvas.setAttribute('aria-label',`FRIES — ${label} — ${outro?'SQUEEZED':count+' FRIES'}`);
 };
}
