"""The questions of a quiz as HTML for the native quiz page: the questions hold TeX math ($...$), which only a web view can draw (MathJax), so the cards are one small web page; everything around them is native.
PURE (no Qt): the page is built from a run (see study/quizrun.py) and a palette (qtui/theme.py)."""
import html
import json
import re

from study import quizrun

_MATH = re.compile(r"(\$\$.+?\$\$|\$.+?\$)", re.S)
MATHJAX = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"          # the same MathJax the study guides use


def md(text):
    """A question text (Markdown with TeX math) as HTML: bold, italics, code and line breaks; math is left for MathJax."""
    out = []
    for i, part in enumerate(_MATH.split(str(text or ""))):
        if i % 2:                                            # a formula
            out.append(html.escape(part, quote=False))
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.S)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s, flags=re.S)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\n\s*\n", "<br><br>", s)
        s = re.sub(r"  \n|\n", "<br>", s)
        out.append(s)
    return "".join(out)


CSS = """
:root { --bg:%(bg)s; --bg2:%(bg2)s; --text:%(text)s; --border:%(border)s; --card:%(card)s; --accent:%(accent)s; --primary:%(primary)s; --input:%(input)s; }
html, body { background: var(--bg); color: var(--text); font-family: "Segoe UI", "Source Sans 3", Arial, sans-serif; font-size: 15px; margin: 0; }
body { padding: 6px 4px 40px 4px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin: 0 0 14px 0; }
.qtext { font-size: 16px; line-height: 1.5; }
.tag { opacity: .65; font-size: 12px; margin: 4px 0 8px 0; }
.opts { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 6px 0; }
button { font: inherit; color: var(--text); background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 7px 14px; cursor: pointer; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { cursor: default; opacity: .8; }
.opt.chosen { border: 2px solid var(--accent); background: color-mix(in srgb, var(--accent) 22%%, var(--bg)); }
.opt.right { border: 2px solid #2e9e5b; background: rgba(46,158,91,.26); opacity: 1; }
.opt.wrong { border: 2px solid #d64545; background: rgba(214,69,69,.26); opacity: 1; }
.opt.gone { opacity: .4; text-decoration: line-through; }
.help { margin-top: 8px; display: flex; gap: 10px; }
.help button { border: none; background: transparent; opacity: .8; padding: 4px 8px; }
.ok { color: #2e9e5b; font-weight: 700; } .bad { color: #d64545; font-weight: 700; } .warn { color: #e0a030; }
.box { border-radius: 8px; padding: 8px 12px; margin: 8px 0; background: color-mix(in srgb, var(--accent) 14%%, var(--bg)); }
.box.w { background: rgba(224,160,48,.16); }
details { margin: 6px 0; } summary { cursor: pointer; opacity: .85; }
.ctx { background: var(--bg2); border-radius: 8px; padding: 6px 12px; }
.self button.primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.rev .qtext b.n { margin-right: 4px; }
mjx-container { max-width: 100%%; overflow-x: auto; overflow-y: hidden; }
code { background: var(--input); padding: 1px 5px; border-radius: 4px; }
"""

JS = """
var bridge = null;
function ready(cb) { if (bridge) cb(); else setTimeout(function () { ready(cb); }, 50); }
if (window.qt && qt.webChannelTransport) { new QWebChannel(qt.webChannelTransport, function (ch) { bridge = ch.objects.bridge; }); }
function send(kind, qi, arg) { ready(function () { bridge.act(kind, qi, arg || 0); }); }
function setCard(i, h) { var e = document.getElementById('q' + i); if (!e) return; e.innerHTML = h; if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([e]); }
"""


def page(colors, body):
    css = CSS % {k: colors[k] for k in ("bg", "bg2", "text", "border", "card", "accent", "primary", "input")}
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style>'
            f'<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
            f'<script>window.MathJax = {{tex: {{inlineMath: [["$","$"]], displayMath: [["$$","$$"]]}}, svg: {{fontCache: "global"}}}};</script>'
            f'<script async src="{MATHJAX}"></script><script>{JS}</script></head><body>{body}</body></html>')


def card_inner(run, qi, pos=None, first_of_group=None):
    """The inside of the card of question `qi` of the run, in the state it is in (what was answered, the notes and hint used)."""
    qs, order = run["qs"], run["order"]
    q, res = qs[qi], run["res"].get(qi) or {}
    if pos is None:
        pos = order.index(qi) + 1
    if first_of_group is None:
        first_of_group = pos == 1 or qs[order[pos - 2]].get("group") != q.get("group")
    mode, part = run.get("mode"), run.get("part", "concept")
    locked = mode == "each" and q["kind"] == "mc" and res.get("chosen") is not None
    out = []
    if q.get("ctx"):
        out.append(f'<details class="ctx"{" open" if first_of_group else ""}><summary>Problem</summary><div>{md(q["ctx"])}</div></details>')
    out.append(f'<div class="qtext"><b>{pos}.</b> {md(q["q"])}</div>')
    if q.get("tag"):
        out.append(f'<div class="tag">{md(q["tag"])}</div>')
    gone = quizrun._hint_for(q)[1] if q["kind"] == "mc" and res.get("hint") else None
    if q["kind"] == "mc":
        opts = []
        for oi, text in enumerate(q["o"]):
            cls = ["opt"]
            if locked:
                if oi == q["a"]:
                    cls.append("right")
                elif oi == res["chosen"]:
                    cls.append("wrong")
            elif res.get("chosen") == oi:
                cls.append("chosen")
            if oi == gone:
                cls.append("gone")
            mark = "✓  " if "right" in cls or ("chosen" in cls) else "✗  " if "wrong" in cls else ""
            dis = " disabled" if locked or oi == gone else ""
            opts.append(f'<button class="{" ".join(cls)}"{dis} onclick="send(\'pick\',{qi},{oi})">{mark}{md(text)}</button>')
        out.append('<div class="opts">' + "".join(opts) + "</div>")
    if locked:
        if res["chosen"] == q["a"]:
            out.append('<div class="ok">Correct.</div>')
        else:
            out.append(f'<div class="bad">Not correct.</div> The answer is: {md(q["o"][q["a"]])}')
            fb = (q.get("ofb") or [None] * 99)[res["chosen"]]
            if fb:
                out.append(f'<div class="box w">{md(fb)}</div>')
        if q.get("e"):
            out.append(f'<div class="box">{md(q["e"])}</div>')
    if q["kind"] != "mc":
        out.append(f'<details><summary>Show the model answer</summary><div class="box">{md(q.get("e") or "(The page gives no model answer.)")}</div></details>')
        got = res.get("got")
        out.append(f'<div class="self"><button class="{"primary" if got is True else ""}" onclick="send(\'grade\',{qi},1)">✓ I Had It</button> '
                   f'<button class="{"primary" if got is False else ""}" onclick="send(\'grade\',{qi},0)">✗ Not Yet</button></div>')
    if q["kind"] == "mc" and res.get("hint"):
        text = quizrun._hint_for(q)[0]
        out.append(f'<div class="warn"><b>Hint used. This is recorded.</b> {md(text)}</div>')
    if res.get("notes"):
        out.append('<div class="warn"><b>Notes used for this question. This is recorded.</b></div>')
    if part not in ("speed", "closed"):
        help_ = [f'<button{" disabled" if locked else ""} onclick="send(\'notes\',{qi})">{"Show Notes" if res.get("notes") else "Check Notes"}</button>']
        if q["kind"] == "mc":
            help_.append(f'<button{" disabled" if (locked or res.get("hint")) else ""} onclick="send(\'hint\',{qi})">Hint</button>')
        out.append('<div class="help">' + "".join(help_) + "</div>")
    return "".join(out)


def run_body(run):
    """All the cards of a running quiz (each in a div that `setCard` can refill)."""
    order = run["order"]
    return "".join(f'<div class="card" id="q{qi}">{card_inner(run, qi, pos)}</div>' for pos, qi in enumerate(order, 1))


def review_body(review):
    """A finished attempt: every question with its mark, the answer given and the explanation (the ones missed are open)."""
    out = []
    for pos, r in enumerate(review, 1):
        q = r.get("snap")
        if not q:
            continue
        mark = "✅" if r["ok"] else "❌"
        extras = (" 📖 <span class='warn'>notes used</span>" if r.get("notes") else "") + (" 💡 <span class='warn'>hint used</span>" if r.get("hint") else "")
        parts = [f'<div class="qtext">{mark} <b>{pos}.</b> {md(q["q"])}{extras}</div>']
        if q["kind"] == "mc":
            if not r["ok"]:
                chosen = q["o"][r["chosen"]] if r["chosen"] is not None else "(none)"
                parts.append(f"<div>Your answer: {md(chosen)}</div>")
            parts.append(f"<div>Answer: {md(q['o'][q['a']])}</div>")
            if not r["ok"] and r["chosen"] is not None and (q.get("ofb") or [None] * 99)[r["chosen"]]:
                parts.append(f'<div class="box w">{md(q["ofb"][r["chosen"]])}</div>')
        if q.get("e"):
            if not r["ok"]:
                parts.append(f'<div class="box">{md(q["e"])}</div>')
            else:
                parts.append(f'<details><summary>Explanation</summary><div class="box">{md(q["e"])}</div></details>')
        out.append('<div class="card rev">' + "".join(parts) + "</div>")
    return "".join(out) or "<p>The answers of this attempt were not saved, so only the score can be shown.</p>"


def js_card(qi, inner):
    """The script that refills a card."""
    return f"setCard({int(qi)}, {json.dumps(inner)});"
