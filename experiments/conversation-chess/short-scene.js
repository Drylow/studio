// Portrait companion to scene.js: same official icons and pawn silhouette.
window.ChessShort = (() => {
  const canvas = document.querySelector('canvas');
  const ctx = canvas.getContext('2d', {alpha:true});
  const schema = window.ConversationRatingSchema;
  const icons = {};
  const clamp = v => Math.max(0, Math.min(1, v));
  function text(value,x,y,size,color='#eeeae2',weight=700) {
    ctx.font=`${weight} ${size}px Arial`; ctx.textAlign='left';
    ctx.textBaseline='alphabetic'; ctx.fillStyle=color; ctx.fillText(value,x,y);
  }
  function pawn(x,y,height,white) {
    ctx.save();ctx.translate(x-height*.34,y);ctx.scale(height/100,height/100);
    ctx.beginPath();ctx.arc(34,17,14,0,Math.PI*2);
    ctx.moveTo(19,36);ctx.lineTo(49,36);ctx.lineTo(51,44);ctx.lineTo(17,44);ctx.closePath();
    ctx.moveTo(22,45);ctx.bezierCurveTo(24,60,19,73,12,82);ctx.lineTo(56,82);
    ctx.bezierCurveTo(49,73,44,60,46,45);ctx.closePath();
    ctx.moveTo(10,83);ctx.lineTo(58,83);ctx.lineTo(62,94);ctx.lineTo(6,94);ctx.closePath();
    ctx.fillStyle=white?'#fff':'#403c38';ctx.fill();
    ctx.strokeStyle=white?'#aaa69e':'#b8b2a8';ctx.lineWidth=2;ctx.stroke();ctx.restore();
  }
  function icon(id,x,y,size,angle=-8) {
    const im=icons[id];if(!im)throw new Error('Missing official icon '+id);
    const width=size*im.width/Math.max(im.width,im.height),height=size*im.height/Math.max(im.width,im.height);
    ctx.save();ctx.translate(x+size/2,y+size/2);ctx.rotate(angle*Math.PI/180);
    ctx.drawImage(im,-width/2,-height/2,width,height);ctx.restore();
  }
  function wrap(value,x,y,width,size,color,leading=48) {
    ctx.font=`700 ${size}px Arial`;let row='',line=0;
    for(const word of value.split(' ')) {
      const candidate=row?row+' '+word:word;
      if(ctx.measureText(candidate).width>width&&row){text(row,x,y+line*leading,size,color);row=word;line++;}
      else row=candidate;
    }
    if(row)text(row,x,y+line*leading,size,color);
    if(line>3)throw new Error('Short commentary exceeds four lines');
  }
  function frame(o) {
    ctx.clearRect(0,0,1080,1920);
    text(o.series.toUpperCase(),68,105,29,'#a49e94');
    o.hook.forEach((s,i)=>text(s,68,201+i*83,76));
    ctx.fillStyle='#37332f';ctx.fillRect(68,311,862,2);
    pawn(87,333,33,true);text(o.sides.white,115,361,27);
    text('VS',442,361,22,'#77716a');
    pawn(502,333,33,false);text(o.sides.black,529,361,27);
    // The scene occupies x68,y392,940x1040. Leave the right platform rail clear.
    const old=o.previous_score??o.score;
    const progress=o.kind==='analysis'?clamp((o.time-.25)/.5):1;
    const score=old+(o.score-old)*progress;
    const white=clamp(.5+Math.tanh(score/4)*.42);
    ctx.fillStyle='#403c38';ctx.fillRect(22,540,26,728);
    ctx.fillStyle='#fff';ctx.fillRect(22,540+728*(1-white),26,728*white);
    ctx.strokeStyle='#8d867d';ctx.lineWidth=1;ctx.strokeRect(22,540,26,728);
    text(score>0?'+'+score.toFixed(1):score.toFixed(1),17,1315,22,'#b6aea3');
    if(o.kind==='analysis') {
      const a=o.analysis,category=schema.categories.find(c=>c.id===a.rating);
      const entry=1-Math.pow(1-clamp(o.time/.35),3);
      ctx.save();ctx.translate(0,14*(1-entry));ctx.globalAlpha=entry;
      pawn(131,1476,230,a.speaker==='white');
      icon(a.rating,240,1470,72,a.speaker==='white'?-8:8);
      text(o.sides[a.speaker]+' · '+category.label+' Move',335,1523,33,category.color);
      ctx.fillStyle='#f2eee6';ctx.beginPath();ctx.roundRect(238,1553,690,209,16);ctx.fill();
      ctx.beginPath();ctx.moveTo(238,1581);ctx.lineTo(207,1600);ctx.lineTo(238,1615);ctx.closePath();ctx.fill();
      const visible=a.comment.slice(0,Math.floor(Math.max(0,o.time-schema.bubble_delay_seconds)*schema.typewriter_cps));
      wrap(visible,271,1600,620,34,'#27231f',45);ctx.restore();
    } else if(o.kind==='outro') {
      icon('blunder',68,1500,70,9);icon('brilliant',68,1600,70,-9);
      text(o.recap[0],175,1550,36);text(o.recap[1],175,1650,36);
    } else {
      text('THE MOVE',68,1509,25,'#888178');
      wrap(o.context,68,1577,827,44,'#eeeae2',57);
    }
    text('ANALYSED LIKE CHESS',68,1824,22,'#787168');
    if(o.kind==='outro') {
      const alpha=clamp((o.time-(o.seconds-.4))/.4);
      ctx.globalCompositeOperation='destination-out';ctx.fillStyle=`rgba(0,0,0,${alpha})`;
      ctx.fillRect(0,0,1080,1920);ctx.globalCompositeOperation='source-over';
    }
    return canvas.toDataURL('image/png');
  }
  async function init(iconUrls) {
    canvas.width=1080;canvas.height=1920;
    await Promise.all(Object.entries(iconUrls).map(async([id,url])=>{
      const im=new Image();im.src=url;await im.decode();icons[id]=im;
    }));
  }
  return {init,frame};
})();
