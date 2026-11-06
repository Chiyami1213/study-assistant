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


def safe_html(text, goto=None, questions=None, errata_source=None):
    """The note's HTML with the link guard added just before the closing body tag (or at the end). `goto` is the id of
    a section to scroll to once the page has loaded (the Exercises tab opens the page at #exercises). `questions` (the
    app's question dicts) replace the note's own Self-check, so the note and the course Quiz tab agree."""
    script = _SCRIPT
    if errata_source:
        script += _ERRATA.replace("__SRC__", errata_source)
    if questions:
        data = [{"q": q["q"], "o": q["o"], "a": q["a"], "e": q.get("e", ""), "tag": q.get("tag", "")}
                for q in questions if q.get("kind") == "mc"]
        script += _QUIZ.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if goto:
        script += ("<script>window.addEventListener('load', function () { var go = function () { var t = document.getElementById("
                   + repr(goto) + "); if (t) { var d = t.tagName === 'DETAILS' ? t : t.closest('details'); if (d) d.open = true; t.scrollIntoView({block: 'start'}); } }; go(); setTimeout(go, 400); setTimeout(go, 1200); });</script>")
    low = text.lower()
    i = low.rfind("</body>")
    return text + script if i < 0 else text[:i] + script + text[i:]
