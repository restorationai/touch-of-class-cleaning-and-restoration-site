(function(){const o=window.EmergencyWidgetId;if(!o){console.error("Restoration AI: Missing EmergencyWidgetId. Embed failed.");return}const d="https://nyscciinkhlutvqkgyvq.supabase.co",r="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im55c2NjaWlua2hsdXR2cWtneXZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYyODMxMzMsImV4cCI6MjA4MTg1OTEzM30.4c3QmNYFZS68y4JLtEKwzVo_nQm3pKzucLOajSVRDOA";async function p(){try{return(await(await fetch(`${d}/rest/v1/public_widget_settings?id=eq.${o}`,{headers:{apikey:r,Authorization:`Bearer ${r}`}})).json())[0]}catch(e){return console.error("Restoration AI: Failed to sync settings.",e),null}}function g(e){const i=document.createElement("style");i.innerHTML=`
      #rai-widget-wrapper {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 2147483647;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 16px;
      }
      #rai-iframe-container {
        width: 400px;
        height: 700px;
        max-height: calc(100vh - 120px);
        max-width: calc(100vw - 48px);
        background: transparent;
        border: none;
        border-radius: 2rem;
        box-shadow: 0 20px 80px rgba(0,0,0,0.25);
        display: none;
        overflow: hidden;
        margin-bottom: 12px;
      }
      .rai-fab {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        background-color: ${e};
        box-shadow: 0 12px 40px rgba(0,0,0,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        border: none;
        padding: 0;
        outline: none;
      }
      .rai-fab:hover { transform: scale(1.1); }
      .rai-fab svg { color: white; fill: white; width: 32px; height: 32px; }
      .rai-dot {
        position: absolute;
        top: 0;
        right: 0;
        width: 12px;
        height: 12px;
        background-color: white;
        border-radius: 50%;
        border: 2px solid ${e};
      }
      .rai-bubble {
        background: white;
        padding: 20px;
        border-radius: 28px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.15);
        width: 280px;
        display: flex;
        align-items: center;
        gap: 16px;
        border: 1px solid #f1f5f9;
        position: relative;
        animation: raiFadeUp 0.5s ease-out forwards;
      }
      .rai-logo-circle {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background: #f8fafc;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        flex-shrink: 0;
        border: 1px solid #f1f5f9;
      }
      .rai-logo-circle img { width: 100%; height: 100%; object-fit: cover; }
      .rai-welcome-text {
        font-size: 14px;
        font-weight: 700;
        color: #334155;
        line-height: 1.4;
        margin: 0;
      }
      .rai-close-bubble {
        position: absolute;
        top: 12px;
        right: 12px;
        cursor: pointer;
        color: #94a3b8;
        background: none;
        border: none;
        padding: 4px;
      }
      @keyframes raiFadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `,document.head.appendChild(i)}async function a(){const e=await p();if(!e)return;g(e.widget_primary_color||"#ef4444");const i=document.createElement("div");i.id="rai-widget-wrapper";const s=document.currentScript||document.querySelector('script[src*="widget-main.js"]'),b=`${s?new URL(s.src).origin:window.location.origin}/?widget=true&id=${o}`;i.innerHTML=`
      <iframe id="rai-iframe-container" src="${b}" allow="microphone"></iframe>
      <div class="rai-bubble" id="rai-welcome-bubble">
        <button class="rai-close-bubble" onclick="document.getElementById('rai-welcome-bubble').style.display='none'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="12"></line></svg>
        </button>
        <div class="rai-logo-circle">
          ${e.widget_logo_url?`<img src="${e.widget_logo_url}" />`:`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${e.widget_primary_color}" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`}
        </div>
        <p class="rai-welcome-text">${e.widget_welcome_text}</p>
      </div>
      <button class="rai-fab" id="rai-toggle-btn">
        <svg viewBox="0 0 24 24" fill="currentColor" id="rai-icon-open"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" id="rai-icon-close" style="display:none; color: white;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        <div class="rai-dot"></div>
      </button>
    `,document.body.appendChild(i);const m=document.getElementById("rai-toggle-btn"),n=document.getElementById("rai-iframe-container"),u=document.getElementById("rai-welcome-bubble"),l=document.getElementById("rai-icon-open"),c=document.getElementById("rai-icon-close");m.addEventListener("click",()=>{const t=n.style.display==="block";n.style.display=t?"none":"block",l.style.display=t?"block":"none",c.style.display=t?"none":"block",t||(u.style.display="none")}),window.addEventListener("message",t=>{t.data==="rai-close-widget"&&(n.style.display="none",l.style.display="block",c.style.display="none")})}document.readyState==="complete"?a():window.addEventListener("load",a)})();
