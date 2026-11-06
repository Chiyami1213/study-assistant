"""Claude chat for the Note Builder (Anthropic API). The key comes from ANTHROPIC_API_KEY or from Settings."""
import base64
import os

import settings

MODEL = "claude-sonnet-5-5"

SYSTEM = """You help a graduate student build their own study notes inside an app called Study Assistant (Note Builder).
The notes have two tabs, Notes and Exercises, written in Markdown with LaTeX math ($...$ inline, $$...$$ display).
When the student asks for content, give it ready to paste: clear headings, short bullets, equations in LaTeX,
worked steps for derivations. When they ask for an interactive note, reply with ONE complete self-contained HTML
document (inline CSS and JavaScript, MathJax from the jsdelivr CDN with \( \) for inline math, step-through derivations,
sliders or toggles where they help) inside a single ```html code block. Do not use external images.
Keep replies focused; ask one short question if the request is unclear.
"""


def api_key():
    return os.environ.get("ANTHROPIC_API_KEY") or settings.get_api_key()


def available():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(api_key())


def _context(note, reference):
    parts = [f"Current note title: {note['title']}"]
    if reference:
        parts.append(f"The student is reading: {reference}")
    for label, field in (("Notes tab", "notes"), ("Exercises tab", "exercises")):
        text = (note.get(field) or "").strip()
        if text:
            parts.append(f"--- {label} so far ---\n{text[:12000]}")
    return "\n\n".join(parts)


def stream_reply(history, note, reference=None, page_png=None):
    """Yield text chunks of Claude's reply. `history` is [{'role', 'content'}] ending with the user's message;
    `page_png` (bytes) is attached to that last message when given."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key())
    messages = [dict(m) for m in history]
    if page_png and messages and messages[-1]["role"] == "user":
        img = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                           "data": base64.b64encode(page_png).decode()}}
        messages[-1] = {"role": "user", "content": [img, {"type": "text", "text": messages[-1]["content"]}]}
    system = SYSTEM + "\n\n" + _context(note, reference)
    with client.messages.stream(model=MODEL, max_tokens=16000, system=system, messages=messages) as stream:
        for text in stream.text_stream:
            yield text
