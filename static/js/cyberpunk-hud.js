// Night City HUD — Character + quote rotator (lightweight, no deps)
// Curated lines from Cyberpunk 2077 / Edgerunners (English VA).
(function () {
  const LINES = [
    { who: "JOHNNY SILVERHAND", role: "ROCKERBOY",   q: "Wake the fuck up, Samurai. We have a city to burn." },
    { who: "DAVID MARTINEZ",    role: "EDGERUNNER",  q: "Look, Mom… I'm here, very top of Arasaka Tower." },
    { who: "LUCY",              role: "NETRUNNER",   q: "You never had to save me. All I ever wanted was for you to live." },
    { who: "REBECCA",           role: "EDGERUNNER",  q: "Sign me up, choomba. Into the fire." },
    { who: "DAVID MARTINEZ",    role: "EDGERUNNER",  q: "I feel better in metal than in my own skin." },
    { who: "LUCY",              role: "NETRUNNER",   q: "Don't make a name for yourself as a cyberpunk by how you live… make a name by how you die." },
    { who: "ADAM SMASHER",      role: "ENFORCER",    q: "Who the fuck are you?" },
  ];

  function init() {
    const nodes = document.querySelectorAll(".silverhand-hud");
    if (!nodes.length) return;

    nodes.forEach((hud) => {
      const headEl  = hud.querySelector(".silverhand-head");
      const quoteEl = hud.querySelector(".silverhand-quote");
      if (!headEl || !quoteEl) return;

      // Random start so every page load feels different
      let i = Math.floor(Math.random() * LINES.length);

      const render = () => {
        const { who, role, q } = LINES[i % LINES.length];
        headEl.style.transition  = "opacity 0.35s";
        quoteEl.style.transition = "opacity 0.35s";
        headEl.style.opacity  = "0";
        quoteEl.style.opacity = "0";
        setTimeout(() => {
          headEl.textContent  = `${who} // ${role}`;
          quoteEl.textContent = `"${q}"`;
          headEl.style.opacity  = "0.95";
          quoteEl.style.opacity = "0.95";
        }, 380);
        i++;
      };

      render();
      setInterval(render, 7000);
    });
  }

  // ── Horloge Night City dans la topbar ─────────────────────────────
  function initClock() {
    const crumb = document.querySelector(".topbar-breadcrumb");
    if (!crumb || crumb.querySelector(".nc-clock")) return;
    const el = document.createElement("span");
    el.className = "topbar-aux nc-clock";
    crumb.appendChild(el);
    const tick = () => {
      const d = new Date();
      const p = (n) => String(n).padStart(2, "0");
      el.textContent = `NC ${p(d.getHours())}:${p(d.getMinutes())}`;
    };
    tick();
    setInterval(tick, 30000);
  }

  // ── SFX d'interface (WebAudio, ultra discret, toggle persistant) ──
  function initSfx() {
    const KEY = "nc_sfx";
    let enabled = localStorage.getItem(KEY) !== "off";
    let ctx = null;

    // Crée/réveille l'AudioContext. Les navigateurs le démarrent "suspended"
    // tant qu'il n'y a pas eu de geste utilisateur → on le réveille ici.
    function ensureCtx() {
      try {
        if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
        if (ctx.state === "suspended") ctx.resume();
        return ctx;
      } catch (e) { return null; }
    }

    // Amorçage : au TOUT PREMIER geste (clic/touche), on réveille le contexte
    // pour que les bips de survol qui suivent soient fiables. (Le survol seul
    // ne suffit pas à débloquer l'audio côté navigateur.)
    const prime = () => { ensureCtx(); window.removeEventListener("pointerdown", prime); window.removeEventListener("keydown", prime); };
    window.addEventListener("pointerdown", prime, { once: false });
    window.addEventListener("keydown", prime, { once: false });

    const blip = (freq, dur, gain, type) => {
      if (!enabled) return;
      const c = ensureCtx();
      if (!c || c.state !== "running") return;   // pas encore débloqué → silence propre
      try {
        const osc = c.createOscillator();
        const g = c.createGain();
        osc.type = type || "square";
        osc.frequency.value = freq;
        g.gain.setValueAtTime(gain, c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + dur);
        osc.connect(g).connect(c.destination);
        osc.start();
        osc.stop(c.currentTime + dur);
      } catch (e) { /* WebAudio indispo — tant pis, pas de son */ }
    };

    const hoverSfx = () => blip(2400, 0.03, 0.012, "square");
    const clickSfx = () => blip(1180, 0.07, 0.025, "triangle");

    // Délégation : survol nav/cartes = tick, clic boutons/liens = blip.
    const SEL = ".nav-item, .tool-card, .hg-channel-card";
    document.addEventListener("mouseover", (e) => {
      const t = e.target.closest && e.target.closest(SEL);
      if (t) {
        // On ne rejoue pas tant qu'on reste sur le MÊME élément…
        if (t !== initSfx._last) { initSfx._last = t; hoverSfx(); }
      } else {
        // …mais on réarme dès qu'on quitte la cible → re-survol = re-son.
        initSfx._last = null;
      }
    });
    document.addEventListener("click", (e) => {
      if (e.target.closest(".nav-item, .tool-card, .btn-ghost, .hg-btn, .hg-channel-card, button, a")) clickSfx();
    });

    // Interrupteur sur la ligne du status (pour ne pas grandir le footer)
    const statusRow = document.querySelector(".sidebar-footer .status-dot");
    if (statusRow) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sfx-toggle" + (enabled ? "" : " off");
      btn.textContent = enabled ? "♪ ON" : "♪ OFF";
      btn.title = "Sons d'interface";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        enabled = !enabled;
        localStorage.setItem(KEY, enabled ? "on" : "off");
        btn.className = "sfx-toggle" + (enabled ? "" : " off");
        btn.textContent = enabled ? "♪ ON" : "♪ OFF";
        if (enabled) clickSfx();
      });
      statusRow.appendChild(btn);
    }
  }

  // ── Delamain : se masque dès que la nav n'a plus la place ─────────
  function boot() {
    init();
    initClock();
    initSfx();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
