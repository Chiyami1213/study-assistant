// The guided tour (views/tutorial.py): dims the page except for the thing to use, draws a box and an arrow on it, and shows a helper card in the corner farthest from it, with a chain of the
// steps (a tick for each one done, the present one in blue) and Back / Next / Skip buttons. The buttons write "next|time", "back|time", "skip|time" or "done|time" into the hidden box
// tour_sink; the Python side moves to the page and opens the window of the next step, then draws this overlay again. __CFG__ is replaced by the step.
(function () {
  const cfg = __CFG__;
  const win = window.parent, doc = win.document;
  const old = doc.getElementById('sa-tour');
  if (old) { if (old.__stop) old.__stop(); old.remove(); }
  if (!doc.getElementById('sa-tour-css')) {
    const css = doc.createElement('style'); css.id = 'sa-tour-css';
    css.textContent = `
      #sa-tour {position: fixed; inset: 0; z-index: 2147483000; pointer-events: none; font-family: inherit;}
      #sa-tour[popover] {inset: 0; margin: 0; padding: 0; border: 0; width: 100vw; height: 100vh; max-width: none; max-height: none; background: transparent; overflow: visible; color: inherit;}
      #sa-tour .sa-dim {position: fixed; background: rgba(4, 7, 14, 0.66); pointer-events: auto;}
      #sa-tour.sa-free .sa-dim {pointer-events: none;}
      #sa-tour .sa-hole {position: fixed; border: 3px solid #5aa2ff; border-radius: 10px; box-shadow: 0 0 0 4px rgba(90, 162, 255, 0.28), 0 0 22px rgba(90, 162, 255, 0.55); pointer-events: none; animation: sa-pulse 1.6s ease-in-out infinite;}
      #sa-tour .sa-arrow {position: fixed; width: 0; height: 0; pointer-events: none; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));}
      #sa-tour .sa-card {position: fixed; width: 372px; max-width: calc(100vw - 32px); box-sizing: border-box; background: var(--card, #1b2230); color: var(--text, #e8ecf4); border: 1px solid var(--border, #33405a);
        border-radius: 14px; padding: 16px 18px 14px; box-shadow: 0 12px 40px rgba(0,0,0,0.55); pointer-events: auto; transition: left .25s ease, top .25s ease;}
      #sa-tour .sa-chain {display: flex; align-items: center; margin: 0 0 4px;}
      #sa-tour .sa-dot {flex: 0 0 auto; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; box-sizing: border-box;
        border: 2px solid #4a566e; color: #9aa6bd; background: transparent;}
      #sa-tour .sa-dot.sa-done {background: #2c9a5a; border-color: #2c9a5a; color: #fff;}
      #sa-tour .sa-dot.sa-now {width: 28px; height: 28px; background: #2f6fe0; border-color: #2f6fe0; color: #fff; font-size: 14px; box-shadow: 0 0 0 4px rgba(47, 111, 224, 0.28);}
      #sa-tour .sa-line {flex: 1 1 auto; height: 2px; background: #3a465e; margin: 0 4px; min-width: 6px;}
      #sa-tour .sa-line.sa-done {background: #2c9a5a;}
      #sa-tour .sa-where {font-size: 12px; font-weight: 700; color: #6fb0ff; margin: 6px 0 8px; letter-spacing: 0.2px;}
      #sa-tour .sa-title {font-size: 17px; font-weight: 700; margin: 0 0 6px;}
      #sa-tour .sa-text {font-size: 14px; line-height: 1.5; opacity: 0.92; margin: 0 0 14px;}
      #sa-tour .sa-row {display: flex; align-items: center; gap: 8px;}
      #sa-tour .sa-count {font-size: 12px; opacity: 0.65; margin-right: auto;}
      #sa-tour button {font: inherit; cursor: pointer; border-radius: 8px; padding: 7px 14px; font-size: 13px; font-weight: 600; border: 1px solid var(--border, #3a465e); background: transparent; color: inherit;}
      #sa-tour button:hover {border-color: #5aa2ff; color: #8ec0ff;}
      #sa-tour button.sa-next {background: #2f6fe0; border-color: #2f6fe0; color: #fff;}
      #sa-tour button.sa-next:hover {background: #3f7ff0; color: #fff;}
      #sa-tour button[disabled] {opacity: 0.35; cursor: default;}
      #sa-tour .sa-top {display: flex; align-items: center; justify-content: space-between; margin: -4px 0 10px; font-size: 12px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase; opacity: 0.85;}
      #sa-tour .sa-skip {border: 0; background: transparent; font-size: 12px; font-weight: 500; opacity: 0.75; padding: 2px 4px; text-transform: none; letter-spacing: 0;}
      @keyframes sa-pulse {50% {box-shadow: 0 0 0 7px rgba(90, 162, 255, 0.18), 0 0 30px rgba(90, 162, 255, 0.7);}}
      @keyframes sa-bob-r {50% {transform: translateX(7px);}} @keyframes sa-bob-l {50% {transform: translateX(-7px);}}
      @keyframes sa-bob-d {50% {transform: translateY(7px);}} @keyframes sa-bob-u {50% {transform: translateY(-7px);}}
      @media (prefers-reduced-motion: reduce) {#sa-tour * {animation: none !important; transition: none !important;}}`;
    doc.head.appendChild(css);
  }
  const root = doc.createElement('div'); root.id = 'sa-tour'; root.setAttribute('popover', 'manual'); doc.body.appendChild(root);
  // in the top layer of the browser: a window of the app (Streamlit's dialog) is there too, and would otherwise cover the helper card
  const raise = () => { try { if (root.matches(':popover-open')) root.hidePopover(); root.showPopover(); } catch (e) {} };
  // a window of the app marks everything outside it inert and hidden; the card has to stay usable on top of it
  const unlock = () => { if (root.hasAttribute('inert')) root.removeAttribute('inert'); if (root.hasAttribute('aria-hidden')) root.removeAttribute('aria-hidden'); };
  const guard = new win.MutationObserver(unlock); guard.observe(root, {attributes: true, attributeFilter: ['inert', 'aria-hidden']});
  unlock();
  // a click on the card must not count as a click outside a window of the app (that would close it): the pointer events that start in the card stop at the window
  const swallow = e => { if (root.contains(e.target)) e.stopPropagation(); };
  const kinds = ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'touchstart', 'touchend'];
  kinds.forEach(k => win.addEventListener(k, swallow, true));
  raise();
  let dialogs = doc.querySelectorAll('[data-testid="stDialog"]').length;
  const make = (cls, parent) => { const e = doc.createElement('div'); e.className = cls; (parent || root).appendChild(e); return e; };
  const dims = [make('sa-dim'), make('sa-dim'), make('sa-dim'), make('sa-dim')];
  const hole = make('sa-hole'), arrow = make('sa-arrow'), card = make('sa-card');

  // ---- the helper card
  const chain = cfg.chain.map((c, i) => `${i ? `<div class="sa-line${c.state !== 'todo' ? ' sa-done' : ''}"></div>` : ''}<div class="sa-dot sa-${c.state}">${c.state === 'done' ? '&#10003;' : i + 1}</div>`).join('');
  const now = cfg.chain.find(c => c.state === 'now');
  const esc = s => String(s).replace(/[&<>]/g, m => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[m]));
  card.innerHTML = `<div class="sa-top"><span>Getting Started</span><button class="sa-skip" data-a="skip" title="close the tutorial">Skip Tutorial &#10005;</button></div><div class="sa-chain">${chain}</div>`
    + `<div class="sa-where">${now ? esc((cfg.chain.indexOf(now) + 1) + '. ' + now.label) : esc(cfg.where || '')}</div><div class="sa-title">${esc(cfg.title)}</div><div class="sa-text">${esc(cfg.text)}</div>`
    + `<div class="sa-row"><span class="sa-count">${cfg.i + 1} / ${cfg.n}</span><button data-a="back"${cfg.i === 0 ? ' disabled' : ''}>Back</button>`
    + `<button class="sa-next" data-a="${cfg.last ? 'done' : 'next'}">${cfg.last ? 'Finish' : 'Next'}</button></div>`;
  const send = text => {
    const inp = doc.querySelector('.st-key-tour_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  card.addEventListener('click', e => { const b = e.target.closest('button[data-a]'); if (b && !b.disabled) { e.stopPropagation(); send(b.dataset.a); } });
  dims.forEach(d => d.addEventListener('wheel', e => {                        // the dim does not stop the page from scrolling
    const sc = doc.querySelector('[data-testid="stMain"]') || doc.querySelector('section.main'); if (sc) sc.scrollBy(0, e.deltaY);
  }, {passive: true}));

  // ---- the thing to use
  const WIDGETS = '[data-testid="stTextInput"], [data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stFileUploader"], [data-testid="stDateInput"], [data-testid="stTimeInput"], '
                + '[data-testid="stNumberInput"], [data-testid="stButtonGroup"], [data-testid="stCheckbox"], [data-testid="stToggle"], [data-testid="stTextArea"]';
  const visible = e => { if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const find = spec => {
    if (!spec) return null;
    const scope = doc.querySelector('[data-testid="stDialog"]') || doc;
    if (spec.startsWith('css:')) return [...doc.querySelectorAll(spec.slice(4))].find(visible) || null;
    if (spec === 'dialog') return doc.querySelector('[data-testid="stDialog"] [role="dialog"], [data-testid="stDialog"] > div') || null;
    if (spec.startsWith('label:')) {
      const want = spec.slice(6).toLowerCase();
      const lab = [...scope.querySelectorAll('[data-testid="stWidgetLabel"], label')].find(l => (l.textContent || '').trim().toLowerCase().startsWith(want));
      if (!lab) return null;
      return lab.closest(WIDGETS) || lab.parentElement;
    }
    if (spec.startsWith('button:')) {
      const want = spec.slice(7).toLowerCase();
      return [...scope.querySelectorAll('button')].find(b => visible(b) && (b.textContent || '').trim().toLowerCase() === want) || null;
    }
    return null;
  };
  let scrolled = false, born = Date.now();
  const place = () => {
    const vw = win.innerWidth, vh = win.innerHeight;
    const nd = doc.querySelectorAll('[data-testid="stDialog"]').length;
    if (nd !== dialogs) { dialogs = nd; raise(); }                         // a window opened or closed: be on top of it again
    let target = find(cfg.target);
    if (target && !scrolled) {                                              // bring it into view once
      const r = target.getBoundingClientRect();
      if (r.top < 70 || r.bottom > vh - 20) target.scrollIntoView({block: 'center'});
      scrolled = true;
    }
    const r = target && visible(target) ? target.getBoundingClientRect() : null;
    const setRect = (el, x, y, w, h) => { el.style.left = x + 'px'; el.style.top = y + 'px'; el.style.width = Math.max(0, w) + 'px'; el.style.height = Math.max(0, h) + 'px'; };
    root.classList.toggle('sa-free', !r && cfg.target && Date.now() - born > 5000);          // a target that never shows up must not trap the student
    if (!r) {
      dims.forEach((d, i) => setRect(d, 0, 0, i === 0 ? vw : 0, i === 0 ? vh : 0));
      hole.style.display = arrow.style.display = 'none';
    } else {
      const pad = 6, x = Math.max(0, r.left - pad), y = Math.max(0, r.top - pad), w = r.width + 2 * pad, h = r.height + 2 * pad;
      setRect(dims[0], 0, 0, vw, y); setRect(dims[1], 0, y + h, vw, vh - y - h); setRect(dims[2], 0, y, x, h); setRect(dims[3], x + w, y, vw - x - w, h);
      hole.style.display = 'block'; setRect(hole, x, y, w, h);
      // the arrow: on the side of the box that has room, pointing at it
      const room = {left: x, right: vw - x - w, top: y, bottom: vh - y - h}, side = room.left > 70 ? 'left' : room.top > 70 ? 'top' : room.right > 70 ? 'right' : 'bottom';
      const S = 14, cx = x + w / 2, cy = y + h / 2;
      arrow.style.display = 'block'; arrow.style.border = '0'; arrow.style.animation = '';
      const set = (css, left, top, anim) => { arrow.style.cssText += css; arrow.style.left = left + 'px'; arrow.style.top = top + 'px'; arrow.style.animation = anim + ' 0.9s ease-in-out infinite'; };
      arrow.style.cssText = 'display:block;position:fixed;width:0;height:0;pointer-events:none;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5));';
      if (side === 'left') set(`border-top:${S}px solid transparent;border-bottom:${S}px solid transparent;border-left:${S * 1.6}px solid #5aa2ff;`, x - S * 1.6 - 10, cy - S, 'sa-bob-r');
      else if (side === 'top') set(`border-left:${S}px solid transparent;border-right:${S}px solid transparent;border-top:${S * 1.6}px solid #5aa2ff;`, cx - S, y - S * 1.6 - 10, 'sa-bob-d');
      else if (side === 'right') set(`border-top:${S}px solid transparent;border-bottom:${S}px solid transparent;border-right:${S * 1.6}px solid #5aa2ff;`, x + w + 10, cy - S, 'sa-bob-l');
      else set(`border-left:${S}px solid transparent;border-right:${S}px solid transparent;border-bottom:${S * 1.6}px solid #5aa2ff;`, cx - S, y + h + 10, 'sa-bob-u');
    }
    // the card sits in the corner farthest from the box (the middle of the page when there is no box)
    const cw = card.offsetWidth, ch = card.offsetHeight, m = 20;
    if (!r) { card.style.left = Math.max(m, (vw - cw) / 2) + 'px'; card.style.top = Math.max(m, (vh - ch) / 2) + 'px'; return; }
    const ccx = r.left + r.width / 2, ccy = r.top + r.height / 2;
    const corners = [[vw - cw - m, vh - ch - m], [m + 70, vh - ch - m], [vw - cw - m, m], [m + 70, m]];
    let best = corners[0], bestD = -1;
    corners.forEach(([x, y]) => {
      const overlap = !(x + cw < r.left - 12 || x > r.right + 12 || y + ch < r.top - 12 || y > r.bottom + 12);
      const d = Math.hypot(x + cw / 2 - ccx, y + ch / 2 - ccy) - (overlap ? 10000 : 0);
      if (d > bestD) { bestD = d; best = [x, y]; }
    });
    card.style.left = best[0] + 'px'; card.style.top = best[1] + 'px';
  };
  place();
  const timer = win.setInterval(place, 220);
  win.addEventListener('resize', place);
  root.__stop = () => { kinds.forEach(k => win.removeEventListener(k, swallow, true)); guard.disconnect(); win.clearInterval(timer); win.removeEventListener('resize', place); };
})();
