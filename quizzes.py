"""Quiz questions taken from the Self-check sections of the Library's HTML notes.

Two shapes occur in the notes:
  * a JavaScript array of multiple-choice questions:  const Q=[ {q:'..',o:[..],a:1,e:'..'}, ... ]  or  [question, [options], answer, why]
  * <details class="q"><summary>1. question</summary><p>model answer</p></details>   (open questions, self-graded)
Each question comes out as {kind: "mc" | "open", q, o, a, e}, with TeX written for Streamlit ($...$)."""
import html as _html
import re

import macros


# ---------- a tolerant reader for JavaScript literals (arrays, objects, strings, templates, numbers) ----------
class _JS:
    def __init__(self, text, i):
        self.t, self.i = text, i

    def ws(self):
        t = self.t
        while self.i < len(t):
            if t[self.i].isspace():
                self.i += 1
            elif t.startswith("//", self.i):
                self.i = t.find("\n", self.i) if "\n" in t[self.i:] else len(t)
            elif t.startswith("/*", self.i):
                j = t.find("*/", self.i)
                self.i = len(t) if j < 0 else j + 2
            else:
                break

    def value(self):
        self.ws()
        c = self.t[self.i]
        if c == "[":
            return self.array()
        if c == "{":
            return self.obj()
        if c in "'\"":
            return self.string(c)
        if c == "`":
            return self.template(raw=False)
        m = re.compile(r"-?\d+(?:\.\d+)?").match(self.t, self.i)
        if m:
            self.i = m.end()
            return float(m.group()) if "." in m.group() else int(m.group())
        m = re.compile(r"[A-Za-z_$][\w$]*").match(self.t, self.i)
        if m:
            self.i = m.end()
            word = m.group()
            if self.t.startswith("`", self.i):                       # tagged template (Rw`...` keeps backslashes)
                return self.template(raw=True)
            return {"true": True, "false": False, "null": None}[word]
        raise ValueError("unexpected character")

    def array(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.t[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.t[self.i] == ",":
                self.i += 1

    def obj(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.t[self.i] == "}":
                self.i += 1
                return out
            if self.t[self.i] in "'\"":
                key = self.string(self.t[self.i])
            else:
                m = re.compile(r"[A-Za-z_$][\w$]*").match(self.t, self.i)
                if not m:
                    raise ValueError("bad key")
                key, self.i = m.group(), m.end()
            self.ws()
            if self.t[self.i] != ":":
                raise ValueError("expected :")
            self.i += 1
            out[key] = self.value()
            self.ws()
            if self.t[self.i] == ",":
                self.i += 1

    _ESC = {"n": "\n", "t": "\t", "r": "", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}

    def _cooked(self, end):
        t, out = self.t, []
        while True:
            c = t[self.i]
            if c == end:
                self.i += 1
                return "".join(out)
            if c == "\\":
                n = t[self.i + 1]
                if n == "u":
                    if t[self.i + 2] == "{":
                        j = t.index("}", self.i)
                        out.append(chr(int(t[self.i + 3:j], 16)))
                        self.i = j + 1
                    else:
                        out.append(chr(int(t[self.i + 2:self.i + 6], 16)))
                        self.i += 6
                    continue
                out.append(self._ESC.get(n, n))
                self.i += 2
                continue
            out.append(c)
            self.i += 1

    def string(self, quote):
        self.i += 1
        return self._cooked(quote)

    def template(self, raw):
        self.i += 1
        if not raw:
            return self._cooked("`")
        t, out = self.t, []
        while True:
            c = t[self.i]
            if c == "`":
                self.i += 1
                return "".join(out)
            if c == "\\" and t[self.i + 1] in "`$":
                out.append(t[self.i + 1])
                self.i += 2
                continue
            out.append(c)
            self.i += 1


def _md(text, defs=None):
    """Display text for Streamlit: HTML tags removed, entities decoded, MathJax \\( \\) -> $ $, note macros expanded."""
    text = macros.expand(str(text), defs)
    text = re.sub(r"<br\s*/?>", "  \n", text)
    text = re.sub(r"</?(?:i|em)>", "*", text)
    text = re.sub(r"</?(?:b|strong)>", "**", text)
    text = re.sub(r"</?p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", text, flags=re.S)
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: "$$" + m.group(1).strip() + "$$", text, flags=re.S)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _question(item, defs=None):
    """One question from a parsed JavaScript item, or None if it is not a multiple-choice question."""
    if isinstance(item, dict):
        q, o, a, e = item.get("q"), item.get("o"), item.get("a"), item.get("e", "")
    elif isinstance(item, list) and len(item) >= 3:
        q, o, a, e = item[0], item[1], item[2], (item[3] if len(item) > 3 else "")
    else:
        return None
    if not (isinstance(q, str) and isinstance(o, list) and o and all(isinstance(x, str) for x in o)
            and isinstance(a, int) and 0 <= a < len(o)):
        return None
    return {"kind": "mc", "q": _md(q, defs), "o": [_md(x, defs) for x in o], "a": a, "e": _md(e or "", defs)}


def _array_questions(html_text):
    best, defs = [], macros.from_html(html_text)
    for m in re.finditer(r"(?:const|let|var)\s+(?:Q|QUIZ|quiz\w*|questions\w*|qs)\s*=\s*\[", html_text):
        try:
            items = _JS(html_text, m.end() - 1).value()
        except (ValueError, IndexError, KeyError):
            continue
        found = [q for q in (_question(it, defs) for it in items) if q]
        if len(found) > len(best):
            best = found
    return best


def _open_questions(html_text):
    out, defs = [], macros.from_html(html_text)
    for m in re.finditer(r'<details class="q">\s*<summary>(.*?)</summary>(.*?)</details>', html_text, re.S):
        q = re.sub(r"^\s*\d+\.\s*", "", _md(m.group(1), defs))
        if q:
            out.append({"kind": "open", "q": q, "o": [], "a": None, "e": _md(m.group(2), defs)})
    return out


def parse(html_text):
    """The self-check questions of an HTML note ([] if it has none)."""
    return _array_questions(html_text) or _open_questions(html_text)
