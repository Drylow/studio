// Absolute-time authored states shared by the picture, foley and verification.
export const DURATION=63.6, OUTRO=60.8, FLOOR=1.08, HOME=5.9;
export const loads=[
 {start:0,end:18,count:48,contact:4,crushEnd:9.7,oilAt:5.25,liftAt:14.4,liftEnd:16.5},
 {start:18,end:38,count:96,contact:3.8,crushEnd:10.7,oilAt:4.65,liftAt:15.9,liftEnd:18.3},
 {start:38,end:60.8,count:192,contact:4.1,crushEnd:12,oilAt:4.75,liftAt:18.3,liftEnd:20.7}
];
export const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
export const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
export const rand=n=>{const x=Math.sin(n*127.1+311.7)*43758.5453;return x-Math.floor(x);};
export function stateAt(time,heights){
 const t=clamp(time,0,DURATION),outro=t>=OUTRO;
 const index=outro?2:t>=38?2:t>=18?1:0,load=loads[index],local=t-load.start;
 const arrival=smooth(local/1.25),withdraw=smooth((local-1.4)/.7);
 const leave=index<2?smooth((local-(load.end-load.start-1.05))/.85):0;
 const compression=smooth((local-load.contact)/(load.crushEnd-load.contact));
 const contactY=FLOOR+heights[index]+.05;
 let plate=HOME;
 if(local>=2.15&&local<load.contact)plate=HOME+(contactY-HOME)*smooth((local-2.15)/(load.contact-2.15));
 else if(local>=load.contact)plate=FLOOR+heights[index]*(1-.87*compression)+.05;
 const lift=smooth((local-load.liftAt)/(load.liftEnd-load.liftAt));
 plate=plate+(HOME-plate)*lift;
 const oil=smooth((local-load.oilAt)/(index===2?4:4.6));
 const flow=oil*(1-.45*smooth((local-load.liftEnd)/2));
 return {t,index,load,local,outro,arrival,withdraw,leave,compression,plate,lift,oil,flow,
  trayX:-6.7*(1-arrival)+leave*7.5,
  cameraClose:smooth((local-3)/2.1)*(1-.65*smooth((local-load.liftAt)/2)),
  runoff:smooth((local-load.crushEnd+.8)/2.7)*(1-smooth((local-load.liftEnd)/1.3))};
}
export function eventsFor(frames){
 const events=[];
 for(let j=0;j<loads.length;j++){
  const l=loads[j];
  events.push({kind:'tray',t:l.start+1.25,load:j,gain:.20});
  events.push({kind:'motor',t:l.start+2.15,end:l.start+l.crushEnd,load:j,gain:.22+j*.035});
  events.push({kind:'lift',t:l.start+l.liftAt,end:l.start+l.liftEnd,load:j,gain:.12});
  events.push({kind:'squeeze',t:l.start+l.contact+.23,end:l.start+l.crushEnd+.8,load:j,gain:.30+j*.055});
  events.push({kind:'oil',t:l.start+l.oilAt+.35,end:l.start+l.liftEnd+.45,load:j,gain:.17+j*.085});
  for(let i=0;i<18+j*8;i++)events.push({kind:'crunch',t:l.start+l.contact+.12+(l.crushEnd-l.contact-.5)*Math.pow((i+.2)/(18+j*8),.8),load:j,gain:(.24+j*.035)/Math.sqrt(1+j*.2),variant:i%3});
  for(let i=0;i<12+j*9;i++)events.push({kind:'drop',t:l.start+l.oilAt+2.25+i*.32+(rand(i+j*100)-.5)*.14,load:j,gain:.034+j*.008,variant:i%3});
 }
 events.push({kind:'celebrate',t:OUTRO+.17,load:2,gain:.035});
 return events.sort((a,b)=>a.t-b.t);
}
