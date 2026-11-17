"""Reading an iCalendar (.ics) file or feed: what Canvas (Calendar Feed), Brightspace (Subscribe) and Google Calendar (Secret address in iCal format, or Export) give out. PURE: no database, no
Streamlit, no network. `parse(text, zone)` reads the events and to-dos; `occurrences(items, first, last, zone)` turns them (repeating ones too) into the plain items inside a window of time;
`classify` says whether an item is a task (a due date) or an event, and which category a task has; `match_course` finds the course an item is about.

All moments come out in UTC (an all-day item has `all_day` True and its date in the zone of the term)."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
WINDOWS_ZONES = {"Eastern Standard Time": "America/New_York", "Central Standard Time": "America/Chicago", "Mountain Standard Time": "America/Denver", "Pacific Standard Time": "America/Los_Angeles",
                 "Alaskan Standard Time": "America/Anchorage", "Hawaiian Standard Time": "Pacific/Honolulu", "UTC": "UTC", "GMT Standard Time": "Europe/London",
                 "W. Europe Standard Time": "Europe/Berlin", "Central Europe Standard Time": "Europe/Budapest", "China Standard Time": "Asia/Shanghai", "India Standard Time": "Asia/Kolkata",
                 "Tokyo Standard Time": "Asia/Tokyo", "AUS Eastern Standard Time": "Australia/Sydney"}
MAX_STEPS = 4000                                                           # a rule that would run on for ever stops here


@dataclass
class Item:
    uid: str
    kind: str                                                              # "event" or "todo"
    summary: str = ""
    start: object = None                                                   # an aware UTC datetime, or a date (all day)
    end: object = None
    due: object = None                                                     # to-dos: the due moment
    all_day: bool = False
    description: str = ""
    location: str = ""
    url: str = ""
    done: bool = False                                                     # a to-do marked completed
    rule: dict = field(default_factory=dict)                               # RRULE: {FREQ, INTERVAL, COUNT, UNTIL, BYDAY}
    exdates: list = field(default_factory=list)
    recurrence_id: object = None                                           # the original start of the one occurrence this item replaces
    tz: object = None                                                      # the zone the start was written in (the repeats keep their wall-clock time there)


def unfold(text):
    """The lines of the file, with the folded ones (a continuation starts with a space or a tab) joined."""
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _split(line):
    """(NAME, {PARAM: value}, value) of one content line, or None."""
    in_quote, cut, parts, last = False, -1, [], 0
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch == ";" and not in_quote and cut < 0:
            parts.append(line[last:i])
            last = i + 1
        elif ch == ":" and not in_quote:
            cut = i
            break
    if cut < 0:
        return None
    parts.append(line[last:cut])
    name, params = parts[0].upper(), {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return name, params, line[cut + 1:]


def _unescape(value):
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def _zone(name, default):
    if not name:
        return default
    name = WINDOWS_ZONES.get(name, name)
    try:
        return ZoneInfo(name)
    except Exception:
        return default


def parse_when(value, params, default_zone):
    """(moment, all_day, zone): a date for an all-day value, else an aware UTC datetime; the zone the value was written in (None when it was UTC)."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return date(int(value[:4]), int(value[4:6]), int(value[6:8])), True, None
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z?)", value)
    if not m:
        raise ValueError(f"not a date: {value}")
    y, mo, d, h, mi, s, z = m.groups()
    naive = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s or 0))
    if z:
        return naive.replace(tzinfo=UTC), False, None
    zone = _zone(params.get("TZID"), default_zone)
    return naive.replace(tzinfo=zone).astimezone(UTC), False, zone


def _rule(value):
    out = {}
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.upper()] = v
    return out


def parse(text, zone=UTC):
    """[Item] for the VEVENTs and VTODOs of an iCalendar text (an item that cannot be read is left out). `zone`: where a time without a zone is meant."""
    items, current = [], None
    for line in unfold(text):
        up = line.strip().upper()
        if up in ("BEGIN:VEVENT", "BEGIN:VTODO"):
            current = {"kind": "event" if up.endswith("VEVENT") else "todo", "props": []}
        elif up in ("END:VEVENT", "END:VTODO") and current is not None:
            item = _item(current, zone)
            if item:
                items.append(item)
            current = None
        elif current is not None:
            parsed = _split(line)
            if parsed:
                current["props"].append(parsed)
    return items


def _item(raw, zone):
    props = {}
    extra = {"EXDATE": []}
    for name, params, value in raw["props"]:
        if name == "EXDATE":
            extra["EXDATE"].append((params, value))
        else:
            props.setdefault(name, (params, value))
    try:
        item = Item(uid=(props.get("UID", ({}, ""))[1] or "").strip(), kind=raw["kind"])
        item.summary = _unescape(props.get("SUMMARY", ({}, ""))[1]).strip()
        item.description = _unescape(props.get("DESCRIPTION", ({}, ""))[1]).strip()
        item.location = _unescape(props.get("LOCATION", ({}, ""))[1]).strip()
        item.url = props.get("URL", ({}, ""))[1].strip()
        item.done = props.get("STATUS", ({}, ""))[1].strip().upper() == "COMPLETED"
        if props.get("STATUS", ({}, ""))[1].strip().upper() == "CANCELLED":
            return None
        if "DTSTART" in props:
            item.start, item.all_day, item.tz = parse_when(props["DTSTART"][1], props["DTSTART"][0], zone)
        if "DTEND" in props:
            item.end = parse_when(props["DTEND"][1], props["DTEND"][0], zone)[0]
        elif "DURATION" in props and item.start is not None:
            m = re.fullmatch(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", props["DURATION"][1].strip())
            if m:
                w, d, h, mi, s = (int(x or 0) for x in m.groups())
                delta = timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)
                item.end = item.start + delta
        if "DUE" in props:
            item.due = parse_when(props["DUE"][1], props["DUE"][0], zone)[0]
            if item.start is None:
                item.start, item.all_day = item.due, isinstance(item.due, date) and not isinstance(item.due, datetime)
        if "RECURRENCE-ID" in props:
            item.recurrence_id = parse_when(props["RECURRENCE-ID"][1], props["RECURRENCE-ID"][0], zone)[0]
        if "RRULE" in props:
            item.rule = _rule(props["RRULE"][1])
        for params, value in extra["EXDATE"]:
            for v in value.split(","):
                item.exdates.append(parse_when(v, params, zone)[0])
        if item.start is None:
            return None
        if item.end is None:
            item.end = item.start
        if not item.uid:
            item.uid = f"{item.summary}@{item.start}"
        return item
    except (ValueError, KeyError):
        return None


# ---------------------------------------------------------------- repeats
_DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _after(a, b):
    """a is later than b; either may be a date or a datetime (then the dates are compared)."""
    if isinstance(a, datetime) and isinstance(b, datetime):
        return a > b
    return (a.date() if isinstance(a, datetime) else a) > (b.date() if isinstance(b, datetime) else b)


def _repeats(item, last, zone):
    """The start moments (UTC datetimes, or dates for an all-day item) of a repeating item up to `last` (the rule, with COUNT and UNTIL)."""
    rule = item.rule
    freq, step = rule.get("FREQ", ""), max(1, int(rule.get("INTERVAL", "1") or 1))
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    zone = item.tz or UTC                                                  # a time written in UTC repeats on the UTC clock
    first_local = item.start if item.all_day else item.start.astimezone(zone)
    until = None
    if rule.get("UNTIL"):
        try:
            until = parse_when(rule["UNTIL"], {}, zone)[0]
        except ValueError:
            until = None
    wanted_days = sorted(_DAYS[d[-2:]] for d in rule.get("BYDAY", "").split(",") if d[-2:] in _DAYS)

    def make(naive_date):
        if item.all_day:
            return naive_date
        local = datetime.combine(naive_date, first_local.time()).replace(tzinfo=zone)
        return local.astimezone(UTC)

    base = first_local.date() if not item.all_day else first_local
    out, produced, steps = [], 0, 0
    k = 0
    while steps < MAX_STEPS:
        steps += 1
        if freq == "DAILY":
            days = [base + timedelta(days=k * step)]
        elif freq == "WEEKLY":
            monday = base - timedelta(days=base.weekday()) + timedelta(weeks=k * step)
            days = [monday + timedelta(days=d) for d in (wanted_days or [base.weekday()])]
        elif freq == "MONTHLY":
            month = base.month - 1 + k * step
            try:
                days = [date(base.year + month // 12, month % 12 + 1, base.day)]
            except ValueError:
                days = []
        elif freq == "YEARLY":
            try:
                days = [date(base.year + k * step, base.month, base.day)]
            except ValueError:
                days = []
        else:
            return out
        k += 1
        for d in days:
            if d < base:
                continue
            moment = make(d)
            if until is not None and _after(moment, until):
                return out
            if count is not None and produced >= count:
                return out
            produced += 1
            if _after(moment, last):
                return out
            out.append(moment)
        if count is not None and produced >= count:
            return out
    return out


def occurrences(items, first, last, zone=UTC):
    """The items that fall in the window [first, last] (aware UTC datetimes), repeats expanded and one-off changes of a repeat applied: a list of dicts
    {key, uid, kind, title, start, end, all_day, due, description, location, url, done}. `key` is the same on every read of the same item (the uid, and the start of a repeat)."""
    overrides = {(i.uid, i.recurrence_id): i for i in items if i.recurrence_id is not None}
    out = []

    def inside(start, end, all_day):
        if all_day:
            return first.date() <= (start if not isinstance(start, datetime) else start.date()) <= last.date()
        return (end if end is not None else start) >= first and start <= last

    def add(item, start, end, key):
        out.append({"key": key, "uid": item.uid, "kind": item.kind, "title": item.summary or "(No Title)", "start": start, "end": end, "all_day": item.all_day,
                    "due": item.due, "description": item.description, "location": item.location, "url": item.url, "done": item.done})

    for item in items:
        if item.recurrence_id is not None:
            if inside(item.start, item.end, item.all_day):
                add(item, item.start, item.end, f"{item.uid}@{item.recurrence_id}")
            continue
        length = (item.end - item.start) if item.end is not None else timedelta(0)
        if item.rule:
            for start in _repeats(item, last, zone):
                if start in item.exdates or (overrides.get((item.uid, start)) is not None):
                    continue
                end = start + (length if not item.all_day else timedelta(days=max(0, length.days)))
                if inside(start, end, item.all_day):
                    add(item, start, end, f"{item.uid}@{start}")
        elif inside(item.start, item.end, item.all_day):
            add(item, item.start, item.end, item.uid)
    return sorted(out, key=lambda o: (datetime.combine(o["start"], time.min, UTC) if not isinstance(o["start"], datetime) else o["start"], o["title"]))


# ---------------------------------------------------------------- what an item is
_CATEGORY_WORDS = (("Exam", r"exam|midterm|final|test"), ("Quiz", r"quiz"), ("Lab", r"\blab\b|laboratory"), ("Reading", r"reading|read\b|chapter"),
                   ("Project", r"project|paper|essay|presentation|report|proposal"), ("Homework", r"homework|assignment|\bhw\b|problem set|pset|worksheet|discussion|submission"))
_TASK_WORDS = re.compile(r"homework|assignment|\bhw\b|problem set|pset|worksheet|quiz|exam|midterm|final|\blab\b|lab report|project|reading|essay|paper|due\b|submission|discussion|presentation", re.I)


def category_of(text):
    for category, pattern in _CATEGORY_WORDS:
        if re.search(pattern, text or "", re.I):
            return category
    return "Other"


def classify(occ, source=None):
    """("task" or "event", category): a to-do, an assignment of Canvas, an item with a due date or a short item that names homework, a quiz or an exam is a task; the rest is an event.
    `source` is the service the calendar comes from. A Shovel calendar holds the student's classes and the study time Shovel planned (for a task named "Homework 4", say): a timed item there is
    time on the calendar, an event, never a second copy of the task; only a to-do or an all-day item (a due date) can be a task."""
    title, uid = occ["title"], (occ.get("uid") or "").lower()
    if occ["kind"] == "todo":
        return "task", category_of(title)
    if source == "Shovel" and not occ["all_day"]:
        return "event", category_of(title)
    start, end = occ["start"], occ["end"]
    short = occ["all_day"] or end is None or (isinstance(start, datetime) and isinstance(end, datetime) and end - start <= timedelta(minutes=60))
    if "assignment" in uid or "quiz" in uid or uid.startswith("event-assignment"):
        return "task", category_of(title)
    if short and _TASK_WORDS.search(title):
        return "task", category_of(title)
    return "event", category_of(title)


def _compact(text):
    return re.sub(r"[\s\-_./]+", "", (text or "")).upper()


def match_course(occ, courses):
    """The id of the course an item is about (its number, such as AE6765, appears in the title, the place or the start of the description), or None. `courses`: [{id, code, name}]."""
    haystack = _compact(" ".join([occ["title"], occ.get("location") or "", (occ.get("description") or "")[:300]]))
    best = None
    for c in courses:
        code = _compact((c.get("code") or "").split("/")[0])
        if code and code in haystack and (best is None or len(code) > best[0]):
            best = (len(code), c["id"])
    if best:
        return best[1]
    for c in courses:
        name = (c.get("name") or "").strip().lower()
        if len(name) >= 8 and name in (occ["title"] or "").lower():
            return c["id"]
    return None
