# Homework and Exam Pages for This Course

## Inputs I Will Give You

- Homework or exam PDFs, graded scans (often scans without a text layer: render pages to images and read them), the posted solution if one exists, and screenshots from my course software (class mean, standard deviation, top score, most common issues).
- My chapter or lecture notes {{NOTES_WORD}}, so you can link to them. Read my existing notes first and link to the matching sections.
- If a needed input is missing, say what is missing and continue with what you have. Never invent grader comments or class statistics.

## Reference Pages (Match These)

If you can read my earlier pages for this course (homework grade explanations, helpers, exam reflections and preparation pages), read them before writing and match their structure and look. If you cannot, use the specification below.

## Visual System (Use for Every Page)

- **Fonts** (Google Fonts): Spectral (headings, 500/600/700 and italic), IBM Plex Sans (body), IBM Plex Mono (labels, numbers). Math: MathJax 3.2.2 `tex-svg` from jsdelivr (`https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js`), inline `\( \)`, display `\[ \]`.
- **Tokens** on `:root`, with dark mode under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])` and again under `:root[data-theme="dark"]`:
  - light: `--bg #F3F5F8`, `--surface #FFFFFF`, `--ink #132033`, `--muted #5B6779`, `--rule #D6DCE5`, `--bench #E9EEF5`, `--halpha #C2302A` (red), `--hbeta #1D6CB0` (blue), `--hgamma #6A3FB5` (purple), `--ok #2C7A4B`, `--warn #A86A12`, `--bad #C2302A`, `--bulb #B98207`
  - dark: `--bg #0D131C`, `--surface #141C28`, `--ink #E3E8EF`, `--muted #94A1B4`, `--rule #283445`, `--bench #111925`, `--halpha #FF6A5C`, `--hbeta #5CB0F4`, `--hgamma #A98BF0`, `--ok #5BC48A`, `--warn #E3A84A`, `--bad #FF6A5C`, `--bulb #F2C14E`
- **Layout**: two-column shell (left sticky table of contents 250 px, content right), max width 1220 px; 16 px side gutters with `max(16px, env(safe-area-inset-*))`; a `<meta name="claude:viewport-fit-sides" content="cover">`. Under 960 px the table of contents becomes a slide-in menu opened by a fixed "☰ Contents" button with a scrim.
- **Table of contents**: scroll-spy highlights the current section; a "Related" block at the bottom links sibling pages.
- **Compact**: body 14.5 px, line height 1.45, card padding 10 px 14 px, tight tables (12.5 px). Designed for a phone-width study app.
- **Folding**: all detail is in `<details>` closed by default; a `beforeprint` script opens them all; clicking a table-of-contents link to a folded `details` opens it.
- **Equations**: `.eqb` boxes, black 1.5 px edge for regular equations, red 2.5 px edge (`--halpha`, with a faint glow) for final results and governing equations.
- **Units** in parentheses with a center dot, dimensions in square brackets, every vector with `\vec`, no `/` for division (see the rules).
- **Title** of each page is the file name (for example `<COURSE> Midterm 1 Grades`); headings in APA title case; fix any formatting problem on every page of that type.
- Browser storage (`localStorage`) only for per-viewer ticks, always inside `try/catch`.

## Page Specifications

### 1. Homework Helper

Purpose: help me solve the homework myself, part by part, with short steps (I am time-pressed before the due date).

1. Header: course, homework number, a lede with what the homework covers.
2. **Before You Start: Lessons From Graded Work**: a checklist of the points lost on my earlier homework and exams (grader comments), each tagged with its source (for example `HW1 P4a`). **Include only the lessons that apply to this homework's problems**; drop any the problems cannot trigger and reword examples to the current problems. The lede says only applicable lessons are shown and names the ones that matter most, without numbering them. The first homework of a course has no such section.
3. One card per problem: page number pill, "Concept check · getting started", the task restated briefly in a shaded box, then:
   - a resource list: notes section links (book icon), a worked example in my notes that uses the same approach (calculator icon), key boxed equations in my notes (Σ icon)
   - one block per part with a lightbulb button that reveals **hints one step at a time** ("Next hint (2 of 4)"), never the full answer
   - a "done" checkbox per part saved in the browser
4. Hints give the method and the check, not the numeric answer.

### 2. Homework Grade Explanation

1. Header: eyebrow `<COURSE> · Homework n · Grade Explanation`, title `Homework n: <topic>` with the topic in italics (red), the total score, one line on where the points went, a one-line instruction ("Tap a block to expand …"), and a **scoreboard** of tiles (one per problem: title clamped to three lines, score, bar; amber when partial, red when low, green when full).
2. **One card per problem**, in this order, with these folds closed:
   - header with problem title and a **score pill** (`full` green, `part` amber, `low` red)
   - fold **Score by part** (summary shows count and flagged lines): rows with ✓ (full), ◐ (partial), ✗ (none), points as `earned / maximum`, and a one-line reason
   - open, not folded: **Grader Comments**, one card per comment, numbered badge, "Grader · part (x), page n", the grader's words quoted exactly
   - fold **What you wrote** (purple edge): a neutral summary of my work
   - fold **Why points were lost** (red edge): the cause, stated plainly
   - fold **Correct solution** (blue edge): boxed equations, red edge for final results; numbers computed, not recalled
   - fold **Notes links** (blue edge): links to the matching sections in my chapter notes
   - **Takeaway** (green edge), 1–2 sentences, always visible
3. Endings: **Patterns to Carry Forward** (folded, a grid of short cards) and **Notes on the Posted Solution** (folded table of errors or ambiguities in the posted solution, each with the check that found it).
4. Footer: sources used.

### 3. Exam Grade Explanation

Same as the homework grade explanation, with these differences:

1. No posted solution usually exists: **work out the full solution yourself**, check every number by computing it (script or calculator), and say in the footer that the solutions are your own.
2. Per-part maxima come from the graded paper or my course software; when two sources disagree, my course software wins.
3. If the exam statement is inconsistent (for example a second-law violation, a table row beyond the range, a table value that does not integrate correctly), do not hide it: list it in **Notes on the Exam Statement**, state what answer you used, and say that it does not change the grade.
4. Do **not** put patterns on this page; they go on the Reflection page. Link to the Reflection and Preparation pages in the table of contents.

### 4. Exam Reflection

Sections: Overview, At a Glance, By Part, Where the Points Went (by cause), The Pattern, Predicted vs Actual, Carried to the Next Exam.

1. **At a Glance** table: exam date and rules (open book, calculator), score and class statistics, where I stand, each problem's score, homework versus exam.
2. **By Part** table: part, score, class mean (percent), score minus mean (green or red), standard deviation, top score (number of students), what happened and the class's common issues; above it a bar chart of score minus mean per part (diverging bars, green right, red left).
3. **Where the points went, by cause**: a table that regroups lost points by cause (misread term, unfinished numbers, missing link, reasoning), with parts, points and share. Add a green note on what worked.
4. **The Pattern**: five bullets, each tied to a part and, where it applies, to a repeat of an earlier homework comment.
5. **Predicted vs Actual**: compare the actual exam problems with the predicted problems from the exam's Preparation page, one row per predicted type (evidence, the actual problem, Hit, Partial or Miss, exam points). List what the prediction missed (the angle on a known topic, reasoning versus computing, overweighted topics) and say whether points were lost to surprise or to execution. Also compare the Preparation page's **mock exam** with the real exam, problem by problem and part by part (match: strong, partial, none; point weights per part; what the mock covered and missed). A mock should match the real point weights per part, not only the topics; fix the mock when the comparison shows a gap. If the Preparation page was written after the exam, say its predictions and mock are not an independent test. If no prediction was written before the exam, do a **backtest** from only what existed before the exam (earlier homework and lectures), label it a backtest, and never use the exam as evidence for the ranking. End with the next exam's predictions in a table with empty "Actual problem" and "Result" columns to score later.
6. **Carried to the Next Exam**: a short pointer only. The Reflection is a record of one exam. Put everything useful for the next exam into that exam's Preparation page instead: the fixes (table of habit, rule on the exam, points it was worth) in its rules section, and empty tables for scoring the next exam's predicted types and mock exam in a final "Score After the Exam" section. Do not duplicate them in the Reflection.
7. **Provenance chips**: `stated` (green) for numbers read from my course software or slides, `estimate` (amber) for anything you inferred. If a cell's data was not in my screenshots, show a dash and a note; if one value looks wrong (for example a top score below my own score), flag it instead of silently using it.
8. If my course software already has a reflection, merge it: keep its numbers and wording where they are right, condense the rest, add the by-cause view and the fixes.

### 5. Exam Preparation

Sections: Overview, Rules From the Last Exam, Coverage Map, Equation Sheet, Problem Patterns, Past Work Analysis, Predicted Problems, Mock Exam, Numbers to Sanity-Check, Self-Test, Study Plan, Score After the Exam.

1. **Header**: coverage as my course software lists it (homework numbers, chapters). If the coverage or date is not listed, state your assumption in the lede and say it needs updating. Scoreboard tiles: one per chapter, plus the relevant homework.
2. **Rules From the Last Exam**: four short cards drawn from my reflection, then a table of the fixes: habit, the rule to follow on the exam, and the points it was worth. (The first exam of a course has no last exam: leave this section out.)
3. **Coverage Map** table: topic, links to the matching chapter-note sections, the homework it ties to, priority (High or Medium, red or amber pill). Say the priority is your ranking.
4. **Equation Sheet**: every equation boxed with a red edge, grouped by chapter, two-column grid on wide screens; each label links to its derivation in my notes.
5. **Problem Patterns**: one blue-edged fold per likely problem type with: trigger, numbered recipe, a red **Trap** (the exact way points were lost), and a **Check** with numbers you computed. Derive the patterns from an analysis of every past exam, practice exam and homework problem I give you, not from the notes alone.
6. **Past Work Analysis**: a table of problem types: where each appeared (exam, practice, homework and problem number), how often, points at stake, where points were lost. State which sources were available; if there is no practice exam, say so and do not invent one.
7. **Predicted Problems**: a ranked list of the problem types most likely to appear, each with its evidence (which past problems and homework it repeats, lecture emphasis) and a likelihood labeled as your judgment. Add one or two lower-likelihood wildcards.
8. **Mock Exam**: a full set of problems in the real exam's format (same number of problems, point split, open-book rules, time), mixing the predicted types with new numbers. Fold the solutions: worked, numbers computed by code, points per part, and the trap each part tests. Tag constructed data *constructed* and slide or homework data with its source.
9. **Numbers to Sanity-Check**: a table of quantities with values and what each is used for.
10. **Self-Test**: conceptual questions, answer folded, with a link to the notes section. No numerical problems here.
11. **Study Plan**: sessions with suggested lengths, ending with a timed run of the mock exam; checkboxes saved in the browser, a "n of m done" counter.
12. For a final exam, add **Cross-Chapter Links** (how chapters feed each other) and mark which chapters are new, not yet examined.
13. **Score After the Exam** (the last section): empty tables to fill in after the exam, so it can be scored: one row per predicted problem type (predicted type, actual problem, result Hit, Partial or Miss, exam points) and one row per mock exam problem and part (mock problem, matching real problem, match strong, partial or none, point weights). My Reflection page for this exam fills them in; do not fill them in now.
14. Section order: Overview, Rules From the Last Exam, Coverage Map, Equation Sheet, Problem Patterns, Past Work Analysis, Predicted Problems, Mock Exam, Numbers to Sanity-Check, Self-Test, Study Plan, Score After the Exam.

## Method

1. **Plan the task list first** and keep it updated. The last step is always checking.
2. **Read the inputs**: render scanned pages to images at about 110 dpi for reading and 220 dpi for crops of handwriting. Transcribe the grader's marks and comments exactly.
3. **Solve before writing**: compute every number in the solutions with code. If a result contradicts the problem statement, find out why before writing (for example check a second-law balance, the table range, the units).
4. **Gather the material before opening any skill or template**, then build in stages (header and scoreboard, then each card, then the endings).
5. **Verify** before publishing: open the page at 390 and 1100 (px) wide in a headless browser, confirm no sideways scroll, no script errors and that all folds are closed. (Math may not render offline in a sandbox; that is not a bug.)
6. {{PUBLISH_STEP}}
7. {{UPDATE_STEP}}
8. **Zip**: when I ask, deliver one zip per course with the pages (homework grades and helpers together), named with the same names as the pages.
9. **Report briefly**: the score, what the page contains, and anything you assumed, estimated or could not read. Do not recap the steps.

## Honesty Rules

1. Quote graders exactly; mark your own reasoning as yours.
2. Never present an estimate as stated data; use the chips.
3. Say plainly when an exam or posted solution has an error, and which answer you used.
4. When the grader's scores and your reading of the work disagree, report the grader's scores.
5. Do not give the numeric answers in the Helper; give method and checks.
6. Ask me only when a decision is expensive to redo and ambiguous (for example which homeworks to cover). Otherwise take the most reasonable reading, say which reading you took at the top of your reply, and continue.
