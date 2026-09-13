(() => {
  const specialists = {
    memory_context: {kicker:'THE MEMORY SPECIALIST',title:'Smaller footprint.\nQuality still comes first.',description:'Inspect memory use and context demand. Propose supported cache and context settings; keep the quality and performance gates fixed.',levers:['KV-cache precision','Context limits','Memory budget'],principle:'If memory is not the bottleneck, the investigator can say so. A useful answer does not always require a change.'},
    scheduling: {kicker:'THE SCHEDULING SPECIALIST',title:'The right work.\nAt the right time.',description:'Read load metrics and slow requests. Test batching, prefix caching, and graph execution against the measured workload.',levers:['Batched tokens','Prefix caching','Graph execution'],principle:'A proposal is a prediction. Only a measured trial establishes whether it helps.'},
    output_quality: {kicker:'THE QUALITY SPECIALIST',title:'Faster responses.\nAnswers that still pass.',description:'Inspect recorded outputs and failed answer checks. Diagnose a failed trial and propose a legal next step without lowering the quality floor.',levers:['Output inspection','Failure diagnosis','Fixed quality gate'],principle:'The evaluator grades actual model outputs on eight exact-answer JSON tasks. Passing these tasks is not a general model-quality score.'}
  };
  document.querySelectorAll('[data-specialist]').forEach(button => button.addEventListener('click', () => {
    const data=specialists[button.dataset.specialist];
    document.querySelectorAll('[data-specialist]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));
    ['kicker','title','description','principle'].forEach(key=>{document.getElementById('specialist-'+key).textContent=data[key];});
    document.getElementById('specialist-levers').replaceChildren(...data.levers.map(label=>{const span=document.createElement('span');span.textContent=label;return span;}));
  }));
  const canvas = document.getElementById('nucleus');
  const scene = document.getElementById('nucleus-scene');
  const toggle = document.getElementById('motion-toggle');
  if (!canvas || !scene || !toggle) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) { toggle.hidden = true; return; }
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reducedMotion.matches;
  let width = 0, height = 0, time = 0, lastFrame = 0, frame = null;
  let pointerX = 0, pointerY = 0, easedX = 0, easedY = 0;
  const particleCount = matchMedia('(max-width: 700px)').matches ? 1600 : 2800;
  const particles = Array.from({length: particleCount}, (_, i) => {
    const y = 1 - 2 * (i + .5) / particleCount;
    const r = Math.sqrt(1 - y * y), phi = i * Math.PI * (3 - Math.sqrt(5));
    const shell=i%4===0?.68:1;
    return {x: Math.cos(phi) * r*shell, y:y*shell, z: Math.sin(phi) * r*shell, size: .65 + (i % 7) / 9};
  });
  // Stable samples flow along three tubular orbits without flickering between frames.
  const ribbonCount = particleCount === 1600 ? 1100 : 2400;
  const fract = value => value - Math.floor(value);
  const ribbonParticles = Array.from({length: ribbonCount}, (_, i) => ({
    angle: i / ribbonCount * Math.PI * 2,
    cross: fract(i * .61803398875) * Math.PI * 2,
    radius: Math.sqrt(fract((i + 1) * .754877666)) * .125,
    size: 1.05 + fract(i * .569840291) * 1.0,
    color: i % 10 < 5 ? 0 : i % 10 < 8 ? 1 : i % 10 === 8 ? 2 : 3
  }));
  const ribbonColors = ['24,99,65', '79,116,70', '24,106,135', '151,105,22'];
  const ribbonPaints = ribbonColors.map(color => Array.from({length: 12}, (_, depth) => `rgba(${color},${.32 + depth * .06})`));
  function rotate(x,y,z,a,b) {
    const x1 = x*Math.cos(a) + z*Math.sin(a), z1 = -x*Math.sin(a) + z*Math.cos(a);
    return {x:x1, y:y*Math.cos(b)-z1*Math.sin(b), z:y*Math.sin(b)+z1*Math.cos(b)};
  }
  function draw() {
    ctx.clearRect(0,0,width,height);
    const centerX=width*.5, centerY=height*.47, scale=Math.min(width*.36,height*.36);
    const spin=time*.12 + easedX*.22, tilt=.32 + easedY*.2;
    function project(x,y,z) { const p=rotate(x,y,z,spin,tilt); const perspective=3.9/(3.9-p.z); return {x:centerX+p.x*scale*perspective,y:centerY+p.y*scale*perspective,z:p.z}; }
    const glow=ctx.createRadialGradient(centerX,centerY,0,centerX,centerY,scale*.76);
    glow.addColorStop(0,'rgba(40,101,85,.08)');glow.addColorStop(.4,'rgba(79,116,70,.04)');glow.addColorStop(1,'rgba(79,116,70,0)');
    ctx.fillStyle=glow;ctx.fillRect(0,0,width,height);
    // A loose halo of independently moving points surrounds the denser core.
    for(let i=0;i<160;i++){
      const angle=i*2.39996+time*(.025+(i%5)*.007), radius=.65+(i%23)/38;
      const halo=rotate(Math.cos(angle)*radius,Math.sin(angle)*radius,Math.sin(i*1.17)*.42,.3,Math.sin(i)*.5);
      const p=project(halo.x,halo.y,halo.z);
      ctx.fillStyle=i%3===0?'rgba(79,116,70,.42)':'rgba(24,99,65,.42)';
      ctx.beginPath();ctx.arc(p.x,p.y,.55+(i%4)*.23,0,Math.PI*2);ctx.fill();
    }
    function orbitAt(angle,ring){return rotate(Math.cos(angle)*1.02,Math.sin(angle)*1.02,0,ring*1.08+.35+Math.sin(time*.12)*.12,ring*.75+.35+Math.cos(time*.1+ring)*.09);}
    const ribbonPoints=[];
    for(let ring=0;ring<3;ring++){
      const orientation=ring*1.08+.35+Math.sin(time*.12)*.12;
      const inclination=ring*.75+.35+Math.cos(time*.1+ring)*.09;
      for(const mote of ribbonParticles){
        const angle=mote.angle+time*(.13+ring*.045);
        const twist=mote.cross+angle*2+time*.16;
        const bandRadius=1.02+Math.cos(twist)*mote.radius;
        const p=rotate(Math.cos(angle)*bandRadius,Math.sin(angle)*bandRadius,Math.sin(twist)*mote.radius,orientation,inclination);
        const point=project(p.x,p.y,p.z);
        ribbonPoints.push({...point,size:mote.size,color:mote.color});
      }
    }
    function drawRibbons(front){
      for(const p of ribbonPoints){
        if((p.z>=0)!==front)continue;
        const depth=Math.max(0,Math.min(11,Math.floor((p.z+1.2)/2.4*12)));
        const size=p.size*(.85+depth*.04);
        ctx.fillStyle=ribbonPaints[p.color][depth];
        ctx.fillRect(p.x-size/2,p.y-size/2,size,size);
      }
    }
    drawRibbons(false);
    const projected=particles.map((p,i)=>{
      const breath=1+Math.sin(time*.8+i*.013)*.025;
      const q=rotate(p.x*.42*breath,p.y*.42*breath,p.z*.42*breath,time*.08,-.18);
      return {...project(q.x,q.y,q.z),size:p.size,index:i};
    }).sort((a,b)=>a.z-b.z);
    projected.forEach(p=>{
      const depth=(p.z+.48)/.96;
      const alpha=.24+depth*.68;
      ctx.fillStyle=p.index%5===0?`rgba(79,116,70,${alpha})`:`rgba(40,101,85,${alpha})`;
      ctx.beginPath();ctx.arc(p.x,p.y,p.size*(.6+depth*.6),0,Math.PI*2);ctx.fill();
    });
    drawRibbons(true);
    for(let ring=0;ring<3;ring++) for(let satellite=0;satellite<3;satellite++){
      const angle=time*(.46+ring*.13)+ring*2.1+satellite*Math.PI*2/3;
      for(let trail=22;trail>0;trail--){
        const o=orbitAt(angle-trail*.018,ring),p=project(o.x,o.y,o.z);
        const alpha=(1-trail/23)*.4;
        ctx.fillStyle=ring===1?`rgba(79,116,70,${alpha})`:`rgba(40,101,85,${alpha})`;
        ctx.beginPath();ctx.arc(p.x,p.y,(1-trail/25)*1.9,0,Math.PI*2);ctx.fill();
      }
      const orbit=orbitAt(angle,ring);
      const p=project(orbit.x,orbit.y,orbit.z);
      const light=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,15);
      light.addColorStop(0,ring===1?'rgba(79,116,70,.42)':'rgba(24,99,65,.42)');light.addColorStop(1,'rgba(40,101,85,0)');
      ctx.fillStyle=light;ctx.fillRect(p.x-15,p.y-15,30,30);ctx.fillStyle=ring===1?'#57775e':'#286555';
      ctx.beginPath();ctx.arc(p.x,p.y,2.6,0,Math.PI*2);ctx.fill();
      for(let mote=0;mote<4;mote++){
        const a=time*1.4+mote*Math.PI/2+ring, radius=5+mote*.6;
        ctx.fillStyle=ring===1?'rgba(79,116,70,.55)':'rgba(40,101,85,.55)';
        ctx.beginPath();ctx.arc(p.x+Math.cos(a)*radius,p.y+Math.sin(a)*radius*.6,.8,0,Math.PI*2);ctx.fill();
      }
    }
  }
  function tick(timestamp){
    frame=null;
    if(paused||document.hidden)return;
    if(lastFrame)time+=Math.min((timestamp-lastFrame)/1000,.05);
    lastFrame=timestamp;easedX+=(pointerX-easedX)*.025;easedY+=(pointerY-easedY)*.025;
    draw();frame=requestAnimationFrame(tick);
  }
  function sync(){
    toggle.setAttribute('aria-pressed',String(paused));
    toggle.setAttribute('aria-label',paused?'Play nucleus animation':'Pause nucleus animation');
    toggle.innerHTML=paused?'Play motion <span aria-hidden="true">▷</span>':'Pause motion <span aria-hidden="true">Ⅱ</span>';
    if(frame!==null)cancelAnimationFrame(frame);frame=null;lastFrame=0;
    draw();if(!paused&&!document.hidden)frame=requestAnimationFrame(tick);
  }
  function resize(){
    const rect=scene.getBoundingClientRect();width=rect.width;height=rect.height;
    const ratio=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    ctx.setTransform(ratio,0,0,ratio,0,0);draw();
  }
  scene.addEventListener('pointermove',event=>{if(paused)return;const rect=scene.getBoundingClientRect();pointerX=(event.clientX-rect.left)/rect.width-.5;pointerY=(event.clientY-rect.top)/rect.height-.5});
  scene.addEventListener('pointerleave',()=>{pointerX=0;pointerY=0});
  toggle.addEventListener('click',()=>{paused=!paused;sync()});
  reducedMotion.addEventListener('change',()=>{paused=reducedMotion.matches;sync()});
  document.addEventListener('visibilitychange',sync);
  new ResizeObserver(resize).observe(scene);resize();sync();
})();
