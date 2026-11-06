"""A chapter's quiz as one self-contained HTML page (File page export), in the look of the notes.

Same rules as the app: choose one option per question, nothing is marked until you finish, then the score, pass or fail
(below 60% fails) and the explanation for every question that was missed. The page needs only a browser."""
import html as _html
import json

import outline

PASS = 60

_CSS = """
.q{border:1px solid var(--line);background:var(--panel);border-radius:12px;padding:16px 20px;margin:16px 0}
.q .qt{font-weight:600;margin-bottom:4px}
.q .tag{font:500 11px "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
.opts{display:flex;flex-wrap:wrap;gap:10px}
.opts button{font-size:1rem;padding:8px 16px;border-radius:10px;background:transparent}
.opts button.sel{border-color:var(--accent);background:var(--soft)}
.opts button.right{border-color:#2f9e5f;background:rgba(47,158,95,.16)}
.opts button.wrong{border-color:#d14343;background:rgba(209,67,67,.14)}
.opts button:disabled{cursor:default}
.ex{margin-top:12px;padding:10px 14px;border-radius:8px;background:var(--soft)}
.score{display:flex;align-items:center;gap:16px;margin:22px 0 6px}
.score b{font-size:2rem}
.pill{border:1px solid var(--line);border-radius:999px;padding:2px 14px;font-size:.85rem}
.pill.pass{border-color:#d9a21b;color:#d9a21b}.pill.strong{border-color:#2f9e5f;color:#2f9e5f}.pill.fail{border-color:#d14343;color:#d14343}
.bar{position:sticky;bottom:0;background:var(--bg);padding:12px 0;border-top:1px solid var(--line);display:flex;gap:12px;align-items:center}
button.go{background:var(--accent);color:#fff;border-color:var(--accent)}
"""

_JS = """
var DATA = __DATA__, PASS = __PASS__;
var chosen = {}, done = false;
var root = document.getElementById('quiz');
function typeset(el) { if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([el]).catch(function () {}); }
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
function draw() {
  root.innerHTML = '';
  DATA.questions.forEach(function (q, qi) {
    var d = document.createElement('div'); d.className = 'q';
    var h = '<div class="qt">' + (qi + 1) + '. ' + esc(q.q) + '</div>' + (q.tag ? '<div class="tag">' + esc(q.tag) + '</div>' : '');
    h += '<div class="opts">';
    if (q.o.length) q.o.forEach(function (o, oi) {
      var cls = chosen[qi] === oi ? 'sel' : '';
      if (done) cls = oi === q.a ? 'right' : (chosen[qi] === oi ? 'wrong' : '');
      h += '<button type="button" class="' + cls + '" data-q="' + qi + '" data-o="' + oi + '"' + (done ? ' disabled' : '') + '>' + esc(o) + '</button>';
    });
    else {
      h += '<button type="button" class="' + (chosen[qi] === 1 ? 'sel' : '') + '" data-q="' + qi + '" data-o="1"' + (done ? ' disabled' : '') + '>I know this</button>' +
           '<button type="button" class="' + (chosen[qi] === 0 ? 'sel' : '') + '" data-q="' + qi + '" data-o="0"' + (done ? ' disabled' : '') + '>Not sure</button>';
    }
    h += '</div>';
    if (done && !isRight(q, qi) && q.e) h += '<div class="ex"><b>Explanation.</b> ' + esc(q.e) + '</div>';
    d.innerHTML = h; root.appendChild(d);
  });
  typeset(root);
}
function isRight(q, qi) { return q.o.length ? chosen[qi] === q.a : chosen[qi] === 1; }
root.addEventListener('click', function (e) {
  var b = e.target.closest('button[data-q]'); if (!b || done) return;
  chosen[+b.dataset.q] = +b.dataset.o; draw(); refresh();
});
function refresh() {
  var n = Object.keys(chosen).length;
  document.getElementById('progress').textContent = n + ' of ' + DATA.questions.length + ' answered. Nothing is marked until you finish.';
}
document.getElementById('finish').onclick = function () {
  var right = 0; DATA.questions.forEach(function (q, qi) { if (isRight(q, qi)) right++; });
  var total = DATA.questions.length, pct = Math.round(100 * right / total); done = true;
  var label = pct >= 80 ? ['Strong', 'strong'] : pct >= PASS ? ['Passed', 'pass'] : ['Failed', 'fail'];
  document.getElementById('result').innerHTML = '<div class="score"><b>' + right + ' / ' + total + '</b><span>' + pct + '%</span><span class="pill ' + label[1] + '">' + label[0] + '</span></div>' +
    (pct < PASS ? '<p>Below ' + PASS + '% is a fail. Read the explanations, then try again.</p>' : '');
  document.getElementById('finish').hidden = true; document.getElementById('again').hidden = false;
  draw(); window.scrollTo({top: 0, behavior: 'smooth'});
};
document.getElementById('again').onclick = function () { location.reload(); };
draw(); refresh();
"""


def build(title, questions):
    """The quiz page. `questions` are the app's question dicts: kind, q, o, a, e, tag (math written as $...$)."""
    data = {"title": title, "questions": [
        {"q": q["q"], "o": q["o"] if q["kind"] == "mc" else [], "a": q["a"] if q["kind"] == "mc" else None,
         "e": q.get("e", ""), "tag": q.get("tag", "")} for q in questions]}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    body = (f'<div id="result"></div><div id="quiz"></div>'
            f'<div class="bar"><span id="progress"></span><button class="go" id="finish" type="button">Finish And Score</button>'
            f'<button id="again" type="button" hidden>Try Again</button></div>')
    page = outline.page(f"{title}: Quiz", body, "Quiz")
    page = page.replace("<style>", "<style>" + _CSS, 1)
    # the quiz writes math as $...$, so the page's MathJax is told to read those
    page = page.replace("inlineMath:[[String.fromCharCode(92)+'(',String.fromCharCode(92)+')']]",
                        "inlineMath:[['$','$'],[String.fromCharCode(92)+'(',String.fromCharCode(92)+')']]")
    start = page.index("<script>\ndocument.querySelectorAll('.deriv')")
    end = page.index("</script>", start) + len("</script>")
    return page[:start] + "<script>" + _JS.replace("__DATA__", payload).replace("__PASS__", str(PASS)) + "</script>" + page[end:]
