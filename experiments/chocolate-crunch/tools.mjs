// Shared absolute-time mechanism poses for the physics bake and visible tools.
const levels=[
 {tool:'fork',count:1,length:3.3},
 {tool:'fork',count:4,length:3.2},
 {tool:'glove',count:4,length:3.4},
 {tool:'glove',count:8,length:3.6},
 {tool:'jackhammer',count:8,length:4.0},
 {tool:'jackhammer',count:16,length:4.2}
];
// Two quantities per tool; three rapid, freshly fractured salvos at each quantity.
export const trials=levels.flatMap(level=>Array.from({length:3},(_,round)=>({...level,round:round+1,rounds:3})));
export const smooth=v=>{v=Math.max(0,Math.min(1,v));return v*v*(3-2*v);};
export function toolState(tool,t){
 if(tool==='glove'){
  const compress=smooth((t-.12)/.56),punch=smooth((t-.86)/.13),retract=smooth((t-1.45)/.28);
  return {x:-3.1-.80*compress+3.1*punch-2.3*retract,y:3.82,z:0,compress,punch};
 }
 const motor=tool==='jackhammer'&&t>=.98&&t<3.0;
 return {x:0,y:motor?.085*Math.sin((t-.98)*Math.PI*44):0,z:0,motor};
}
