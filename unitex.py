r"""Math written with Unicode symbols (A → U†AU, ⟨x|ψ⟩, ħk/m, x²) becomes LaTeX ($A \to U^\dagger A U$, ...), so it is drawn like
the rest of the math: a dagger is a superscript, kets are real bras and kets, subscripts sit low. Text already inside
$...$ is left alone, and so is ordinary prose."""
import re

# Unicode symbol -> LaTeX (a trailing space where a word-like macro could run into the next letter)
SYMBOLS = {
    "⟩": r"\rangle ", "⟨": r"\langle ", "ħ": r"\hbar ", "−": "-", "√": r"\sqrt", "ω": r"\omega ", "ψ": r"\psi ",
    "†": r"^\dagger ", "Δ": r"\Delta ", "′": "'", "″": "''", "±": r"\pm ", "⊗": r"\otimes ", "𝟙": r"\mathbf{1}",
    "→": r"\to ", "δ": r"\delta ", "σ": r"\sigma ", "∫": r"\int ", "‖": r"\Vert ", "λ": r"\lambda ", "≪": r"\ll ",
    "≫": r"\gg ", "≥": r"\ge ", "≤": r"\le ", "≠": r"\ne ", "≡": r"\equiv ", "∝": r"\propto ", "∂": r"\partial ",
    "π": r"\pi ", "∞": r"\infty ", "⇔": r"\Leftrightarrow ", "β": r"\beta ", "α": r"\alpha ", "φ": r"\varphi ",
    "≈": r"\approx ", "×": r"\times ", "·": r"\cdot ", "θ": r"\theta ", "γ": r"\gamma ", "μ": r"\mu ", "ν": r"\nu ",
    "ρ": r"\rho ", "τ": r"\tau ", "ε": r"\varepsilon ", "κ": r"\kappa ", "η": r"\eta ", "χ": r"\chi ", "Ω": r"\Omega ",
    "Σ": r"\Sigma ", "Π": r"\Pi ", "Φ": r"\Phi ", "Ψ": r"\Psi ", "Γ": r"\Gamma ", "Λ": r"\Lambda ", "∇": r"\nabla ",
    "∈": r"\in ", "∀": r"\forall ", "∃": r"\exists ", "∑": r"\sum ", "∏": r"\prod ", "⊕": r"\oplus ", "⊥": r"\perp ",
    "∥": r"\parallel ", "⇒": r"\Rightarrow ", "←": r"\leftarrow ", "↔": r"\leftrightarrow ", "∼": r"\sim ",
    "ẑ": r"\hat{z}", "Ẋ": r"\dot{X}", "ẋ": r"\dot{x}", "ṗ": r"\dot{p}", "Ṗ": r"\dot{P}",
}
SUPER = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁺": "+",
         "⁻": "-", "ⁿ": "n", "ⁱ": "i"}
SUB = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9", "₊": "+",
       "₋": "-", "ₙ": "n", "ᵢ": "i", "ₓ": "x"}
MARKERS = set(SYMBOLS) | set(SUPER) | set(SUB) | {"̂"}
OPS = {"=", "+", "-", "−", "±", "×", "/", "∝", "≡", "≠", "≈", "≪", "≫", "≥", "≤", "⇔", "→", "⊗", "·", "<", ">", "∈", "⇒", "←", "↔"}
WORDS_OK = {"a", "I"}                                    # one-letter English words are not math unless next to an operator


def _core(token):
    return token.strip("?,.;:!")


def _is_marker(token):
    return any(c in MARKERS for c in token)


def _extendable(token, touches_operator):
    """May this neighbouring token join a math run? Operators and marked tokens always; plain letters and numbers
    only when they sit next to an operator (A → U†AU, x + a†)."""
    core = _core(token)
    if not core:
        return False
    if _is_marker(core) or core in OPS:
        return True
    if not touches_operator:
        return len(core) == 1 and core.isalpha() and core not in WORDS_OK
    return bool(re.fullmatch(r"[A-Za-z0-9.()|/^_{}+\-*]{1,10}", core)) and not re.fullmatch(r"[A-Za-z]{3,}", core)


def _tex(run):
    """LaTeX for one run of Unicode math."""
    run = re.sub(r"([A-Za-z])\u0302", r"\\hat{\1}", run)                      # x̂
    run = re.sub(r"√(\d+|[A-Za-z])", r"\\sqrt{\1}", run)                       # √2
    run = re.sub(r"√(\((?:[^()]|\([^()]*\))*\))", r"\\sqrt{\1}", run)          # √(1 + ...)
    run = re.sub("[" + "".join(SUPER) + "]+", lambda m: "^{" + "".join(SUPER[c] for c in m.group()) + "}", run)
    run = re.sub("[" + "".join(SUB) + "]+", lambda m: "_{" + "".join(SUB[c] for c in m.group()) + "}", run)
    run = "".join(SYMBOLS.get(c, c) for c in run)
    run = re.sub(r"\\sqrt(?![{])", r"\\sqrt ", run)
    return re.sub(r"\s+", " ", run).strip()


def _plain_to_tex(text):
    tokens = list(re.finditer(r"\S+", text))
    flags = [_is_marker(_core(t.group())) for t in tokens]
    if not any(flags):
        return text
    used = [False] * len(tokens)
    out, pos, i = [], 0, 0
    while i < len(tokens):
        if not flags[i] or used[i]:
            i += 1
            continue
        lo = hi = i
        while hi + 1 < len(tokens):                                   # extend right
            prev_op = _core(tokens[hi].group()) in OPS
            if _extendable(tokens[hi + 1].group(), prev_op):
                hi += 1
            else:
                break
        while lo > 0 and not used[lo - 1]:                            # extend left
            next_op = _core(tokens[lo].group()) in OPS
            if _extendable(tokens[lo - 1].group(), next_op):
                lo -= 1
            else:
                break
        while hi > lo and (_core(tokens[hi].group()) in OPS):         # a run does not end on a dangling operator
            hi -= 1
        while lo < hi and (_core(tokens[lo].group()) in OPS) and lo < i:
            lo += 1
        for k in range(lo, hi + 1):
            used[k] = True
        start, end = tokens[lo].start(), tokens[hi].end()
        run = text[start:end]
        trail = re.search(r"[?,.;:!]+$", run)                         # punctuation stays outside the math
        tail = trail.group() if trail else ""
        run = run[:len(run) - len(tail)] if tail else run
        out.append(text[pos:start])
        out.append("$" + _tex(run) + "$" + tail)
        pos = end
        i = hi + 1
    out.append(text[pos:])
    return "".join(out)


def convert(text):
    """Text with its Unicode math as LaTeX; math already between $ signs is untouched."""
    parts = re.split(r"(\$\$.+?\$\$|\$.+?\$)", text, flags=re.S)
    return "".join(p if p.startswith("$") else _plain_to_tex(p) for p in parts)
