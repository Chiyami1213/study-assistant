"""An HTML study guide for a native web view: the same page the classic reader shows (`study/htmlnotes.safe_html`: the app's theme, the link guard, the guide's quiz questions), with the highlights kept inside the
stored page like in the classic reader (`study/hlstore.py`), but reported through Qt WebChannel instead of the hidden box of the web page.
What the classic reader gets from its parent page and this one does not: the links between windows (slides of a lecture, the source of an equation in the textbook) and the errata marks on a PDF."""
import json
import random

from PySide6.QtCore import QObject, Slot

from study import hlstore, htmlnotes, quizrun

_SEED = random.randint(1, 10 ** 9)           # the order of the quiz questions: the same all session, another next time

_HL = r"""<script src="qrc:///qtwebchannel/qwebchannel.js"></script><script>
(function () {
  var BOOK = "__BOOK__", RESTORED = __RESTORED__, KEYRE = /^sg:.*:highlights$/, ls;
  try { ls = window.localStorage; } catch (e) { return; }
  var setItem = Storage.prototype.setItem, removeItem = Storage.prototype.removeItem, timer = null, pending = null, sent = null, restored = null, bridge = null;
  if (RESTORED && RESTORED.key && typeof RESTORED.value === 'string') { setItem.call(ls, RESTORED.key, RESTORED.value); restored = RESTORED.value; sent = RESTORED.value; }
  try { if (window.qt && qt.webChannelTransport && window.QWebChannel) new QWebChannel(qt.webChannelTransport, function (ch) { bridge = ch.objects.bridge; }); } catch (e) {}
  function b64(s) { return btoa(unescape(encodeURIComponent(s))); }
  function send(key, value) {
    if (value === sent) return; sent = value;
    (function go() { if (bridge) bridge.highlight(BOOK, b64(JSON.stringify({key: key, value: value}))); else setTimeout(go, 100); })();
  }
  function flush() { if (pending === null) return; var k = pending; pending = null; clearTimeout(timer); var v = null; try { v = ls.getItem(k); } catch (e) {} send(k, v); }
  function later(k) { pending = k; clearTimeout(timer); timer = setTimeout(flush, 400); }
  Storage.prototype.setItem = function (k, v) { setItem.apply(this, arguments); if (this === ls && KEYRE.test(String(k))) later(String(k)); };
  Storage.prototype.removeItem = function (k) { removeItem.apply(this, arguments); if (this === ls && KEYRE.test(String(k))) later(String(k)); };
  window.addEventListener('pagehide', flush);
})();
</script>"""


class HighlightBridge(QObject):
    """The page of a guide tells Python what was highlighted; it is kept inside the stored page."""

    @Slot(str, str)
    def highlight(self, book_id, b64):
        hlstore.handle_message(f"hl:{book_id}:{b64}|0")


def note_html(book, text, section=None, anchor="win"):
    """The page of a note of the Library as the native reader shows it, opened at `section`."""
    clean, saved = hlstore.split(text)
    try:
        hlstore.mirror(book["id"], saved)
    except OSError:
        pass
    own_quiz = 'id="qBox"' in clean                                         # a note with its own quiz script runs it as it is
    questions = None if own_quiz else quizrun.book_questions(book, _SEED)
    page = htmlnotes.safe_html(clean, section, questions=questions, anchor=anchor)
    snippet = _HL.replace("__BOOK__", str(int(book["id"]))).replace("__RESTORED__", json.dumps(saved).replace("</", "<\\/") if saved else "null")
    return htmlnotes._early(page, snippet)
