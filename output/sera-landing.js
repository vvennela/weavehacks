(() => {
  const dropdowns = [...document.querySelectorAll('.nav-dropdown')];
  dropdowns.forEach(menu => {
    menu.addEventListener('toggle', () => { if(menu.open) dropdowns.forEach(other => { if(other !== menu) other.open=false; }); });
    menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {menu.open=false;}));
  });
  document.addEventListener('click', event => { if(!event.target.closest('.nav-dropdown')) dropdowns.forEach(menu => {menu.open=false;}); });
  document.addEventListener('keydown', event => { if(event.key==='Escape') dropdowns.forEach(menu => {if(menu.open){menu.open=false;menu.querySelector('summary').focus();}}); });
  const specialists = {
    quantization: {kicker:'THE MEMORY SPECIALIST',title:'Smaller footprint.\nQuality still comes first.',description:'Explore weight and KV-cache precision to reduce memory demand. Every candidate still has to clear the quality and performance gates.',levers:['Weight precision','KV-cache precision'],principle:'If memory isn’t the bottleneck, the specialist can say so. A useful answer doesn’t always require a change.'},
    batching: {kicker:'THE SCHEDULING SPECIALIST',title:'The right work.\nAt the right time.',description:'Explore concurrency, token budgets, and chunked prefill to balance throughput with latency for the workload at hand.',levers:['Concurrent sequences','Batched tokens','Chunked prefill'],principle:'A larger batch is not always a better batch. The specialist checks whether scheduling is actually the constraint.'},
    parallelism: {kicker:'THE DEVICE SPECIALIST',title:'More devices?\nOnly when they help.',description:'Explore tensor and pipeline parallelism to distribute model work. Account for device availability and the goal of freeing a GPU.',levers:['Tensor parallelism','Pipeline parallelism'],principle:'The fastest multi-device run may be the wrong choice for consolidation. A viable single-device configuration answers a different question.'}
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
    return {x: Math.cos(phi) * r*shell, y:y*shell, z: Math.sin(phi) * r*shell, size: .45 + (i % 7) / 11};
  });
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
    glow.addColorStop(0,'rgba(40,101,85,.08)');glow.addColorStop(.4,'rgba(121,88,137,.04)');glow.addColorStop(1,'rgba(121,88,137,0)');
    ctx.fillStyle=glow;ctx.fillRect(0,0,width,height);
    // A loose halo of independently moving points surrounds the denser core.
    for(let i=0;i<160;i++){
      const angle=i*2.39996+time*(.025+(i%5)*.007), radius=.65+(i%23)/38;
      const halo=rotate(Math.cos(angle)*radius,Math.sin(angle)*radius,Math.sin(i*1.17)*.42,.3,Math.sin(i)*.5);
      const p=project(halo.x,halo.y,halo.z);
      ctx.fillStyle=i%3===0?'rgba(121,88,137,.24)':'rgba(40,101,85,.24)';
      ctx.beginPath();ctx.arc(p.x,p.y,.55+(i%4)*.23,0,Math.PI*2);ctx.fill();
    }
    function orbitAt(angle,ring){return rotate(Math.cos(angle)*1.02,Math.sin(angle)*1.02,0,ring*1.08+.35+Math.sin(time*.12)*.12,ring*.75+.35+Math.cos(time*.1+ring)*.09);}
    const rings=[];
    for(let ring=0;ring<3;ring++){
      const points=[];
      for(let j=0;j<=160;j++){
        const angle=j/160*Math.PI*2;
        const p=orbitAt(angle,ring);
        points.push(project(p.x,p.y,p.z));
      }
      rings.push(points);
    }
    function drawRings(front){
      rings.forEach((points,ring)=>{
        for(let j=1;j<points.length;j++){
          const p=points[j],prev=points[j-1]; if((p.z>=0)!==front)continue;
          ctx.beginPath();ctx.moveTo(prev.x,prev.y);ctx.lineTo(p.x,p.y);
          const alpha=front?.58:.20;
          ctx.strokeStyle=ring===1?`rgba(121,88,137,${alpha})`:`rgba(40,101,85,${alpha})`;
          ctx.lineWidth=front?.85:.65;ctx.stroke();
        }
      });
    }
    drawRings(false);
    const projected=particles.map((p,i)=>{
      const breath=1+Math.sin(time*.8+i*.013)*.025;
      const q=rotate(p.x*.42*breath,p.y*.42*breath,p.z*.42*breath,time*.08,-.18);
      return {...project(q.x,q.y,q.z),size:p.size,index:i};
    }).sort((a,b)=>a.z-b.z);
    projected.forEach(p=>{
      const depth=(p.z+.48)/.96;
      const alpha=.12+depth*.65;
      ctx.fillStyle=p.index%5===0?`rgba(121,88,137,${alpha})`:`rgba(40,101,85,${alpha})`;
      ctx.beginPath();ctx.arc(p.x,p.y,p.size*(.6+depth*.6),0,Math.PI*2);ctx.fill();
    });
    drawRings(true);
    for(let ring=0;ring<3;ring++) for(let satellite=0;satellite<3;satellite++){
      const angle=time*(.46+ring*.13)+ring*2.1+satellite*Math.PI*2/3;
      for(let trail=22;trail>0;trail--){
        const o=orbitAt(angle-trail*.018,ring),p=project(o.x,o.y,o.z);
        const alpha=(1-trail/23)*.4;
        ctx.fillStyle=ring===1?`rgba(121,88,137,${alpha})`:`rgba(40,101,85,${alpha})`;
        ctx.beginPath();ctx.arc(p.x,p.y,(1-trail/25)*1.9,0,Math.PI*2);ctx.fill();
      }
      const orbit=orbitAt(angle,ring);
      const p=project(orbit.x,orbit.y,orbit.z);
      const light=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,15);
      light.addColorStop(0,ring===1?'rgba(121,88,137,.24)':'rgba(40,101,85,.24)');light.addColorStop(1,'rgba(40,101,85,0)');
      ctx.fillStyle=light;ctx.fillRect(p.x-15,p.y-15,30,30);ctx.fillStyle=ring===1?'#795889':'#286555';
      ctx.beginPath();ctx.arc(p.x,p.y,2.6,0,Math.PI*2);ctx.fill();
      for(let mote=0;mote<4;mote++){
        const a=time*1.4+mote*Math.PI/2+ring, radius=5+mote*.6;
        ctx.fillStyle=ring===1?'rgba(121,88,137,.55)':'rgba(40,101,85,.55)';
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
