"""Note Builder pages are self-contained interactive HTML. This module holds the standard format and builds the
starting page of a chapter: blank, or the outline of a Claude-generated HTML note from the Library.

A page has a title, then one <section> per topic: key idea, equations (MathJax), step-through derivations and a
place for an animation. Everything is plain HTML, CSS and JavaScript in one file, so Claude (or you) can edit it."""
import html as _html
import json
import re

import macros

CSS = """
:root{--bg:#fff;--panel:#f5f6fa;--ink:#161b29;--muted:#5b667c;--line:#d8dce6;--accent:#3646c7;--soft:#e4e7fa;--ok:#0c7f77}
@media (prefers-color-scheme:dark){:root{--bg:#0e1117;--panel:#161c2a;--ink:#e6e9f2;--muted:#9aa4b8;--line:#2a3247;--accent:#8e9cff;--soft:#1e2549;--ok:#3cc3b5}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:28px 22px 80px}
.eyebrow{font:500 12px "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font:600 2rem/1.2 Georgia,"Spectral",serif;margin:.3em 0 .6em}
h2{font:600 1.35rem/1.3 Georgia,"Spectral",serif;margin:2.2em 0 .4em;padding-top:1.1em;border-top:1px solid var(--line)}
h2 .num{display:block;font:500 12px "IBM Plex Mono",monospace;color:var(--muted);letter-spacing:.06em;margin-bottom:2px}
h3{font-size:1.05rem;margin:1.6em 0 .3em}
.key{background:var(--soft);border-left:4px solid var(--accent);border-radius:6px;padding:10px 14px;margin:1em 0}
.eq{overflow-x:auto;padding:4px 0}
.deriv,.demo,.example{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:12px 16px;margin:1em 0}
.deriv-head{font-weight:600;display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.deriv ol{margin:.6em 0 0;padding-left:1.3em}
.deriv li{margin:.5em 0}
.deriv li.hidden{display:none}
button{font:inherit;font-size:.85rem;padding:4px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--accent);color:var(--accent)}
.demo canvas{width:100%;height:220px;display:block;background:var(--bg);border:1px solid var(--line);border-radius:8px}
.demo label{font-size:.85rem;color:var(--muted);display:flex;gap:10px;align-items:center;margin-top:8px}
.demo input[type=range]{flex:1}
details.problem{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:1em 0;background:var(--panel)}
details.problem summary{cursor:pointer;font-weight:600}
.todo{color:var(--muted);font-style:italic}
"""

_MACROS = json.dumps({k: [v[0], v[1]] if v[1] else v[0] for k, v in macros.DEFAULT.items()})
MATHJAX = ("<script>window.MathJax={tex:{inlineMath:[[String.fromCharCode(92)+'(',String.fromCharCode(92)+')']],"
           "displayMath:[[String.fromCharCode(92)+'[',String.fromCharCode(92)+']']],macros:" + _MACROS + "},svg:{fontCache:'global'}};</script>\n"
           '<script src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js" async></script>')

# generic behaviour: "Step through" reveals a derivation one step at a time; the demo is a starting point for an animation
JS = """<script>
document.querySelectorAll('.deriv').forEach(function(d){
  var steps=[].slice.call(d.querySelectorAll('li')), i=steps.length, b=d.querySelector('button.step');
  if(!b) return;
  b.onclick=function(){
    if(i>=steps.length){i=0;steps.forEach(function(s){s.classList.add('hidden')});}
    steps[i].classList.remove('hidden'); i++; b.textContent=i>=steps.length?'Restart':'Next step';
  };
});
document.querySelectorAll('.demo').forEach(function(d){
  var c=d.querySelector('canvas'), s=d.querySelector('input'); if(!c||!s) return;
  var x=c.getContext('2d'), t=0, playing=true;
  function draw(){
    var w=c.width=c.clientWidth*devicePixelRatio, h=c.height=c.clientHeight*devicePixelRatio, a=+s.value;
    x.clearRect(0,0,w,h); x.strokeStyle=getComputedStyle(document.body).color; x.lineWidth=2*devicePixelRatio; x.beginPath();
    for(var px=0;px<w;px++){var u=px/w*6.28*2; var y=h/2-Math.sin(u*a+t)*h*0.3; px?x.lineTo(px,y):x.moveTo(px,y);} x.stroke();
    if(playing){t+=0.03; requestAnimationFrame(draw);}
  }
  s.oninput=function(){if(!playing)draw();}; draw();
  var b=d.querySelector('button.play'); if(b) b.onclick=function(){playing=!playing; b.textContent=playing?'Pause':'Play'; if(playing)draw();};
});
</script>"""


def page(title, body, eyebrow=""):
    """A complete interactive page in the standard format."""
    head = (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{_html.escape(title)}</title>\n<style>{CSS}</style>\n{MATHJAX}\n</head>\n')
    eb = f'<div class="eyebrow">{_html.escape(eyebrow)}</div>\n' if eyebrow else ""
    return f'{head}<body>\n<main>\n{eb}<h1>{_html.escape(title)}</h1>\n{body}\n</main>\n{JS}\n</body></html>\n'


def _section(i, name, subs):
    out = [f'<section id="s{i}">', f'<h2><span class="num">§{i}</span>{name}</h2>',
           '<div class="key"><b>Key idea.</b> <span class="todo">Write the main point of this section in a sentence or two.</span></div>',
           '<div class="eq">\\[ \\text{Equation} \\]</div>']
    for s in subs or ["Derivation"]:
        out.append(f'<div class="deriv"><div class="deriv-head"><span>{s}</span><button class="step">Step through</button></div>'
                   f'<ol><li>Step 1. <span class="todo">Start from what is known.</span></li>'
                   f'<li>Step 2. <span class="todo">Apply the next result.</span></li>'
                   f'<li>Step 3. <span class="todo">State the outcome.</span></li></ol></div>')
    out += ['<div class="demo"><b>Animation</b> <span class="todo">Replace this starter wave with an animation of the idea.</span>'
            '<canvas></canvas><label>Parameter <input type="range" min="1" max="6" step="0.1" value="2"> '
            '<button class="play">Pause</button></label></div>',
            '<div class="example"><b>Example.</b> <span class="todo">A worked example.</span></div>', "</section>"]
    return "\n".join(out)


def exercises_section(titles):
    """The Exercises section that closes every page (the Exercises tab scrolls to #exercises)."""
    problems = "\n".join(
        f'<details class="problem"><summary>{i}. {n}</summary><p><b>Problem.</b> <span class="todo">State it.</span></p>'
        f'<p><b>Solution.</b> <span class="todo">Work it out.</span></p></details>' for i, n in enumerate(titles, 1))
    return ('<section id="exercises">\n<h2><span class="num">Exercises</span>Practice problems</h2>\n'
            + (problems or '<p class="todo">Add problems here.</p>') + "\n</section>")


EXERCISE_WORDS = re.compile(r"exercise|self-check|practice|problem|quiz", re.I)


def exercises_id(page_html):
    """Id of the section the Exercises tab opens: our own #exercises section, else a section of the note whose
    heading looks like exercises (Self-check, Practice, Problems, Quiz). None if the page has no such section."""
    if 'id="exercises"' in page_html:
        return "exercises"
    for m in re.finditer(r'<section[^>]*id="([^"]+)"[^>]*>\s*<h2[^>]*>(.*?)</h2>', page_html, re.S):
        if EXERCISE_WORDS.search(re.sub(r"<[^>]+>", " ", m.group(2))):
            return m.group(1)
    return None


def with_exercises(page_html, titles):
    """A finished page with an Exercises section added at its end, unless it already has one (its own Self-check
    or Problems section is used instead)."""
    if exercises_id(page_html):
        return page_html
    block = exercises_section(titles)
    low = page_html.lower()
    for marker in ("</main>", "</body>"):
        i = low.rfind(marker)
        if i >= 0:
            return page_html[:i] + block + chr(10) + page_html[i:]
    return page_html + block


def build_page(title, sections, eyebrow=""):
    """One interactive page: a section per topic, then the Exercises section. `sections` is
    [(section title, [sub titles])] (already HTML-safe)."""
    body = "\n".join(_section(i, n, s) for i, (n, s) in enumerate(sections, 1))
    return page(title, body + "\n" + exercises_section([n for n, _ in sections]), eyebrow)


def blank_page(title):
    """The page of a new empty chapter."""
    return build_page(_html.escape(title, quote=False), [("First Topic", [])])


def _clean(text):
    """Heading text for HTML: tags removed, entities kept safe, MathJax \\( \\) left as it is."""
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return _html.escape(text, quote=False)


def parse_sections(html_text):
    """(title, eyebrow, sections) of a Claude-generated HTML note: its headings become the sections."""
    body = re.sub(r"<(script|style)\b.*?</\1>", "", html_text, flags=re.S | re.I)
    eyebrow = ""
    m = re.search(r'class="eyebrow"[^>]*>(.*?)</div>', body, re.S)
    if m:
        eyebrow = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    title, sections = "", []
    for m in re.finditer(r"<(h1|h2|h3|h4)[^>]*>(.*?)</\1>|<div class=\"deriv-head\".*?<b>(.*?)</b>", body, re.S):
        if m.group(1):
            inner = re.sub(r'<span class="num">.*?</span>', "", m.group(2), flags=re.S)
            kind, text = m.group(1), _clean(inner)
        else:
            kind, text = "deriv", _clean(m.group(3))
        if not text:
            continue
        if kind == "h1" and not title:
            title = text
        elif kind == "h2":
            sections.append((text, []))
        elif sections and kind in ("h3", "h4", "deriv"):
            sections[-1][1].append(("Derivation: " + text) if kind == "deriv" else text)
    return title, eyebrow, sections


def outline_from_html(html_text):
    """(title, page_html): a blank standard page whose sections are the headings of a Library HTML note."""
    title, eyebrow, sections = parse_sections(html_text)
    return _html.unescape(title) or "Untitled Chapter", build_page(title or "Untitled Chapter", sections, eyebrow)
