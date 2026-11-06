r"""TeX macros of the HTML notes (\ket, \bra, \one ...), for places that render math with KaTeX instead of MathJax.

Each note defines its macros in its MathJax setup, for example  macros: {ket: ['\\lvert #1\\rangle', 1], one: '\\mathbf{1}'}.
KaTeX (the quiz, the errata list) does not know them and would show them in red, so they are expanded first."""
import re

# the macros the notes share; a note's own definitions are added on top of these
DEFAULT = {
    "ket": (r"\lvert #1\rangle", 1),
    "bra": (r"\langle #1\rvert", 1),
    "braket": (r"\langle #1\vert #2\rangle", 2),
    "mel": (r"\langle #1\vert #2\vert #3\rangle", 3),
    "ketbra": (r"\lvert #1\rangle\langle #2\rvert", 2),
    "one": (r"\mathbf{1}", 0),
}


def from_html(html_text):
    """DEFAULT plus the macros defined in the note's MathJax setup."""
    found = dict(DEFAULT)
    m = re.search(r"macros\s*:\s*\{", html_text or "")
    if m:
        from quizzes import _JS                      # the tolerant JavaScript-literal reader
        try:
            for name, value in _JS(html_text, m.end() - 1).value().items():
                if isinstance(value, str):
                    found[name] = (value, 0)
                elif isinstance(value, list) and value and isinstance(value[0], str):
                    found[name] = (value[0], int(value[1]) if len(value) > 1 else 0)
        except (ValueError, IndexError, KeyError):
            pass
    return found


def _args(text, i, n):
    """The n brace groups after position i, as ([contents], end position), or None if they are not there."""
    out = []
    for _ in range(n):
        while i < len(text) and text[i] == " ":
            i += 1
        if i >= len(text):
            return None
        if text[i] != "{":                           # TeX takes the next single token: \ket\psi, \bra\phi, \ket 0
            m = re.compile(r"\\[A-Za-z]+|\\.|[^\s\\{}]").match(text, i)
            if not m:
                return None
            out.append(m.group())
            i = m.end()
            continue
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        else:
            return None
        out.append(text[i + 1:j])
        i = j + 1
    return out, i


def expand(text, defs=None):
    """Replace each macro by its definition, so the TeX needs no macros."""
    defs = defs or DEFAULT
    for _ in range(4):                               # macros may use other macros
        before = text
        for name in sorted(defs, key=len, reverse=True):
            body, nargs = defs[name]
            pattern = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z])")
            out, pos = [], 0
            for m in pattern.finditer(text):
                if m.start() < pos:
                    continue
                got = _args(text, m.end(), nargs) if nargs else ([], m.end())
                if got is None:
                    continue
                args, end = got
                repl = body
                for k in range(nargs, 0, -1):
                    repl = repl.replace(f"#{k}", args[k - 1])
                out.append(text[pos:m.start()])
                out.append(repl + (" " if not nargs else ""))
                pos = end
            out.append(text[pos:])
            text = "".join(out)
        if text == before:
            break
    return text
