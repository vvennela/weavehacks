(() => {
  const root=document.documentElement;
  let theme='light';
  try { theme=localStorage.getItem('sera-theme')==='dark'?'dark':'light'; } catch {}
  function apply(){
    root.dataset.theme=theme;
    const meta=document.querySelector('meta[name="theme-color"]');
    if(meta)meta.content=theme==='dark'?'#101a17':'#f6f5f0';
    document.querySelectorAll('[data-theme-toggle]').forEach(button=>{
      button.setAttribute('aria-pressed',String(theme==='dark'));
      button.setAttribute('aria-label',theme==='dark'?'Switch to light colors':'Switch to dark colors');
      button.innerHTML=theme==='dark'?'<span aria-hidden="true">☀</span>':'<span aria-hidden="true">☾</span>';
    });
  }
  apply();
  document.addEventListener('DOMContentLoaded',()=>{
    apply();
    document.querySelectorAll('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>{
      theme=theme==='light'?'dark':'light';
      try {localStorage.setItem('sera-theme',theme);}catch{}
      apply();
    }));
  });
})();
