"""The other two parts of a study guide's quiz, read from the page so the course Quiz tab can run them: the speed round and the guided numerical practice. PURE (no Streamlit, no database).

A guide's Quiz has three parts (see CLAUDE.md): (1) conceptual questions (`quizzes.parse`), (2) a speed round: `var BANK=[[question, [options], index of the right one, explanation], ...]` with `N=8,LIMIT=90`
(8 questions drawn from the bank, 90 seconds), and (3) guided numerical practice: the worked examples `ex-P1`, `ex-P2` of `<section id="gpractice">`, whose steps are in the page's `window.GD_DATA` as
`{"id": "P1", "steps": [{"tag", "q", "o": [[option, 1 or 0, reason], ...], "done", "plain"}], "final"}`. Each step becomes one multiple-choice question; the reason of the option chosen is shown as feedback."""
import json
import re

from study import quizzes

_DEC = json.JSONDecoder()


_BANK = r"(?:var|let|const)\s+(?:[A-Za-z_]*BANK|SR_?(?:QS|QUESTIONS|DATA)|SPEED(?:_?[A-Za-z]+)?|speed(?:Bank|Qs|Questions|Data)?)\s*=\s*(?=\[)"
_GD = r"GD_DATA\s*=\s*(?:\(\s*window\.GD_DATA\s*\|\|\s*\[\s*\]\s*\)\s*\.concat\(\s*)?(?=\[)"


def _arrays_after(text, pattern):
    """Every JSON array that follows a match of `pattern` (a regex ending just before its `[`), as a list of lists. `window.GD_DATA=[...]` and `window.GD_DATA=(window.GD_DATA||[]).concat([...])` are both read."""
    out = []
    for m in re.finditer(pattern, text):
        i = m.end()
        try:
            value, _ = _DEC.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(value, list):
            out.append(value)
    return out


def speed(html_text, defs=None):
    """{"questions": [question dicts of the bank], "n": questions in a round, "limit": seconds} or None when the page has no speed round."""
    arrays = _arrays_after(html_text, _BANK)
    if not arrays:
        return None
    qs = []
    for item in arrays[0]:
        q = quizzes._question(item, defs)
        if q and q["kind"] == "mc" and q.get("a") is not None:
            qs.append({**q, "tag": "Speed Round"})
    if not qs:
        return None
    n_m, limit_m = re.search(r"\bN\s*=\s*(\d+)\b", html_text), re.search(r"\bLIMIT\s*=\s*(\d+)\b", html_text)
    n, limit = (int(n_m.group(1)) if n_m else 8), (int(limit_m.group(1)) if limit_m else 90)
    return {"questions": qs, "n": max(1, min(n, len(qs))), "limit": max(10, limit)}


def closed(html_text, defs=None):
    """The closed-book round of a page (`<div id="cbr">`): equations to write from memory. [{"kind": "open", "q": what to write, "e": the answer (equations and a note), "tag"}] in page order, or [].
    Each card is `<details class="cb"><summary>... <span class="cbq">Write: ...</span></summary><div class="cba">equation, note, tick box</div></details>`; the student ticks it in the page, here the
    student says "I Had It" or "Not Yet" like for any open question."""
    out = []
    for m in re.finditer(r'<details[^>]*class="cb"[^>]*>(.*?)</details>', html_text, re.S):
        body = m.group(1)
        q = re.search(r'<span class="cbq">(.*?)</span>\s*</summary>', body, re.S) or re.search(r"<summary>(.*?)</summary>", body, re.S)
        a = re.search(r'<div class="cba">(.*)', body, re.S)
        if not q:
            continue
        ans = re.sub(r'<label class="cbk">.*?</label>', "", a.group(1) if a else "", flags=re.S)
        ans = re.sub(r"</div>|<p\b", lambda x: "\n\n" + x.group(0), ans)               # an equation and the note under it are separate paragraphs
        text = quizzes._md(q.group(1), defs)
        if text:
            out.append({"kind": "open", "q": text, "o": [], "a": None, "e": quizzes._md(ans, defs), "tag": "Closed-Book Round"})
    return out


def _example_info(html_text, ex_id, defs):
    """(title, problem statement as markdown) of the practice example `ex-<id>`."""
    m = re.search(r'<details[^>]*id="ex-' + re.escape(str(ex_id)) + r'"[^>]*>\s*<summary>(.*?)</summary>(.*?)(?=<h5[^>]*class="exclear"|</details>)', html_text, re.S)
    if not m:
        return f"Practice {ex_id}", ""
    summary = re.sub(r'<span class="(?:exn|extag)">.*?</span>', "", m.group(1), flags=re.S)
    title = quizzes._md(re.sub(r"<[^>]+>", "", summary), defs).strip() or f"Practice {ex_id}"
    prob = re.search(r"<h5[^>]*>\s*Problem\s*</h5>(.*)", m.group(2), re.S)
    return title, quizzes._md(prob.group(1), defs) if prob else ""


def guided(html_text, defs=None):
    """[{"id", "title", "problem", "questions", "final"}] for the guided numerical practice of the page, in page order: the examples of the section `gpractice`; a guide with no such section but with
    guided examples in its notes (Guided mode) offers those instead."""
    data = {}
    for arr in _arrays_after(html_text, _GD):
        for ex in arr:
            if isinstance(ex, dict) and "steps" in ex:
                data[str(ex.get("id"))] = ex
    section = re.search(r'<section[^>]*id="gpractice"[^>]*>(.*?)</section>', html_text, re.S)
    if section:
        wanted = re.findall(r'<details[^>]*id="ex-([^"]+)"', section.group(1))
    else:
        wanted = [i for i in re.findall(r'<details[^>]*id="ex-([^"]+)"', html_text) if i in data]
    out = []
    for ex_id in wanted:
        ex = data.get(ex_id)
        if not ex:
            continue
        title, problem = _example_info(html_text, ex_id, defs)
        steps = ex["steps"]
        questions = []
        for i, s in enumerate(steps, 1):
            opts = s.get("o") or []
            right = next((k for k, o in enumerate(opts) if len(o) > 1 and o[1]), None)
            if right is None or len(opts) < 2:
                continue
            questions.append({"kind": "mc", "q": quizzes._md(s.get("q", ""), defs), "o": [quizzes._md(o[0], defs) for o in opts], "a": right,
                              "e": quizzes._md(opts[right][2], defs) if len(opts[right]) > 2 else "",
                              "ofb": [quizzes._md(o[2], defs) if len(o) > 2 else "" for o in opts],
                              "tag": f"Practice {ex_id.lstrip('P')} · {title} · Step {i} of {len(steps)} · {quizzes._md(s.get('tag', ''), defs)}".strip(" ·"),
                              "ctx": f"**{title}**  \n{problem}" if problem else f"**{title}**", "group": ex_id, "noshuffle": True})
        if questions:
            out.append({"id": ex_id, "title": title, "problem": problem, "questions": questions, "final": quizzes._md(ex.get("final", ""), defs)})
    return out
