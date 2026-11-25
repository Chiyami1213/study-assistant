"""The other two parts of a study guide's quiz, read from the page so the course Quiz tab can run them: the speed round and the guided numerical practice. PURE (no Streamlit, no database).

A guide's Quiz has three parts (see CLAUDE.md): (1) conceptual questions (`quizzes.parse`), (2) a speed round: `var BANK=[[question, [options], index of the right one, explanation], ...]` with `N=8,LIMIT=90`
(8 questions drawn from the bank, 90 seconds), and (3) guided numerical practice: the worked examples `ex-P1`, `ex-P2` of `<section id="gpractice">`, whose steps are in the page's `window.GD_DATA` as
`{"id": "P1", "steps": [{"tag", "q", "o": [[option, 1 or 0, reason], ...], "done", "plain"}], "final"}`. Each step becomes one multiple-choice question; the reason of the option chosen is shown as feedback."""
import json
import re

from study import quizzes

_DEC = json.JSONDecoder()


def _arrays_after(text, marker):
    """Every JSON array that follows `marker` in the page, as a list of lists. `window.GD_DATA=[...]` and `window.GD_DATA=(window.GD_DATA||[]).concat([...])` are both read."""
    out = []
    for m in re.finditer(re.escape(marker) + r"\s*(?:\(\s*window\.GD_DATA\s*\|\|\s*\[\s*\]\s*\)\s*\.concat\(\s*)?(?=\[)", text):
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
    arrays = _arrays_after(html_text, "var BANK=")
    if not arrays:
        return None
    qs = []
    for item in arrays[0]:
        q = quizzes._question(item, defs)
        if q and q["kind"] == "mc" and q.get("a") is not None:
            qs.append({**q, "tag": "Speed Round"})
    if not qs:
        return None
    m = re.search(r"\bN\s*=\s*(\d+)\s*,\s*LIMIT\s*=\s*(\d+)", html_text)
    n, limit = (int(m.group(1)), int(m.group(2))) if m else (8, 90)
    return {"questions": qs, "n": min(n, len(qs)), "limit": limit}


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
    """[{"id", "title", "problem", "questions", "final"}] for the guided numerical practice of the page (the examples of `gpractice`, ids that start with P), in page order."""
    section = re.search(r'<section[^>]*id="gpractice"[^>]*>(.*?)</section>', html_text, re.S)
    if not section:
        return []
    wanted = re.findall(r'<details[^>]*id="ex-([^"]+)"', section.group(1))
    data = {}
    for arr in _arrays_after(html_text, "GD_DATA="):
        for ex in arr:
            if isinstance(ex, dict) and "steps" in ex:
                data[str(ex.get("id"))] = ex
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
