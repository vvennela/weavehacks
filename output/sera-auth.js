(() => {
  const form=document.getElementById('auth-form');
  if(form){
    let signup=form.dataset.mode==='signup';
    const password=document.getElementById('password'), submit=document.getElementById('auth-submit'), error=document.getElementById('auth-error'), mode=document.getElementById('switch-mode');
    const show=document.getElementById('show-password');
    show.addEventListener('click',()=>{const visible=password.type==='password';password.type=visible?'text':'password';show.textContent=visible?'Hide':'Show';show.setAttribute('aria-pressed',String(visible));show.setAttribute('aria-label',visible?'Hide password':'Show password');});
    mode.addEventListener('click',()=>location.assign(signup?'/sign-in':'/get-started'));
    const demo=document.getElementById('fill-demo');
    if(demo)demo.addEventListener('click',()=>{form.email.value=demo.dataset.email;password.value=demo.dataset.password;error.hidden=true;submit.focus();});
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(!form.reportValidity())return;
      submit.disabled=true;mode.disabled=true;error.hidden=true;submit.textContent=signup?'Creating account…':'Signing in…';
      try{
        const response=await fetch(signup?'/api/sign-up':'/api/sign-in',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:form.email.value,password:password.value})});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||'Unable to sign in. Please try again.');
        location.assign('/lab');
      }catch(err){error.textContent=err instanceof TypeError?'Cannot reach the local server. Please try again.':err.message;error.hidden=false;submit.disabled=false;mode.disabled=false;submit.textContent=signup?'Create account ↗':'Sign in ↗';}
    });
  }
  const logout=document.getElementById('sign-out');
  if(logout){
    fetch('/api/session').then(async response=>{if(response.status===401){location.replace('/sign-in');return;}if(!response.ok)throw new Error();const user=await response.json();document.getElementById('account-email').textContent=user.email;}).catch(()=>{document.getElementById('account-email').textContent='Account unavailable';});
    logout.addEventListener('click',async()=>{logout.disabled=true;try{const response=await fetch('/api/sign-out',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw new Error();location.replace('/sign-in');}catch{document.getElementById('logout-error').textContent='Could not sign out. Please try again.';logout.disabled=false;}});
    window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
  }
})();
