(() => {
  const canvas = document.getElementById('nucleus');
  const scene = document.getElementById('nucleus-scene');
  const toggle = document.getElementById('motion-toggle');
  const ctx = canvas.getContext('2d');
  if (!ctx) { toggle.hidden = true; return; }
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reducedMotion.matches;
  let width = 0, height = 0, time = 0, lastFrame = 0, frame = null;
  let pointerX = 0, pointerY = 0, easedX = 0, easedY = 0;
  const particles = Array.from({length: 1050}, (_, i) => {
    const y = 1 - 2 * (i + .5) / 1050;
    const r = Math.sqrt(1 - y * y), phi = i * Math.PI * (3 - Math.sqrt(5));
    return {x: Math.cos(phi) * r, y, z: Math.sin(phi) * r, size: .6 + (i % 7) / 9};
  });
  function rotate(x,y,z,a,b) {
    const x1 = x*Math.cos(a) + z*Math.sin(a), z1 = -x*Math.sin(a) + z*Math.cos(a);
    return {x:x1, y:y*Math.cos(b)-z1*Math.sin(b), z:y*Math.sin(b)+z1*Math.cos(b)};
  }
  function draw() {
    ctx.clearRect(0,0,width,height);
    const centerX=width*.5, centerY=height*.47, scale=Math.min(width*.40,height*.39);
    const spin=time*.12 + easedX*.22, tilt=.32 + easedY*.2;
    function project(x,y,z) { const p=rotate(x,y,z,spin,tilt); const perspective=3.9/(3.9-p.z); return {x:centerX+p.x*scale*perspective,y:centerY+p.y*scale*perspective,z:p.z}; }
    const glow=ctx.createRadialGradient(centerX,centerY,0,centerX,centerY,scale*.76);
    glow.addColorStop(0,'rgba(190,247,220,.09)');glow.addColorStop(.4,'rgba(127,200,196,.05)');glow.addColorStop(1,'rgba(127,200,196,0)');
    ctx.fillStyle=glow;ctx.fillRect(0,0,width,height);
    const rings=[];
    for(let ring=0;ring<3;ring++){
      const points=[];
      for(let j=0;j<=160;j++){
        const angle=j/160*Math.PI*2;
        const p=rotate(Math.cos(angle)*1.02,Math.sin(angle)*1.02,0,ring*1.08+.35,ring*.75+.35);
        points.push(project(p.x,p.y,p.z));
      }
      rings.push(points);
    }
    function drawRings(front){
      rings.forEach((points,ring)=>{
        for(let j=1;j<points.length;j++){
          const p=points[j],prev=points[j-1]; if((p.z>=0)!==front)continue;
          ctx.beginPath();ctx.moveTo(prev.x,prev.y);ctx.lineTo(p.x,p.y);
          const alpha=front?.48:.14;
          ctx.strokeStyle=ring===1?`rgba(185,168,238,${alpha})`:`rgba(166,231,209,${alpha})`;
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
      const alpha=.15+depth*.73;
      ctx.fillStyle=p.index%5===0?`rgba(195,177,244,${alpha})`:`rgba(186,244,219,${alpha})`;
      ctx.beginPath();ctx.arc(p.x,p.y,p.size*(.6+depth*.6),0,Math.PI*2);ctx.fill();
    });
    drawRings(true);
    for(let ring=0;ring<3;ring++){
      const angle=time*(.38+ring*.09)+ring*2.1;
      const orbit=rotate(Math.cos(angle)*1.02,Math.sin(angle)*1.02,0,ring*1.08+.35,ring*.75+.35);
      const p=project(orbit.x,orbit.y,orbit.z);
      const light=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,15);
      light.addColorStop(0,ring===1?'rgba(200,184,255,.6)':'rgba(193,255,224,.6)');light.addColorStop(1,'rgba(193,255,224,0)');
      ctx.fillStyle=light;ctx.fillRect(p.x-15,p.y-15,30,30);ctx.fillStyle=ring===1?'#d1beff':'#d5ffe8';
      ctx.beginPath();ctx.arc(p.x,p.y,2.6,0,Math.PI*2);ctx.fill();
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
