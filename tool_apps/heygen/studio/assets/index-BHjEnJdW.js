(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const n of document.querySelectorAll('link[rel="modulepreload"]'))o(n);new MutationObserver(n=>{for(const s of n)if(s.type==="childList")for(const c of s.addedNodes)c.tagName==="LINK"&&c.rel==="modulepreload"&&o(c)}).observe(document,{childList:!0,subtree:!0});function a(n){const s={};return n.integrity&&(s.integrity=n.integrity),n.referrerPolicy&&(s.referrerPolicy=n.referrerPolicy),n.crossOrigin==="use-credentials"?s.credentials="include":n.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function o(n){if(n.ep)return;n.ep=!0;const s=a(n);fetch(n.href,s)}})();const O="heygen-studio";function x(){try{const e=localStorage.getItem(O);if(e)return{apiKey:"",voices:[],...JSON.parse(e)}}catch{}return{apiKey:"",voices:[]}}function j(e){const t={...x(),...e};return localStorage.setItem(O,JSON.stringify(t)),t}function G(e){const t=x();return t.voices.some(a=>a.name===e.name)||t.voices.push(e),j({voices:t.voices})}function k(e){const t=x();return j({voices:t.voices.filter(a=>a.name!==e)})}const m=window.VIDEO_TOOLS,_=((m==null?void 0:m.renderApi)??"").trim().replace(/\/+$/,""),K=_==="",g=`${_}/relay/heygen`;function N(){var t;const e=(((t=m==null?void 0:m.keys)==null?void 0:t.heygen)??"").trim();return e||x().apiKey.trim()}var A;const U=(((A=m==null?void 0:m.keys)==null?void 0:A.heygen)??"").trim()!=="";function b(e=!1){const t={},a=N();return a&&(t["X-Provider-Key"]=a),e&&(t["Content-Type"]="application/json"),t}async function $(e){if(!e.ok){let t=`${e.status} ${e.statusText}`;try{const a=await e.json();t=a.message||a.error||t}catch{}throw new Error(t)}return e.json()}const h={health:()=>fetch(`${g}/api/health`,{headers:b()}).then(e=>$(e)),avatars:()=>fetch(`${g}/api/avatars`,{headers:b()}).then(e=>$(e)).then(e=>e.avatars??[]),uploadAvatar:(e,t)=>{const a=new FormData;return a.append("image",e),t&&a.append("avatar_name",t),fetch(`${g}/api/avatars/upload`,{method:"POST",headers:b(),body:a}).then(o=>$(o))},generateWithAudio:e=>{const t=new FormData;return t.append("audio",e.audio),t.append("avatar_name",e.avatar_name),e.title&&t.append("title",e.title),t.append("resolution",e.resolution),t.append("orientation",e.orientation),fetch(`${g}/api/generate`,{method:"POST",headers:b(),body:t}).then(a=>$(a))},generateWithVoice:e=>fetch(`${g}/api/generate-with-voice`,{method:"POST",headers:b(!0),body:JSON.stringify(e)}).then(t=>$(t)),job:e=>fetch(`${g}/api/jobs/${encodeURIComponent(e)}`,{headers:b()}).then(t=>$(t)),jobs:e=>{const t=new URLSearchParams({page:"1",limit:"50"});return e&&t.set("status",e),fetch(`${g}/api/jobs?${t}`,{headers:b()}).then(a=>$(a)).then(a=>{if(Array.isArray(a))return a;const o=a;return o.jobs??o.data??[]})},downloadUrl:e=>e.download_url?e.download_url.startsWith("http")?e.download_url:g+(e.download_url.startsWith("/")?"":"/")+e.download_url:null},w=document.getElementById("app");function v(e){const t=document.createElement("template");return t.innerHTML=e.trim(),t.content.firstElementChild}function r(e){return e.replace(/[&<>"']/g,t=>`&#${t.charCodeAt(0)};`)}let q;function y(e,t=""){const a=v(`<div class="toastmsg ${t}">${r(e)}</div>`);q.appendChild(a),setTimeout(()=>a.remove(),6e3)}const M=["avatars","voices","generate","jobs","settings"];function R(){w.innerHTML="",K&&w.appendChild(v(`<div style="background:#7c2d12;color:#fde68a;padding:10px 20px;font-weight:600;
            text-align:center;font-size:14px;">⚠️ Render API non configurée — renseignez config.js</div>`)),w.appendChild(v(`<header class="rack">
      <div class="brand">
        <h1>HEYGEN <em>STUDIO</em></h1>
        <span class="sub">multi-channel control room</span>
      </div>
      <div class="leds" id="leds">
        <span class="led" id="led-session"><i></i>session</span>
        <span class="led" id="led-proxy"><i></i>proxy</span>
        <span class="led" id="led-queue"><i></i>queue —</span>
      </div>
    </header>`)),w.appendChild(v(`<nav class="tabs">${M.map((t,a)=>`<a href="#/${t}" data-route="${t}"><span class="k">0${a+1}</span>${t.toUpperCase()}</a>`).join("")}</nav>`));const e=v('<main id="view"></main>');w.appendChild(e),q=v('<div id="toast"></div>'),w.appendChild(q)}async function T(){const e=(t,a,o)=>{const n=document.getElementById(t);n&&(n.className=`led ${a}`,o&&(n.innerHTML=`<i></i>${r(o)}`))};try{const t=await h.health();e("led-session",t.session==="connected"?"on":"off","session"),e("led-proxy",t.proxy==="active"?"on":"warn","proxy");const a=t.queue??{waiting:0,active:0};e("led-queue",a.active>0?"warn":"on",`queue ${a.active??0}/${a.waiting??0}`)}catch{e("led-session","off","session"),e("led-proxy","off","proxy"),e("led-queue","off","queue ?")}}let S=null;async function D(e){e.innerHTML=`<div class="view">
    <h2>Cast of <strong>avatars</strong></h2>
    <p class="lede">Les avatars de ton compte HeyGen. Clique pour copier le nom exact (c'est lui que l'API attend).</p>
    <div class="panel"><h3>roster</h3><div class="cards" id="cards"><div class="empty"><span class="spin"></span>interrogation de HeyGen…</div></div></div>
    <div class="panel"><h3>nouveau photo-avatar</h3>
      <form id="upform">
        <div class="row">
          <label class="field"><span>photo (jpg/png/webp, 20 Mo max)</span><input type="file" name="image" accept="image/jpeg,image/png,image/webp" required /></label>
          <label class="field"><span>nom de l'avatar</span><input type="text" name="avatar_name" placeholder="Ruth V2" /></label>
        </div>
        <button class="cta" type="submit">Créer l'avatar</button>
        <p class="note" style="margin-top:10px">Opération synchrone — l'automatisation HeyGen prend 1 à 2 minutes, laisse la page ouverte.</p>
      </form>
    </div>
  </div>`;const t=e.querySelector("#cards"),a=o=>{t.innerHTML=o.length?"":'<div class="empty">aucun avatar</div>';for(const n of o){const s=v(`<div class="card">
        <div class="idx">#${n.index}</div>
        <div class="nm">${r(n.name)}</div>
        <div class="tag">photo avatar</div>
      </div>`);s.addEventListener("click",()=>{navigator.clipboard.writeText(n.name),y(`« ${n.name} » copié`,"ok")}),t.appendChild(s)}};try{S=await h.avatars(),a(S)}catch(o){t.innerHTML=`<div class="empty">⚠ ${r(String(o))} — clé API manquante ? (onglet SETTINGS)</div>`}e.querySelector("#upform").addEventListener("submit",async o=>{var l;o.preventDefault();const n=o.target,s=n.querySelector("button.cta"),c=(l=n.elements.namedItem("image").files)==null?void 0:l[0],i=n.elements.namedItem("avatar_name").value.trim();if(c){s.disabled=!0,s.innerHTML='<span class="spin"></span>création en cours (1-2 min)…';try{const p=await h.uploadAvatar(c,i||void 0);y(p.message||`Avatar « ${p.avatar_name} » créé`,"ok"),S=await h.avatars(),a(S),n.reset()}catch(p){y(`Échec upload : ${p}`,"err")}finally{s.disabled=!1,s.textContent="Créer l'avatar"}}})}function F(e){const t=()=>{const{voices:a}=x(),o=e.querySelector("#chips");o.innerHTML=a.length?"":`<div class="empty">aucune voix enregistrée — ajoute les noms exacts de l'onglet « My voices » HeyGen</div>`;for(const n of a){const s=v(`<span class="chip"><b>${r(n.name)}</b>${n.label?`<span class="note">${r(n.label)}</span>`:""}<button class="x" title="retirer">✕</button></span>`);s.querySelector(".x").addEventListener("click",()=>{k(n.name),t()}),o.appendChild(s)}};e.innerHTML=`<div class="view">
    <h2>Registre des <strong>voix</strong></h2>
    <p class="lede">L'API n'expose pas la liste des voix : ce registre local mappe les noms exacts de ton onglet
    « My voices » HeyGen. Les clones custom ne survivent pas à un changement de compte HeyGen — re-crée-les si tu te reconnectes.</p>
    <div class="panel"><h3>voix enregistrées</h3><div class="chips" id="chips"></div></div>
    <div class="panel"><h3>ajouter une voix</h3>
      <form id="vform">
        <div class="row">
          <label class="field"><span>voice_name (exact, sensible à la casse)</span><input type="text" name="name" placeholder="ruth_voices" required /></label>
          <label class="field"><span>note (chaîne, langue…)</span><input type="text" name="label" placeholder="Ruth Hayes — EN chaleureux" /></label>
        </div>
        <button class="cta" type="submit">Ajouter</button>
      </form>
    </div>
  </div>`,t(),e.querySelector("#vform").addEventListener("submit",a=>{a.preventDefault();const o=a.target,n=o.elements.namedItem("name").value.trim(),s=o.elements.namedItem("label").value.trim();n&&(G({name:n,label:s||void 0}),o.reset(),t(),y(`Voix « ${n} » ajoutée`,"ok"))})}async function B(e){const{voices:t}=x();let a="voice";e.innerHTML=`<div class="view">
    <h2>Lancer une <strong>génération</strong></h2>
    <p class="lede">Avatar + voix TTS HeyGen, ou avatar + fichier audio déjà prêt (ElevenLabs, Minimax…). Le job part en file et se suit dans JOBS.</p>
    <div class="panel">
      <h3>mode</h3>
      <div class="seg" id="seg">
        <button type="button" data-m="voice" class="on">VOICE — script + TTS</button>
        <button type="button" data-m="audio">AUDIO — fichier uploadé</button>
      </div>
    </div>
    <form id="gform">
      <div class="panel"><h3>casting</h3>
        <div class="row">
          <label class="field"><span>avatar</span><select name="avatar" id="avsel"><option>chargement…</option></select></label>
          <label class="field" id="f-voice"><span>voix (registre local)</span>
            <select name="voice">${t.length?t.map(i=>`<option value="${r(i.name)}">${r(i.name)}${i.label?` — ${r(i.label)}`:""}</option>`).join(""):'<option value="">(registre vide — onglet VOICES)</option>'}</select></label>
          <label class="field" id="f-audio" style="display:none"><span>fichier audio (wav/mp3)</span><input type="file" name="audio" accept="audio/wav,audio/mpeg,audio/mp3" /></label>
        </div>
      </div>
      <div class="panel" id="p-script"><h3>script</h3>
        <label class="field"><span>texte (max 30 000 caractères)</span><textarea name="script" maxlength="30000" placeholder="Le texte que l'avatar va dire…"></textarea></label>
        <div class="charcount" id="cc">0 / 30000</div>
      </div>
      <div class="panel"><h3>réglages</h3>
        <div class="row">
          <label class="field"><span>titre (optionnel)</span><input type="text" name="title" placeholder="RUTH #4 — hydrogen peroxide" /></label>
          <label class="field"><span>résolution</span><select name="resolution"><option value="1080p">1080p</option><option value="720p">720p</option></select></label>
          <label class="field"><span>orientation</span><select name="orientation"><option value="landscape">landscape 16:9</option><option value="portrait">portrait 9:16</option></select></label>
        </div>
        <button class="cta" type="submit">⏺ Générer la vidéo</button>
      </div>
    </form>
  </div>`;const o=e.querySelector("#avsel");try{const i=S??(S=await h.avatars());o.innerHTML=i.map(l=>`<option value="${r(l.name)}" data-index="${l.index}">${r(l.name)} (#${l.index})</option>`).join("")}catch(i){o.innerHTML=`<option value="">erreur: ${r(String(i))}</option>`}const n=e.querySelector("#seg");n.querySelectorAll("button").forEach(i=>i.addEventListener("click",()=>{a=i.dataset.m,n.querySelectorAll("button").forEach(l=>l.classList.toggle("on",l===i)),e.querySelector("#f-voice").style.display=a==="voice"?"":"none",e.querySelector("#p-script").style.display=a==="voice"?"":"none",e.querySelector("#f-audio").style.display=a==="audio"?"":"none"}));const s=e.querySelector("textarea[name=script]"),c=e.querySelector("#cc");s.addEventListener("input",()=>{c.textContent=`${s.value.length} / 30000`,c.classList.toggle("over",s.value.length>=3e4)}),e.querySelector("#gform").addEventListener("submit",async i=>{var I;i.preventDefault();const l=i.target,p=l.querySelector("button.cta"),u=d=>{var f;return((f=l.elements.namedItem(d))==null?void 0:f.value)??""},L=u("avatar");if(!L)return y("Choisis un avatar","err");p.disabled=!0,p.innerHTML='<span class="spin"></span>envoi…';try{let d;if(a==="voice"){const f=u("voice"),H=u("script").trim();if(!f)throw new Error("Aucune voix — ajoute-en une dans VOICES");if(!H)throw new Error("Script vide");const C=o.selectedOptions[0];d=await h.generateWithVoice({avatar_name:L,voice_name:f,script_text:H,title:u("title")||void 0,avatar_index:C?Number(C.dataset.index??0):0,resolution:u("resolution"),orientation:u("orientation")})}else{const f=(I=l.elements.namedItem("audio").files)==null?void 0:I[0];if(!f)throw new Error("Aucun fichier audio");d=await h.generateWithAudio({audio:f,avatar_name:L,title:u("title")||void 0,resolution:u("resolution"),orientation:u("orientation")})}y(`Job ${d.job_id} en file (${d.status})`,"ok"),location.hash="#/jobs"}catch(d){y(`Échec : ${d instanceof Error?d.message:d}`,"err")}finally{p.disabled=!1,p.textContent="⏺ Générer la vidéo"}})}let E;async function J(e){e.innerHTML=`<div class="view">
    <h2>File de <strong>jobs</strong></h2>
    <p class="lede">Suivi des générations. Les jobs actifs se rafraîchissent tout seuls toutes les 10 s.</p>
    <div class="panel">
      <h3>générations <button class="ghost" id="rf" style="margin-left:auto">rafraîchir</button></h3>
      <table class="jobs">
        <thead><tr><th>job</th><th>titre</th><th>statut</th><th>progression</th><th>sortie</th></tr></thead>
        <tbody id="rows"><tr><td colspan="5" class="empty"><span class="spin"></span>chargement…</td></tr></tbody>
      </table>
    </div>
  </div>`;const t=e.querySelector("#rows"),a=async()=>{try{const o=await h.jobs();if(!o.length){t.innerHTML='<tr><td colspan="5" class="empty">aucun job — lance une génération</td></tr>';return}t.innerHTML="";for(const s of o){const c=s.progress?parseInt(s.progress):s.status==="complete"?100:0,i=h.downloadUrl(s),l=i?`<a class="dl" href="${r(i)}" target="_blank">télécharger ↓</a>`:s.status==="error"?`<span class="note err">${r(s.message??"erreur")}</span>`:'<span class="note">—</span>';t.appendChild(v(`<tr>
            <td style="font-size:11px;color:var(--dim)">${r(s.job_id).slice(0,13)}…</td>
            <td>${r(s.title??"—")}</td>
            <td><span class="status ${r(s.status)}"><i></i>${r(s.status)}</span></td>
            <td><div class="bar"><div style="width:${c}%"></div></div></td>
            <td>${l}</td>
          </tr>`))}o.some(s=>s.status==="queued"||s.status==="processing")&&location.hash==="#/jobs"&&(clearTimeout(E),E=window.setTimeout(a,1e4))}catch(o){t.innerHTML=`<tr><td colspan="5" class="empty">⚠ ${r(String(o))}</td></tr>`}};e.querySelector("#rf").addEventListener("click",a),a()}function V(e){const t=x();e.innerHTML=`<div class="view">
    <h2>Réglages <strong>console</strong></h2>
    <p class="lede">La clé API HeyGen (Settings → API Keys). Stockée en local dans ce navigateur et envoyée au relais
    via l'en-tête <code>X-Provider-Key</code>, jamais ailleurs.</p>
    ${U?`<div class="panel"><h3>clé config.js</h3><p class="note">Une clé HeyGen est définie dans
           <code>config.js</code> (keys.heygen) — c'est elle qui est utilisée ; la clé ci-dessous est ignorée
           tant que config.js en fournit une.</p></div>`:""}
    <div class="panel"><h3>authentification (clé par navigateur)</h3>
      <form id="sform">
        <div class="row">
          <label class="field"><span>api key</span><input type="password" name="apiKey" value="${r(t.apiKey)}" placeholder="hg_…" /></label>
        </div>
        <button class="cta" type="submit">Enregistrer</button>
      </form>
    </div>
  </div>`,e.querySelector("#sform").addEventListener("submit",a=>{a.preventDefault();const o=a.target.elements.namedItem("apiKey").value.trim();j({apiKey:o}),y("Clé enregistrée","ok"),T()})}function P(){clearTimeout(E);const e=location.hash.replace("#/","")||"avatars",t=M.includes(e)?e:"avatars";document.querySelectorAll("nav.tabs a").forEach(o=>{o.classList.toggle("active",o.dataset.route===t)});const a=document.getElementById("view");({avatars:D,voices:F,generate:B,jobs:J,settings:V})[t](a)}R();window.addEventListener("hashchange",P);P();T();setInterval(T,3e4);
