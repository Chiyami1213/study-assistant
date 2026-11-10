"""Shows Claude-generated HTML notes inside the app without their in-page links navigating the frame, opens them at a
section, and puts the course Quiz tab's question set into the note's own Self-check section."""
import json

# srcdoc frames resolve "#section" links against the app's own address, so a click would load the whole app
# inside the note. This script scrolls to the target instead (the note's own handlers still run).
_SCRIPT = """<script>
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a[href^="#"]');
  if (!a) return;
  e.preventDefault();
  var id = decodeURIComponent(a.getAttribute('href').slice(1));
  var t = id ? (document.getElementById(id) || document.getElementsByName(id)[0]) : document.body;
  if (t && t.scrollIntoView) t.scrollIntoView({behavior: 'smooth', block: 'start'});
}, true);
</script>"""

# Clicking an erratum (a block of the Notes check list) asks the Note Reader to show it on the open PDF: it writes
# "errata:<source>:<number>" into the hidden box of the page around this frame (only the Note Reader has one).
_ERRATA = """<script>
(function () {
  var SRC = "__SRC__", P = window.parent;
  var css = document.createElement('style');
  css.textContent = '.errata li{cursor:pointer}.errata li:hover{outline:2px solid #e5484d;outline-offset:3px;border-radius:6px}';
  document.head.appendChild(css);
  [].forEach.call(document.querySelectorAll('.errata li'), function (li) { li.title = 'show this on the pdf'; });
  document.addEventListener('click', function (e) {
    var li = e.target.closest && e.target.closest('.errata li');
    if (!li || (e.target.closest && e.target.closest('a'))) return;
    var idx = [].indexOf.call(document.querySelectorAll('.errata li'), li) + 1;
    var inp = P.document.querySelector('.st-key-lab_tab_sink input');
    if (!inp) return;
    var set = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, 'errata:' + SRC + ':' + idx + '|' + Date.now());
    inp.dispatchEvent(new P.Event('input', {bubbles: true}));
    inp.dispatchEvent(new P.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
})();
</script>"""

# "Slide 16", "slides 57-74", "Slides 13, 22" in a note are links to that page of the lecture slides: a click writes
# "slide:<note id>:<lecture>:<page>" into the hidden box of the Note Reader (the lecture comes from a "Lec 5" just before the
# words, else it is empty and the note's own lecture is meant).
_SLIDES = r"""<script>
(function () {
  var CFG = "__CFG__".split('|'), BOOK = CFG[0], P = window.parent;
  var css = document.createElement('style');
  css.textContent = '.sa-slide{cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px}.sa-slide:hover{color:#4c8dff;text-decoration-style:solid}';
  document.head.appendChild(css);
  var RE = /\b(slides?)(\s+)(\d+(?:\s*[\u2013-]\s*\d+)?(?:\s*(?:,|and|&)\s*\d+(?:\s*[\u2013-]\s*\d+)?)*)/gi;
  var SKIP = 'script,style,textarea,svg,a,button,mjx-container,.MathJax,input,select,.sa-slide';
  var MATH = /\\\(.*?\\\)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$/g;
  function wrap(node) {
    var t = node.nodeValue, math = [], m, hits = [];
    MATH.lastIndex = 0; while ((m = MATH.exec(t))) math.push([m.index, m.index + m[0].length]);
    RE.lastIndex = 0;
    while ((m = RE.exec(t))) { var s = m.index; if (!math.some(function (r) { return s >= r[0] && s < r[1]; })) hits.push(m); }
    if (!hits.length) return;
    var frag = document.createDocumentFragment(), pos = 0;
    hits.forEach(function (h) {
      var before = t.slice(pos, h.index); frag.appendChild(document.createTextNode(before + h[1] + h[2]));
      var lec = /\bLec(?:ture)?\s*(\d+)\b[^\d]*$/i.exec(t.slice(Math.max(0, h.index - 28), h.index)), nums = h[3], last = 0, n;
      var NUM = /\d+(?:\s*[\u2013-]\s*\d+)?/g;
      while ((n = NUM.exec(nums))) {
        if (n.index > last) frag.appendChild(document.createTextNode(nums.slice(last, n.index)));
        var sp = document.createElement('span'); sp.className = 'sa-slide'; sp.textContent = n[0];
        sp.dataset.page = parseInt(n[0], 10); sp.dataset.lec = lec ? lec[1] : ''; sp.title = 'open this slide in the pdf';
        frag.appendChild(sp); last = n.index + n[0].length;
      }
      if (last < nums.length) frag.appendChild(document.createTextNode(nums.slice(last)));
      pos = h.index + h[0].length;
    });
    frag.appendChild(document.createTextNode(t.slice(pos)));
    node.parentNode.replaceChild(frag, node);
  }
  function run() {
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode: function (n) {
      return n.parentElement && !n.parentElement.closest(SKIP) && /slide/i.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT; }});
    var nodes = [], n; while ((n = w.nextNode())) nodes.push(n);
    nodes.forEach(wrap);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
  window.addEventListener('load', function () { setTimeout(run, 1500); });
  document.addEventListener('click', function (e) {
    var sp = e.target.closest && e.target.closest('.sa-slide'); if (!sp) return;
    var inp = P.document.querySelector('.st-key-lab_tab_sink input'); if (!inp) return;
    var set = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, 'slide:' + BOOK + ':' + sp.dataset.lec + ':' + sp.dataset.page + '|' + Date.now());
    inp.dispatchEvent(new P.Event('input', {bubbles: true}));
    inp.dispatchEvent(new P.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
})();
</script>"""

# A click on an equation (<div class="eqb">) takes the reader to its source: the lecture slides or lecture notes named by the
# "source" line (<div class="src">) above it, or with Shift the textbook named there. The message is
# "eq:<url-encoded json>" in the hidden box of the Note Reader (the json holds the source line, the textbook line, the equation number
# and the words around the equation, which pick the slide inside a range of slides).
_EQSRC = r"""<script>
(function () {
  var CFG = "__CFG__".split('|'), BOOK = CFG[0], P = window.parent;
  var css = document.createElement('style');
  css.textContent = '.eqb{cursor:pointer}.eqb:hover{outline:2px solid #4c8dff;outline-offset:3px;border-radius:6px}.src>span{cursor:pointer}.src>span:hover{filter:brightness(1.3);text-decoration:underline dotted}';
  document.head.appendChild(css);
  var cur = null, head = null;
  [].forEach.call(document.querySelectorAll('h2,h3,.src,.eqb'), function (el) {
    if (el.classList.contains('src')) { cur = el; el._head = head;
      [].forEach.call(el.querySelectorAll(':scope > span'), function (sp) { sp.title = sp.classList.contains('vk') ? 'open this in the textbook' : 'open this in the lecture slides or notes'; }); }
    else if (el.classList.contains('eqb')) { el._src = cur; el._head = head; el.title = 'open its source (shift: textbook)'; }
    else head = el;
  });
  function text(el) { return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function sendEq(payload) {
    var inp = P.document.querySelector('.st-key-lab_tab_sink input'); if (!inp) return;
    var set = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, 'eq:' + encodeURIComponent(JSON.stringify(payload)) + '|' + Date.now());
    inp.dispatchEvent(new P.Event('input', {bubbles: true}));
    inp.dispatchEvent(new P.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }
  document.addEventListener('click', function (e) {                       // a chip of a source line: the lecture slides / notes, or the textbook
    var chip = e.target.closest && e.target.closest('.src>span'); if (!chip || e.target.closest('.sa-slide')) return;
    var src = chip.parentElement, spans = src.querySelectorAll(':scope > span'), vkEl = src.querySelector(':scope > .vk');
    var first = null; [].forEach.call(spans, function (sp) { if (!first && !sp.classList.contains('vk')) first = sp; });
    sendEq({note: BOOK, src: first ? text(first) : '', vk: vkEl ? text(vkEl) : '', eq: '', ctx: text(src._head).slice(0, 700), head: text(src._head), shift: chip.classList.contains('vk'), chip: true});
  }, true);
  document.addEventListener('click', function (e) {
    var eq = e.target.closest && e.target.closest('.eqb'); if (!eq) return;
    if (e.target.closest('a,button,input,textarea,select')) return;
    if (window.getSelection && String(window.getSelection()).length > 2) return;
    var src = eq._src, spans = src ? src.querySelectorAll('span') : [], ctx = text(eq._head), p = eq.previousElementSibling, n = 0;
    while (p && n < 3) { if (p.tagName === 'P') { ctx += ' ' + text(p); break; } p = p.previousElementSibling; n++; }
    var payload = {note: BOOK, src: spans.length ? text(spans[0]) : '', vk: src && src.querySelector('.vk') ? text(src.querySelector('.vk')) : '',
                   eq: text(eq.querySelector('.eqn')), ctx: ctx.slice(0, 700), head: text(eq._head), shift: !!e.shiftKey};
    var inp = P.document.querySelector('.st-key-lab_tab_sink input'); if (!inp) return;
    var set = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, 'eq:' + encodeURIComponent(JSON.stringify(payload)) + '|' + Date.now());
    inp.dispatchEvent(new P.Event('input', {bubbles: true}));
    inp.dispatchEvent(new P.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
})();
</script>"""

# F11 inside a note (a frame of the app): the app window goes full screen, or back (the page itself does this for the rest of the window).
_F11 = """<script>
document.addEventListener('keydown', function (e) {
  try {
    var P = window.parent, t = e.target, tag = (t && t.tagName || '').toLowerCase();
    if (e.key === 'F2' && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey && P && P.__saScreenshot) {
      e.preventDefault(); P.__saScreenshot();                                         // F2 inside a note
    } else if (e.key === 'F5' && !e.altKey && P && P.__saRefresh) {
      e.preventDefault(); if (e.ctrlKey || e.shiftKey || e.metaKey) P.__saReload(); else P.__saRefresh();                 // F5 inside a note
    } else if (e.key === 'F11' && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) {
      if (P && P.__saFullscreen && P.pywebview && P.pywebview.api && P.pywebview.api.toggle_fullscreen) { e.preventDefault(); P.__saFullscreen(); }
    } else if (P && P.__saMenuKey && P.__saMenuKey(e)) {
      e.preventDefault();                                           // a menu letter (l, n, c ...) pressed inside a note: that page opens
    } else if (P && P.__saMenuToggle && P.__keyIs && tag !== 'input' && tag !== 'textarea' && tag !== 'select' && !(t && t.isContentEditable) && P.__keyIs(e, 'app', 'menu', 'm')) {
      e.preventDefault(); P.__saMenuToggle();                       // the key that hides or shows the menu bar, pressed inside a note
    }
  } catch (err) {}
}, true);
</script>"""

# Esc inside a note shown full screen in the Note Reader clicks the page's Exit Full Screen button (unless the find bar used the key).
_ESC = """<script>
document.addEventListener('keydown', function (e) {
  if (e.defaultPrevented) return;
  try {
    var P = window.parent; if (!(P.__keyIs ? P.__keyIs(e, 'notes', 'leave_full', 'esc') : e.key === 'Escape')) return;
    var b = P.document.querySelector('.st-key-lab_full_close button'); if (b) b.click();
  } catch (err) {}
});
</script>"""

# The place the reader is at in a note (the heading or equation at the top of the window and how far past it) is kept as the page is
# scrolled, and the same note opened in the other mode (full screen, or in its window) opens at that place: leaving full screen keeps the position.
_ANCHOR = """<script>
(function () {
  var MODE = "__MODE__", KEY = 'sa_note_anchor', TITLE = document.title || 'note', SEL = 'h2[id],h3[id],h4[id],.eqb[id]';
  var armed = false, timer = null, stored = null;
  try { stored = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
  if (stored && !(stored.title === TITLE && stored.mode !== MODE && Date.now() - stored.t < 60000)) stored = null;
  function current() {
    var els = document.querySelectorAll(SEL), best = null;
    for (var i = 0; i < els.length; i++) { var r = els[i].getBoundingClientRect(); if (r.top <= 6) best = {id: els[i].id, off: Math.round(-r.top)}; else break; }
    return best || {id: '', off: Math.round(window.scrollY)};
  }
  function saveNow() {
    if (!armed) return;
    var c = current();
    try { localStorage.setItem(KEY, JSON.stringify({title: TITLE, mode: MODE, id: c.id, off: c.off, t: Date.now()})); } catch (e) {}
  }
  window.addEventListener('scroll', function () { clearTimeout(timer); timer = setTimeout(saveNow, 120); });
  setInterval(saveNow, 1000);                                  // also while nothing is scrolled: the place is always the latest one
  window.addEventListener('pagehide', saveNow);
  var steps = [], touched = false;
  ['wheel', 'keydown', 'touchstart', 'mousedown'].forEach(function (ev) { window.addEventListener(ev, function () { touched = true; }, {passive: true, capture: true}); });
  function go() {
    if (!stored || touched) return;                              // the reader took over: leave the page where they put it
    var el = stored.id ? document.getElementById(stored.id) : null;
    if (el) {
      var d = el.closest('details'); if (d && !d.open) d.open = true;
      el.scrollIntoView({block: 'start', behavior: 'instant'});
      window.scrollBy({top: stored.off, behavior: 'instant'});
    } else if (!stored.id) window.scrollTo({top: stored.off || 0, behavior: 'instant'});
  }
  // the page grows while its equations are typeset, so the place is found again a few times
  window.addEventListener('load', function () { [500, 1400, 2600, 4200].forEach(function (ms) { steps.push(setTimeout(go, ms)); }); setTimeout(function () { armed = true; }, 4600); });
})();
</script>"""

# A helper or grade explanation written outside the app links to notes sections as web addresses of the page it was written
# against ("...#s2-2", with the text "Lec 1 §2.2 · ..."). A click writes "note:<lecture>:<id>" (or "doc:<the link text>", e.g. "Midterm 2 Preparation")
# into the hidden box of the Library page around this frame, which opens that lecture's notes at that section.
_LINKS = r"""<script>
(function () {
  var P = window.parent, lec = {};
  function art(a) { var m = /claude\.ai\/artifact\/([^#?\/]+)/.exec(a.getAttribute('href') || ''); return m && m[1]; }
  function lecOf(a) { var m = /\b(?:Lec(?:ture)?|Ch(?:apter)?)\s*(\d+)/i.exec(a.textContent || ''); return m && m[1]; }
  [].forEach.call(document.querySelectorAll('a[href]'), function (a) {
    var id = art(a), l = lecOf(a);
    if (id && l) lec[id] = l;
  });
  [].forEach.call(document.querySelectorAll('a[href]'), function (a) {
    var id = art(a);
    if (id) a.title = (lecOf(a) || lec[id]) ? 'open this section in your notes' : 'open this in the app';
  });
  function send(msg) {
    var inp = P.document.querySelector('.st-key-lib_link_sink input'); if (!inp) return;
    var set = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, msg + '|' + Date.now());
    inp.dispatchEvent(new P.Event('input', {bubbles: true}));
    inp.dispatchEvent(new P.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]'); if (!a) return;
    var id = art(a); if (!id) return;
    e.preventDefault(); e.stopPropagation();
    var hash = (a.getAttribute('href').split('#')[1] || ''), l = lecOf(a) || lec[id], txt = a.textContent || '';
    if (l) send('note:' + l + ':' + hash);
    else send('doc:' + txt.replace(/[|\u2197]/g, ' ').replace(/\s+/g, ' ').trim());     // another page of the course, by its name
  }, true);
})();
</script>"""

# In a grade explanation (and in a helper), a click on a problem card, a grader comment (its numbered badge is the comment's number in the grade
# report), the score tiles or the contents list writes "mark:p<problem>" or "mark:c<comment>" into the same hidden box: the
# Library page shows that page of the graded paper and marks the place on it.
_MARKS = r"""<script>
(function () {
  var P = window.parent;
  var css = document.createElement('style');
  css.textContent = 'section.card.rd-sel{outline:2px solid var(--hbeta,#1d6cb0);outline-offset:2px}.gc.rd-sel,div.part.rd-sel,div.partb.rd-sel{outline:2px solid var(--hbeta,#1d6cb0);outline-offset:1px}'
    + 'section.card,.gc,div.part,div.partb{cursor:pointer}';
  document.head.appendChild(css);
  [].forEach.call(document.querySelectorAll('section.card[id], .gc, div.part, div.partb'), function (el) { el.title = 'show this on your paper'; });
  function send(msg) {
    var inp = P.document.querySelector('.st-key-lib_link_sink input'); if (!inp) return;
    var set = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, msg + '|' + Date.now());
    inp.dispatchEvent(new P.Event('input', {bubbles: true}));
    inp.dispatchEvent(new P.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }
  function pick(card, gc, rubric, part) {
    var again = card && card.classList.contains('rd-sel');
    [].forEach.call(document.querySelectorAll('.rd-sel'), function (x) { x.classList.remove('rd-sel'); });
    if (part) part.classList.add('rd-sel'); else if (gc) gc.classList.add('rd-sel'); else if (card) card.classList.add('rd-sel');
    if (rubric && card && !again) {                               // a problem was picked: show its rubric
      var d = card.querySelector('details.rub'); if (d) d.open = true;
    }
  }
  document.addEventListener('click', function (e) {
    var t = e.target; if (!t.closest) return;
    var tile = t.closest('a[href^="#p"]');                       // score tile or contents entry of a problem
    if (tile) {
      var m = /^#p(\d+)$/.exec(tile.getAttribute('href'));
      if (m) { pick(document.getElementById('p' + m[1]), null, true); send('mark:p' + m[1]); }
      return;
    }
    if (t.closest('a, button, label, input, textarea, select')) return;
    var card = t.closest('section.card'), gc = t.closest('.gc');
    if (!card) return;
    var n = /^p(\d+)$/.exec(card.id || '');
    var part = t.closest('div.part, div.partb'), pl = part && part.querySelector('.pl');         // a lettered part (sub-problem) of a helper
    var letter = pl ? (pl.textContent || '').replace(/[^a-z]/gi, '').toLowerCase() : '';
    if (n && part && /^[a-z]$/.test(letter)) { pick(card, null, false, part); send('mark:p' + n[1] + letter); return; }
    var b = gc && gc.querySelector('.badge');
    if (gc && b) {         // a grader comment: its badge number, or (badges that are letters) its place among the page's comments
      var tx = b ? b.textContent.trim() : '';
      var num = /^\d+$/.test(tx) ? tx : String([].indexOf.call(document.querySelectorAll('.gc'), gc) + 1);
      pick(card, gc); send('mark:c' + num);
    }
    else if (n) { pick(card, null, !t.closest('summary')); send('mark:p' + n[1]); }   // a fold's own title toggles that fold itself
  });
})();
</script>"""

# The note's Self-check section is rebuilt from the same questions the course page Quiz tab uses: choose one option
# per question, nothing is marked until you finish, then the score (below 60% fails) and the explanation of each miss.
_QUIZ = """<style>
.qz-q{border:1px solid var(--line,#d8dce6);background:var(--panel,transparent);border-radius:12px;padding:14px 18px;margin:14px 0}
.qz-q .qz-t{font-weight:600;margin-bottom:4px}
.qz-q .qz-tag{font:500 11px ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;opacity:.6;margin-bottom:10px}
.qz-o{display:flex;flex-wrap:wrap;gap:10px}
.qz-o button{font:inherit;font-size:15px;padding:8px 16px;border-radius:10px;background:transparent;color:inherit;border:1px solid var(--line,#d8dce6);cursor:pointer}
.qz-o button:hover{border-color:var(--accent,#3646c7)}
.qz-o button.sel{border:2px solid var(--accent,#3646c7);background:var(--accent-soft,rgba(76,141,255,.2))}
.qz-o button.right{border-color:#2f9e5f;background:rgba(47,158,95,.16)}
.qz-o button.wrong{border-color:#d14343;background:rgba(209,67,67,.14)}
.qz-ex{margin-top:12px;padding:10px 14px;border-radius:8px;background:var(--accent-soft,rgba(127,127,127,.12))}
.qz-bar{display:flex;gap:12px;align-items:center;margin-top:8px}
.qz-go{font:inherit;padding:8px 18px;border-radius:10px;border:1px solid var(--accent,#3646c7);background:var(--accent,#3646c7);color:#fff;cursor:pointer}
.qz-score{display:flex;align-items:center;gap:14px;margin:8px 0}.qz-score b{font-size:1.8rem}
.qz-pill{border:1px solid currentColor;border-radius:999px;padding:1px 12px;font-size:.85rem}
</style>
<script>
(function () {
  var DATA = __DATA__, PASS = 60, chosen = {}, done = false;
  var h2 = [].slice.call(document.querySelectorAll('h2')).filter(function (h) { return /self-check|quiz/i.test(h.textContent); })[0];
  var sec = (document.getElementById('quiz') || (h2 && h2.closest('section')));
  if (!sec) return;
  [].slice.call(sec.children).forEach(function (c) { if (!/^H2$/.test(c.tagName) && !(c.tagName === 'P' && c === sec.querySelector('p'))) c.remove(); });
  var host = document.createElement('div'); sec.appendChild(host);
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  function tex(s) { return esc(s).replace(/\\$\\$([^$]+)\\$\\$/g, '\\\\[$1\\\\]').replace(/\\$([^$]+)\\$/g, '\\\\($1\\\\)'); }
  function right(q, i) { return chosen[i] === q.a; }
  function draw() {
    var h = '';
    DATA.forEach(function (q, i) {
      h += '<div class="qz-q"><div class="qz-t">' + (i + 1) + '. ' + tex(q.q) + '</div>' + (q.tag ? '<div class="qz-tag">' + esc(q.tag) + '</div>' : '') + '<div class="qz-o">';
      q.o.forEach(function (o, oi) {
        var c = chosen[i] === oi ? 'sel' : '';
        if (done) c = oi === q.a ? 'right' : (chosen[i] === oi ? 'wrong' : '');
        h += '<button type="button" class="' + c + '" data-q="' + i + '" data-o="' + oi + '"' + (done ? ' disabled' : '') + '>' + tex(o) + '</button>';
      });
      h += '</div>' + (done && !right(q, i) && q.e ? '<div class="qz-ex"><b>Explanation.</b> ' + tex(q.e) + '</div>' : '') + '</div>';
    });
    h += '<div class="qz-bar"><span id="qz-progress"></span>' + (done ? '<button class="qz-go" id="qz-again" type="button">Try Again</button>' : '<button class="qz-go" id="qz-finish" type="button">Finish And Score</button>') + '</div>';
    host.innerHTML = (done ? host.__score || '' : '') + h;
    var p = document.getElementById('qz-progress');
    if (p) p.textContent = Object.keys(chosen).length + ' of ' + DATA.length + ' answered. Nothing is marked until you finish.';
    if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([host]).catch(function () {});
  }
  host.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b) return;
    if (b.id === 'qz-finish') {
      var n = 0; DATA.forEach(function (q, i) { if (right(q, i)) n++; });
      var pct = Math.round(100 * n / DATA.length), lab = pct >= 80 ? 'Strong' : pct >= PASS ? 'Passed' : 'Failed';
      host.__score = '<div class="qz-score"><b>' + n + ' / ' + DATA.length + '</b><span>' + pct + '%</span><span class="qz-pill">' + lab + '</span></div>' + (pct < PASS ? '<p>Below ' + PASS + '% is a fail. Read the explanations and try again.</p>' : '');
      done = true; draw(); sec.scrollIntoView(); return;
    }
    if (b.id === 'qz-again') { chosen = {}; done = false; host.__score = ''; draw(); return; }
    if (b.dataset.q !== undefined && !done) { chosen[+b.dataset.q] = +b.dataset.o; draw(); }
  });
  draw();
})();
</script>"""


# Find (Ctrl+F) and zoom for a note shown in a frame: a small toolbar with magnifier icons (find, zoom out, zoom in) and a find bar.
_FIND = r"""<script>(function () {
if (window.__ffV1) return; window.__ffV1 = true;
var root = document.documentElement, bar, input, count, hits = [], cur = -1, timer = null, zoom = 1;
var KEY = 'rd-zoom:' + (document.title || 'note');
var css = document.createElement('style');
css.textContent = '.ff-tools,.ff-bar{position:fixed;z-index:2147483000;display:flex;align-items:center;gap:4px;background:#fff;color:#111;border:1px solid #9aa3b5;border-radius:10px;padding:4px 6px;box-shadow:0 3px 14px rgba(0,0,0,.22);font:13px system-ui,sans-serif}'
 + '.ff-tools{top:8px;right:14px;opacity:.55;transition:opacity .15s}.ff-tools:hover,.ff-tools.on{opacity:1}'
 + '.ff-bar{top:48px;right:14px;display:none;padding:6px 8px}'
 + '@media (prefers-color-scheme:dark){.ff-tools,.ff-bar{background:#1b2030;color:#e8eaf2;border-color:#3a4260}.ff-bar input{background:#0f1320;color:#e8eaf2;border-color:#3a4260}}'
 + '.ff-bar input{width:190px;font:inherit;padding:4px 7px;border:1px solid #9aa3b5;border-radius:6px;outline:none}'
 + '.ff-tools button,.ff-bar button{font:inherit;line-height:1;padding:4px 6px;border:1px solid transparent;border-radius:6px;background:transparent;color:inherit;cursor:pointer;display:flex;align-items:center}'
 + '.ff-tools button:hover,.ff-bar button:hover{background:rgba(120,130,160,.25)}.ff-tools svg{width:18px;height:18px}'
 + '.ff-count,.ff-pct{min-width:46px;text-align:center;opacity:.8;font-size:12px}'
 + 'mark.ff-hit{background:#ffe066;color:#111;border-radius:2px;padding:0}mark.ff-hit.ff-cur{background:#ff9f1a;outline:2px solid #ff9f1a}';
(document.head || root).appendChild(css);
function icon(sign) {
  var inner = sign === 'plus' ? '<path d="M8 11h6M11 8v6"/>' : sign === 'minus' ? '<path d="M8 11h6"/>' : '';
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>' + inner + '</svg>';
}
var tools = document.createElement('div'); tools.className = 'ff-tools';
tools.innerHTML = '<button type="button" data-a="find" title="find in this page (ctrl+f)">' + icon('') + '</button>'
  + '<button type="button" data-a="out" title="zoom out">' + icon('minus') + '</button><span class="ff-pct">100%</span>'
  + '<button type="button" data-a="in" title="zoom in">' + icon('plus') + '</button>';
root.appendChild(tools);
var pct = tools.querySelector('.ff-pct');
function setZoom(z) {
  zoom = Math.min(3, Math.max(0.5, Math.round(z * 10) / 10));
  document.body.style.zoom = zoom; pct.textContent = Math.round(zoom * 100) + '%';
  try { localStorage.setItem(KEY, String(zoom)); } catch (e) {}
}
try { var saved = parseFloat(localStorage.getItem(KEY)); if (saved) setZoom(saved); } catch (e) {}
tools.addEventListener('click', function (e) {
  var b = e.target.closest('button'); if (!b) return;
  if (b.dataset.a === 'in') setZoom(zoom + 0.1); else if (b.dataset.a === 'out') setZoom(zoom - 0.1); else openBar();
});
pct.addEventListener('dblclick', function () { setZoom(1); });
// The note's helper box (.tipbox) is placed in screen pixels, but a zoomed page also scales fixed boxes: scale the position back and keep the
// whole box inside the frame (it used to run past the right edge when the page was zoomed in).
(function () {
  var tb = null;
  function fix() {
    if (!tb) return;
    if (zoom === 1) { if (tb._m) { tb.style.maxWidth = ''; tb.style.width = ''; tb._m = 0; } return; }
    var l = parseFloat(tb.style.left), t = parseFloat(tb.style.top);
    if (isNaN(l) || isNaN(t)) return;
    var key = tb.style.left + '|' + tb.style.top + '|' + zoom; if (tb._k === key) return;
    tb.style.maxWidth = Math.max(120, Math.min(340, (window.innerWidth - 24) / zoom)) + 'px'; tb.style.width = 'max-content'; tb._m = 1;
    var x = l / zoom, y = t / zoom;
    tb.style.left = x + 'px'; tb.style.top = y + 'px';
    var r = tb.getBoundingClientRect(), dx = 0, dy = 0;
    if (r.right > window.innerWidth - 8) dx = window.innerWidth - 8 - r.right;
    if (r.left + dx < 8) dx = 8 - r.left;
    if (r.bottom > window.innerHeight - 8) dy = window.innerHeight - 8 - r.bottom;
    if (r.top + dy < 8) dy = 8 - r.top;
    if (dx) tb.style.left = (x + dx / zoom) + 'px';
    if (dy) tb.style.top = (y + dy / zoom) + 'px';
    tb._k = tb.style.left + '|' + tb.style.top + '|' + zoom;
  }
  setInterval(function () {
    if (tb) return;
    tb = document.querySelector('.tipbox');
    if (tb) new MutationObserver(fix).observe(tb, {attributes: true, attributeFilter: ['style']});
  }, 400);
})();
document.addEventListener('wheel', function (e) { if (e.ctrlKey) { e.preventDefault(); setZoom(zoom + (e.deltaY < 0 ? 0.1 : -0.1)); } }, {passive: false});
function build() {
  if (bar) return;
  bar = document.createElement('div'); bar.className = 'ff-bar';
  bar.innerHTML = '<input type="text" placeholder="Find in this page" aria-label="Find"><span class="ff-count"></span>'
    + '<button type="button" data-d="-1" title="previous (shift+enter)">&#9650;</button><button type="button" data-d="1" title="next (enter)">&#9660;</button>'
    + '<button type="button" data-x="1" title="close (esc)">&#10005;</button>';
  root.appendChild(bar); input = bar.querySelector('input'); count = bar.querySelector('.ff-count');
  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 120); });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); step(e.shiftKey ? -1 : 1); } else if (e.key === 'Escape') { e.preventDefault(); closeBar(); }
    e.stopPropagation();
  });
  bar.addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; if (b.dataset.x) closeBar(); else step(+b.dataset.d); });
}
function clear() {
  document.querySelectorAll('mark.ff-hit').forEach(function (m) { var p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); });
  hits = []; cur = -1;
}
function run() {
  clear(); var q = input.value;
  if (!q) { count.textContent = ''; return; }
  var needle = q.toLowerCase();
  var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode: function (n) {
    var p = n.parentElement;
    if (!p || p.closest('script,style,noscript,mjx-container,textarea,select,option,svg,canvas')) return NodeFilter.FILTER_REJECT;
    return n.nodeValue && n.nodeValue.toLowerCase().indexOf(needle) >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
  }});
  var nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(function (n) {
    var text = n.nodeValue, low = text.toLowerCase(), i = 0, at, frag = document.createDocumentFragment();
    while ((at = low.indexOf(needle, i)) >= 0) {
      if (at > i) frag.appendChild(document.createTextNode(text.slice(i, at)));
      var m = document.createElement('mark'); m.className = 'ff-hit'; m.textContent = text.slice(at, at + needle.length); frag.appendChild(m); i = at + needle.length;
    }
    if (i < text.length) frag.appendChild(document.createTextNode(text.slice(i)));
    n.parentNode.replaceChild(frag, n);
  });
  hits = Array.prototype.filter.call(document.querySelectorAll('mark.ff-hit'), function (m) { return !m.closest('[hidden]'); });
  if (!hits.length) { count.textContent = 'No matches'; return; }
  step(1, true);
}
function step(d, first) {
  if (!hits.length) return;
  if (cur >= 0 && hits[cur]) hits[cur].classList.remove('ff-cur');
  cur = first ? 0 : (cur + d + hits.length) % hits.length;
  var m = hits[cur]; m.classList.add('ff-cur');
  var det = m.closest('details'); while (det) { det.open = true; det = det.parentElement && det.parentElement.closest('details'); }
  m.scrollIntoView({block: 'center', behavior: 'smooth'});
  count.textContent = (cur + 1) + ' of ' + hits.length;
}
function openBar() { build(); bar.style.display = 'flex'; tools.classList.add('on'); input.focus(); input.select(); if (input.value) run(); }
function closeBar() { clear(); if (bar) bar.style.display = 'none'; tools.classList.remove('on'); }
document.addEventListener('keydown', function (e) {
  var isFind;
  try { isFind = window.parent.__keyIs ? window.parent.__keyIs(e, 'notes', 'find', 'ctrl+f') : ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'f'); }
  catch (err) { isFind = (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'f'; }
  if (isFind) { e.preventDefault(); openBar(); return; }
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
    var k = e.key.toLowerCase();
    if (k === 'f') { /* the find shortcut is set in Settings */ }
    else if (k === '=' || k === '+') { e.preventDefault(); setZoom(zoom + 0.1); }
    else if (k === '-') { e.preventDefault(); setZoom(zoom - 0.1); }
    else if (k === '0') { e.preventDefault(); setZoom(1); }
  }
});
window.addEventListener('message', function (e) { if (e.data && e.data.study === 'find-open') openBar(); });
})();</script>"""


def safe_html(text, goto=None, questions=None, errata_source=None, resume=None, links=False, marks=False, slides=None, esc_exit=False, anchor=None):
    """The note's HTML with the link guard added just before the closing body tag (or at the end). `goto` is the id of
    a section to scroll to once the page has loaded (the Exercises tab opens the page at #exercises). `questions` (the
    app's question dicts) replace the note's own Self-check, so the note and the course Quiz tab agree."""
    script = _SCRIPT + _FIND + _F11
    if links:
        script += _LINKS
    if marks:
        script += _MARKS
    if slides:                                           # the id of this note: its slide numbers open the lecture slides (Note Reader)
        script += _SLIDES.replace("__CFG__", str(slides)) + _EQSRC.replace("__CFG__", str(slides))
    if anchor:                                           # "full" or "win": which mode of the Note Reader this copy of the note is shown in
        script += _ANCHOR.replace("__MODE__", str(anchor))
    if esc_exit:
        script += _ESC
    if errata_source:
        script += _ERRATA.replace("__SRC__", errata_source)
    if questions:
        data = [{"q": q["q"], "o": q["o"], "a": q["a"], "e": q.get("e", ""), "tag": q.get("tag", "")}
                for q in questions if q.get("kind") == "mc"]
        script += _QUIZ.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if goto:
        script += ("<script>window.addEventListener('load', function () { var go = function () { var t = document.getElementById("
                   + repr(goto) + "); if (t) { var d = t.tagName === 'DETAILS' ? t : t.closest('details'); if (d) d.open = true; t.scrollIntoView({block: 'start'}); } }; go(); setTimeout(go, 400); setTimeout(go, 1200); });</script>")
    if resume:                                           # reading position: saved while scrolling, restored when the note is opened again
        script += ("<script>(function () { var K = 'rd-pos:' + (document.title || 'note') + ':' + " + repr(str(resume)) + ", t = null;"
                   " window.addEventListener('scroll', function () { clearTimeout(t); t = setTimeout(function () {"
                   " try { localStorage.setItem(K, String(Math.round(window.scrollY))); } catch (e) {} }, 300); });"
                   " window.addEventListener('load', function () { setTimeout(function () {"
                   " try { var y = parseFloat(localStorage.getItem(K)); if (y > 0) window.scrollTo(0, y); } catch (e) {} }, 1700); }); })();</script>")
    low = text.lower()
    i = low.rfind("</body>")
    return text + script if i < 0 else text[:i] + script + text[i:]
