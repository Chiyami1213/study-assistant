"""The quizzes of a course (native): the chapters with their up to four quizzes (conceptual questions, speed round, guided practice, closed-book round), taken separately and counted in total;
save for later and resume, notes and hints (recorded), the attempts of a quiz opened again. The questions hold TeX math, so the cards are drawn by a small web page (qtui/quizhtml.py); the rest is native."""
import time
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from core import crud
from qtui import quizhtml
from qtui.widgets import Segmented
from study import htmlnotes, quizrun
from study.quizrun import MODE_EACH, MODE_END, PART_LABEL, PASS

LEVEL_COLORS = {"Strong": "#2e9e5b", "Passed": "#3b82f6", "Failed": "#d64545"}


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


class Bridge(QObject):
    """What the page of cards calls (Qt WebChannel): an option pressed, the notes or the hint asked for, an open question marked."""

    def __init__(self, page):
        super().__init__()
        self.page = page

    @Slot(str, int, int)
    def act(self, kind, qi, arg):
        self.page.on_act(kind, qi, arg)


class CardsView(QWebEngineView):
    """A web view with the cards of a quiz (or the review of an attempt) and the channel to Python."""

    def __init__(self, page):
        super().__init__()
        self.channel = QWebChannel(self)
        self.bridge = Bridge(page)
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)


class QuizPage(QWidget):
    changed = Signal()

    def __init__(self, colors):
        super().__init__()
        self.setObjectName("page")
        self.colors = colors
        self.course = None
        self.chapter = None
        self.run = None
        self.mode = MODE_END
        self.notice = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 16)
        root.setSpacing(8)
        top = QHBoxLayout()
        title = QLabel("Quiz")
        title.setObjectName("h1")
        top.addWidget(title)
        top.addStretch(1)
        self.courses = QComboBox()
        self.courses.setMinimumWidth(320)
        self.courses.currentIndexChanged.connect(self._course_changed)
        top.addWidget(self.courses)
        root.addLayout(top)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        # the list of chapters
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.listbody = QWidget()
        self.listbody.setObjectName("page")
        self.llay = QVBoxLayout(self.listbody)
        self.llay.setContentsMargins(0, 0, 0, 0)
        self.llay.setSpacing(10)
        self.scroll.setWidget(self.listbody)
        self.stack.addWidget(self.scroll)
        # a quiz being taken, a finished one, an attempt opened again
        self.runview = QWidget()
        self.stack.addWidget(self.runview)
        rl = QVBoxLayout(self.runview)
        rl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.run_title = QLabel()
        self.run_title.setObjectName("h2")
        bar.addWidget(self.run_title, 1)
        self.clock = QLabel()
        self.clock.setStyleSheet("font-size: 18px; font-weight: 700;")
        bar.addWidget(self.clock)
        self.save_btn = QPushButton("Save For Later")
        self.save_btn.setToolTip("keeps this quiz as it is (the questions, your answers, the notes and hints used) so you can resume it later")
        self.save_btn.clicked.connect(self.save_for_later)
        self.back_btn = QPushButton("Leave Quiz")
        self.back_btn.clicked.connect(self.leave)
        bar.addWidget(self.save_btn)
        bar.addWidget(self.back_btn)
        rl.addLayout(bar)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        rl.addWidget(self.status)
        self.extra = QVBoxLayout()                       # the score and the buttons of a finished quiz, the attempt box of a view
        rl.addLayout(self.extra)
        self.split = QSplitter(Qt.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.web = CardsView(self)
        self.split.addWidget(self.web)
        self.notes_box = QWidget()
        nl = QVBoxLayout(self.notes_box)
        nl.setContentsMargins(0, 0, 0, 0)
        nb = QHBoxLayout()
        self.notes_title = QLabel()
        nb.addWidget(self.notes_title, 1)
        close = QPushButton("Close Notes")
        close.clicked.connect(self.close_notes)
        nb.addWidget(close)
        nl.addLayout(nb)
        hint = QLabel("Using the notes or a hint is recorded: answers made with either do not count towards the unaided score.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        nl.addWidget(hint)
        self.notes_web = QWebEngineView()
        nl.addWidget(self.notes_web, 1)
        self.split.addWidget(self.notes_box)
        self.notes_box.hide()
        rl.addWidget(self.split, 1)
        self.finish_btn = QPushButton("Finish And Score")
        self.finish_btn.setObjectName("primary")
        self.finish_btn.setFixedWidth(200)
        self.finish_btn.clicked.connect(self.finish)
        rl.addWidget(self.finish_btn)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.reload_courses()

    # ---------------------------------------------------------------- courses and the list
    def set_colors(self, colors):
        self.colors = colors
        if self.run is None:
            self.show_list()

    def reload_courses(self, select=None):
        courses = [c for s in crud.STATUSES for c in crud.courses_by_status(s)]
        self.courses.blockSignals(True)
        self.courses.clear()
        for c in courses:
            self.courses.addItem(crud.label(c), c["id"])
        i = self.courses.findData(select if select is not None else self.course["id"] if self.course else None)
        self.courses.setCurrentIndex(max(0, i) if courses else -1)
        self.courses.blockSignals(False)
        self._course_changed()

    def set_course(self, course_id):
        """Shows the quizzes of this course (when nothing is being taken)."""
        if self.run is None and course_id is not None:
            i = self.courses.findData(course_id)
            if i >= 0 and i != self.courses.currentIndex():
                self.courses.setCurrentIndex(i)

    def _course_changed(self, *_):
        cid = self.courses.currentData()
        self.course = crud.get_course(cid) if cid else None
        if self.run is not None:
            self._drop_run()
        self.show_list()

    def show_list(self):
        self.timer.stop()
        self.stack.setCurrentWidget(self.scroll)
        _clear(self.llay)
        if not self.course:
            self.llay.addWidget(QLabel("No course yet."))
            return
        chapters = quizrun.course_chapters(self.course)
        if not chapters:
            self.llay.addWidget(QLabel("No quiz questions yet. Quizzes come from the conceptual checks and the Self-check section of this course's HTML notes in the Library."))
            self.llay.addStretch(1)
            return
        if self.notice:
            note = QLabel(self.notice)
            note.setObjectName("muted")
            self.llay.addWidget(note)
            self.notice = ""
        row = QHBoxLayout()
        row.addWidget(QLabel("Checking Mode"))
        seg = Segmented([(MODE_END, MODE_END), (MODE_EACH, MODE_EACH)], self.mode)
        seg.setToolTip("check after finishing: nothing is marked until you finish. check after each answer: an answer is marked right away and cannot be changed; check notes and hint are not available")
        seg.changed.connect(lambda k: setattr(self, "mode", k))
        row.addWidget(seg, 1)
        self.llay.addLayout(row)
        cap = QLabel(f"Pick a chapter or lecture. Each chapter has up to four quizzes (conceptual questions, a speed round, guided practice, a closed-book round of equations to write from memory): take them "
                     f"separately; their scores count together in the total. Below {PASS}% the total is failed. Check Notes and Hint are allowed (not in the mode that checks each answer, and not in the speed round) but recorded.")
        cap.setObjectName("muted")
        cap.setWordWrap(True)
        self.llay.addWidget(cap)
        stats = crud.quiz_stats(self.course["id"])
        for c in chapters:
            self.llay.addWidget(self._chapter_card(c, stats.get(c["book"]["id"])))
        if stats:
            clear = QPushButton("Clear Attempt History")
            clear.setFixedWidth(200)
            clear.clicked.connect(lambda: self.clear_history(None))
            self.llay.addWidget(clear)
        self.llay.addStretch(1)

    def _chapter_card(self, c, s):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        parts = quizrun.chapter_parts(c)
        head = QHBoxLayout()
        n_all = sum(quizrun._count(c, p, q) for p, q in parts.items())
        name = QLabel(f"<b>{c['name']}</b><br>{n_all} questions in {len(parts)} quiz{'zes' if len(parts) != 1 else ''}")
        head.addWidget(name, 3)
        if s:
            pct = quizrun._pct(quizrun._unaided(s), s["last_total"])
            level = quizrun._level(pct)[0]
            meta = QLabel(f"Total {quizrun._unaided(s)}/{s['last_total']} unaided ({pct}%)<br>Best {s['best']}% · {s['attempts']} attempts")
            head.addWidget(meta, 2)
            pill = QLabel(level)
            pill.setStyleSheet(f"background: {LEVEL_COLORS[level]}; color: #ffffff; border-radius: 10px; padding: 2px 12px; font-weight: 600;")
            head.addWidget(pill)
            view = QPushButton("View")
            view.setToolTip("opens a finished attempt again: the questions, your answers and the explanations")
            view.clicked.connect(lambda _=False, ch=c: self.view_attempts(ch))
            head.addWidget(view)
        else:
            head.addWidget(QLabel("Not taken yet"), 2)
        lay.addLayout(head)
        cells = QHBoxLayout()
        for part, qs in parts.items():
            ps = (s or {}).get("parts", {}).get(part)
            saved = quizrun.saved_progress(self.course["id"], c["book"]["id"], part)
            unit = {"guided": "steps", "closed": "equations"}.get(part, "questions")
            cap = (f"<b>{PART_LABEL[part]}</b><br>{quizrun._count(c, part, qs)} {unit}"
                   + (f" · last {ps['last_correct'] - ps['last_assisted']}/{ps['last_total']}" if ps else " · not taken")
                   + (f" · {quizrun.speed_limit(c)} s" if part == "speed" else ""))
            cell = QVBoxLayout()
            label = QLabel(cap)
            label.setWordWrap(True)
            cell.addWidget(label)
            go = QPushButton("Retake" if ps else "Start")
            if not ps and not saved:
                go.setObjectName("primary")
            go.clicked.connect(lambda _=False, ch=c, p=part: self.start(ch, p))
            cell.addWidget(go)
            cells.addLayout(cell, 1)
        lay.addLayout(cells)
        for part in parts:
            saved = quizrun.saved_progress(self.course["id"], c["book"]["id"], part)
            if saved:
                done = sum(1 for v in saved["res"].values() if v.get("chosen") is not None or v.get("got") is not None)
                when = saved.get("saved_at", "")[:16].replace("T", " ")
                row = QHBoxLayout()
                row.addWidget(QLabel(f"Saved {PART_LABEL[part].lower()}: {done} of {len(saved['order'])} answered · {'checked after each answer' if saved.get('mode') == 'each' else 'checked after finishing'}"
                                     + (f" · saved {when}" if when else "")), 1)
                resume = QPushButton("Resume")
                resume.setObjectName("primary")
                resume.clicked.connect(lambda _=False, ch=c, p=part: self.resume(ch, p))
                drop = QPushButton("Discard Saved Quiz")
                drop.setToolTip("deletes the saved, unfinished quiz. finished attempts are not touched")
                drop.clicked.connect(lambda _=False, ch=c, p=part: self.discard(ch, p))
                row.addWidget(resume)
                row.addWidget(drop)
                lay.addLayout(row)
        return card

    # ---------------------------------------------------------------- taking a quiz
    def start(self, chapter, part):
        self.chapter = chapter
        self.begin(quizrun.new_run(chapter, part, self.mode))

    def resume(self, chapter, part):
        run = quizrun.saved_progress(self.course["id"], chapter["book"]["id"], part)
        if run:
            self.chapter = chapter
            self.begin(run)

    def discard(self, chapter, part):
        quizrun._drop_progress(self.course["id"], chapter["book"]["id"], part)
        self.notice = "Saved quiz discarded."
        self.show_list()

    def begin(self, run):
        self.run = run
        part = run.get("part", "concept")
        self.run_title.setText(self.chapter["name"] + (f" · {PART_LABEL[part]}" if part != "concept" else ""))
        self.clear_extra()
        self.save_btn.setVisible(part != "speed")
        self.finish_btn.setVisible(True)
        self.back_btn.setText("Leave Quiz")
        self.notes_box.hide()
        self.clock.setVisible(part == "speed")
        self.web.setHtml(quizhtml.page(self.colors, quizhtml.run_body(run)), QUrl("https://localhost/"))
        self.stack.setCurrentWidget(self.runview)
        self.update_status()
        if part == "speed":
            self.timer.start(1000)
            self._tick()
        else:
            self.timer.stop()

    def clear_extra(self):
        _clear(self.extra)

    def update_status(self):
        run = self.run
        if not run or run.get("phase") != "run":
            return
        qs, order, res = run["qs"], run["order"], run["res"]
        answered = sum(1 for qi in order if (res.get(qi) or {}).get("chosen") is not None or (res.get(qi) or {}).get("got") is not None)
        notes = sum(1 for qi in order if (res.get(qi) or {}).get("notes"))
        hints = sum(1 for qi in order if (res.get(qi) or {}).get("hint"))
        if run.get("part") == "closed":
            text = f"{answered} of {len(order)} answered. Notes shut: write each equation on paper, open the model answer to check, then press I Had It only if you had it exactly, or Not Yet."
        elif run.get("mode") == "each":
            right = sum(1 for qi in order if quizrun._is_right(qs[qi], res.get(qi)))
            text = f"{answered} of {len(order)} answered · {right} right so far · {notes} with notes · {hints} with hints (both recorded). Press an option to answer; it is marked at once and cannot be changed."
        else:
            text = f"{answered} of {len(order)} answered · {notes} with notes · {hints} with hints (both recorded). Press an option to choose it; you can change it until you finish. Answers are marked at the end."
        if run.get("part") == "speed":
            text += " Answer on instinct. Time is up after the limit; the questions not answered then are missed."
        self.status.setText(text)

    def _tick(self):
        run = self.run
        if not run or run.get("phase") != "run" or run.get("part") != "speed":
            self.timer.stop()
            return
        left = int(run["limit"] - (time.time() - run["t0"]) + 0.999)
        if left <= 0:
            self.finish()
            return
        self.clock.setText(f"⏱ {left // 60}:{left % 60:02d}")
        self.clock.setStyleSheet("font-size: 18px; font-weight: 700;" + (" color: #d64545;" if left < 15 else ""))

    def on_act(self, kind, qi, arg):
        """A press in the cards."""
        run = self.run
        if not run or run.get("phase") != "run":
            return
        e = run["res"].setdefault(qi, {"chosen": None, "notes": False, "hint": False})
        q = run["qs"][qi]
        if kind == "pick":
            if run.get("mode") == "each" and e["chosen"] is not None:
                return
            e["chosen"] = arg
        elif kind == "hint":
            e["hint"] = True
        elif kind == "grade":
            e["got"] = bool(arg)
        elif kind == "notes":
            e["notes"] = True
            self.open_notes(q)
        self.web.page().runJavaScript(quizhtml.js_card(qi, quizhtml.card_inner(run, qi)))
        self.update_status()

    def open_notes(self, q):
        """The note on the right half, at the section of the question."""
        text = self.chapter["path"].read_text(encoding="utf-8", errors="replace")
        self.notes_title.setText(f"<b>Notes</b> · {q.get('tag') or self.chapter['name']}")
        self.notes_web.setHtml(htmlnotes.safe_html(text, q.get("sec")), QUrl("https://localhost/"))
        self.notes_box.show()
        w = max(self.split.width(), 800)
        self.split.setSizes([w // 2, w // 2])

    def close_notes(self):
        self.notes_box.hide()

    def save_for_later(self):
        run = self.run
        if run and run.get("phase") == "run":
            quizrun._save_progress(self.course["id"], run)
            self.notice = "Quiz saved. Resume it from the Quiz page."
            self._drop_run()
            self.show_list()

    def _drop_run(self):
        self.run, self.chapter = None, None
        self.timer.stop()
        self.notes_box.hide()

    def leave(self):
        self._drop_run()
        self.show_list()

    def finish(self):
        run = self.run
        if not run or run.get("phase") != "run":
            return
        self.timer.stop()
        quizrun.finish_run(self.course["id"], self.chapter, run)
        self.show_done()

    # ---------------------------------------------------------------- the result, the attempts
    def _score_box(self, correct, assisted, total, notes_used, hints_used):
        unaided = correct - assisted
        pct = quizrun._pct(unaided, total)
        level = quizrun._level(pct)[0]
        box = QFrame()
        box.setObjectName("card")
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        big = QLabel(f"{unaided} / {total}   {pct}% unaided")
        big.setStyleSheet("font-size: 22px; font-weight: 700;")
        row.addWidget(big)
        pill = QLabel(level)
        pill.setStyleSheet(f"background: {LEVEL_COLORS[level]}; color: #ffffff; border-radius: 10px; padding: 2px 12px; font-weight: 600;")
        row.addWidget(pill)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(QLabel(f"Recorded for this attempt: notes used on {notes_used} question{'s' if notes_used != 1 else ''}, hints on {hints_used}."))
        if assisted:
            lay.addWidget(QLabel(f"{correct} / {total} correct in all. {assisted} correct answer{'s' if assisted != 1 else ''} used the notes or a hint and {'are' if assisted != 1 else 'is'} recorded as assisted, so not counted."))
        if pct < PASS:
            fail = QLabel(f"Failed: {pct}% is below {PASS}%. Review the explanations below, then retake.")
            fail.setStyleSheet("color: #d64545;")
            lay.addWidget(fail)
        return box

    def show_done(self):
        run = self.run
        self.clear_extra()
        self.save_btn.hide()
        self.finish_btn.hide()
        self.clock.hide()
        self.back_btn.setText("Back To Quizzes")
        self.status.setText("")
        self.extra.addWidget(self._score_box(run["correct"], run["assisted"], len(run["review"]), run["notes_used"], run["hints_used"]))
        retake = QPushButton("Retake")
        retake.setFixedWidth(120)
        retake.clicked.connect(lambda: self.start(self.chapter, run.get("part", "concept")))
        self.extra.addWidget(retake)
        self.web.setHtml(quizhtml.page(self.colors, quizhtml.review_body(run["review"])), QUrl("https://localhost/"))
        self.notes_box.hide()
        self.stack.setCurrentWidget(self.runview)

    def view_attempts(self, chapter):
        """The finished attempts of a chapter's quizzes, opened again."""
        attempts = crud.quiz_attempts(self.course["id"], chapter["book"]["id"])
        if not attempts:
            return
        self.chapter = chapter
        self.run = {"phase": "view"}
        self.clear_extra()
        self.run_title.setText(chapter["name"])
        self.save_btn.hide()
        self.finish_btn.hide()
        self.clock.hide()
        self.back_btn.setText("Back To Quizzes")
        self.status.setText("")
        self.notes_box.hide()
        row = QHBoxLayout()
        pick = QComboBox()
        for a in attempts:
            try:
                when = datetime.fromisoformat(a["taken_at"]).replace(tzinfo=timezone.utc).astimezone().strftime("%b %d, %Y %I:%M %p")
            except (TypeError, ValueError):
                when = str(a["taken_at"])
            pick.addItem(f"{when} · {PART_LABEL.get(a['part'], a['part'])} · {a['correct']} / {a['total']}", a)
        row.addWidget(QLabel("Attempt"))
        row.addWidget(pick, 1)
        clear = QPushButton("Clear Attempt History")
        clear.clicked.connect(lambda: self.clear_history(chapter["book"]["id"]))
        row.addWidget(clear)
        self.extra.addLayout(row)
        holder = QVBoxLayout()
        self.extra.addLayout(holder)

        def show(_=None):
            import json
            _clear(holder)
            a = pick.currentData()
            try:
                review = json.loads(a["answers"]) if a["answers"] else []
            except ValueError:
                review = []
            holder.addWidget(self._score_box(a["correct"], a["assisted"], a["total"], a["notes_used"], a["hints_used"]))
            self.web.setHtml(quizhtml.page(self.colors, quizhtml.review_body(review)), QUrl("https://localhost/"))

        pick.currentIndexChanged.connect(show)
        show()
        self.stack.setCurrentWidget(self.runview)

    def clear_history(self, book_id):
        what = "this quiz" if book_id is not None else "every quiz of this course"
        ask = QMessageBox.question(self.window(), "Clear Attempt History", f"Delete all recorded attempts of {what}? The scores in Understanding go back to Not Taken. This cannot be undone.")
        if ask == QMessageBox.Yes:
            crud.clear_quiz_attempts(self.course["id"], book_id)
            self.notice = "Attempt history cleared." if book_id is None else "Attempt history of this quiz cleared."
            self._drop_run()
            self.show_list()
