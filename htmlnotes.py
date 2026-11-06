"""Shows Claude-generated HTML notes inside the app without their in-page links navigating the frame."""

# srcdoc frames resolve "#section" links against the app's own address, so a click would load the whole app
# inside the note. This script scrolls to the target instead (the note's own handlers still run).
_SCRIPT = """<script>
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a[href^="#"]');
  if (!a) return;
  e.preventDefault();
  var id = decodeURIComponent(a.getAttribute('href').slice(1));
  var t = id ? (document.getElementById(id) || document.getElementsByName(id)[0]) : document.body;
  if (t && t.scrollIntoView) t.scrollIntoView({behavior: 'smooth', block: 'start'});
}, true);
</script>"""


def safe_html(text, goto=None):
    """The note's HTML with the link guard added just before the closing body tag (or at the end). `goto` is the id of
    a section to scroll to once the page has loaded (the Exercises tab opens the page at #exercises)."""
    script = _SCRIPT
    if goto:
        script += ("<script>window.addEventListener('load', function () { var go = function () { var t = document.getElementById("
                   + repr(goto) + "); if (t) t.scrollIntoView({block: 'start'}); }; go(); setTimeout(go, 400); setTimeout(go, 1200); });</script>")
    low = text.lower()
    i = low.rfind("</body>")
    return text + script if i < 0 else text[:i] + script + text[i:]
