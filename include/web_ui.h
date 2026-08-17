#pragma once

const char INDEX_HTML[] = R"rawliteral(
<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sensors</title>
<style>
body{font-family:system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:20px;background:#f3f6f4;color:#17211d}
h2{margin:0 0 10px;font-size:1rem;color:#2a3630;text-align:center}.values{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.value,section{background:white;border:1px solid #d9e2dc;border-radius:8px;padding:16px;box-shadow:0 2px 8px #173b2412}.value{text-align:center}.value strong{display:block;font-size:2rem;margin-top:8px}.unit{color:#607068}section{margin-top:16px}canvas{width:100%;height:220px;display:block}@media(max-width:650px){.values{grid-template-columns:1fr}.value strong{font-size:1.7rem}}
</style></head><body>
<div class="values"><div class="value">CO2<strong id="co2">--</strong><span class="unit">ppm</span></div>
<div class="value">Temperature<strong id="temperature">--</strong><span class="unit">&deg;C</span></div>
<div class="value">Humidity<strong id="humidity">--</strong><span class="unit">%RH</span></div></div>
<section><h2>CO2</h2><canvas id="chart-co2" width="900" height="220"></canvas></section>
<section><h2>Temperature</h2><canvas id="chart-temperature" width="900" height="220"></canvas></section>
<section><h2>Humidity</h2><canvas id="chart-humidity" width="900" height="220"></canvas></section>
<script>
const series=[
  {id:'chart-co2',key:'co2',color:'#d65a4a',min:0,max:10000,unit:'ppm'},
  {id:'chart-temperature',key:'temperature',color:'#2878a8',min:20,max:35,unit:'°C',step:5},
  {id:'chart-humidity',key:'humidity',color:'#3b8c62',min:85,max:100,unit:'%RH',step:5}
];

function drawSeries(canvasId, history, cfg){
  const c=document.getElementById(canvasId),ctx=c.getContext('2d'),w=c.width,h=c.height;
  const left=78,right=12,top=12,bottom=30;
  const pw=w-left-right,ph=h-top-bottom;
  ctx.clearRect(0,0,w,h);
  if(!history.length){return;}

  const ticks=cfg.step
    ? Array.from({length:Math.floor((cfg.max-cfg.min)/cfg.step)+1},(_,i)=>cfg.max-(i*cfg.step))
    : Array.from({length:5},(_,i)=>cfg.max-((cfg.max-cfg.min)*i/4));

  ctx.strokeStyle='#d9e2dc';
  ctx.fillStyle='#607068';
  ctx.font='12px system-ui,sans-serif';
  ctx.textAlign='right';
  ticks.forEach((value)=>{
    const y=top+((cfg.max-value)*ph/(cfg.max-cfg.min));
    ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(left+pw,y);ctx.stroke();
    ctx.fillText(value.toFixed(cfg.key==='co2'?0:1),left-6,y+4);
  });

  ctx.save();
  ctx.translate(20, top + ph / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign='center';
  ctx.fillStyle='#607068';
  ctx.fillText(cfg.unit, 0, 0);
  ctx.restore();

  ctx.beginPath();
  ctx.moveTo(left,top);
  ctx.lineTo(left,top+ph);
  ctx.lineTo(left+pw,top+ph);
  ctx.strokeStyle='#93a39a';
  ctx.stroke();

  const values=history.map(v=>Number(v[cfg.key]));
  ctx.strokeStyle=cfg.color;
  ctx.lineWidth=2;
  ctx.beginPath();
  values.forEach((v,i)=>{
    const clamped=Math.max(cfg.min,Math.min(cfg.max,v));
    const px=left+i*pw/Math.max(1,values.length-1);
    const py=top+(cfg.max-clamped)*ph/(cfg.max-cfg.min);
    i?ctx.lineTo(px,py):ctx.moveTo(px,py);
  });
  ctx.stroke();

  ctx.fillStyle='#607068';
  ctx.textAlign='center';
  const secs=20*60;
  for(let i=0;i<=4;i++){
    const x=left+i*pw/4;
    const t=(secs-(secs*i/4))/60;
    ctx.fillText(i===4?'now':'-'+t.toFixed(0)+'m',x,h-8);
  }
}

function draw(history){series.forEach(s=>drawSeries(s.id,history,s));}
async function update(){try{let r=await fetch('/api/measurement'),d=await r.json();document.querySelector('#co2').textContent=d.co2;document.querySelector('#temperature').textContent=d.temperature.toFixed(1);document.querySelector('#humidity').textContent=d.humidity.toFixed(1);draw(d.history)}catch(e){console.log(e)}}update();setInterval(update,5000);
</script></body></html>
)rawliteral";
