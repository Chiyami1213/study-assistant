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


def safe_html(text):
    """The note's HTML with the link guard added just before the closing body tag (or at the end)."""
    low = text.lower()
    i = low.rfind("</body>")
    return text + _SCRIPT if i < 0 else text[:i] + _SCRIPT + text[i:]
