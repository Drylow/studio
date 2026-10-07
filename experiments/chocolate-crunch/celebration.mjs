// Confetti catalog component: seeded angles, stagger and power2.out burst,
// adapted to the existing bitmap palette and an anchor projected from 3D.
// Absolute local time makes the celebration identical on every seek.
export function drawCelebration(ctx,{time,x,y}){
 const colors=['#ffe59a','#ef5867','#6e9852','#ffd09b'];
 for(let wave=0;wave<2;wave++)for(let i=0;i<14;i++){
  const age=time-(wave===0?.06:.72)-(i%4)*.015;
  if(age<0||age>1.06)continue;
  const progress=Math.min(1,age/.62),ease=1-(1-progress)**3;
  const px=Math.round(x+Math.cos(i*.83+wave*.7)*(13+(i%4)*5)*ease);
  const py=Math.round(y-(17+Math.sin(i*.61)*9)*ease+19*age*age);
  if(px<4||px>212||py<105||py>315)continue;
  ctx.fillStyle=colors[(i+wave)%colors.length];
  if(i%4===0){
   const size=age>.85?1:2;
   ctx.fillRect(px-size,py,1+2*size,1);
   ctx.fillRect(px,py-size,1,1+2*size);
  }else if(i%3===0){
   ctx.fillRect(px,py,1,3);ctx.fillRect(px+1,py+1,1,1);
  }else ctx.fillRect(px,py,age>.85?1:2,1+(i%2));
 }
}
