# Interactive Study Guide Rules

Applies to every interactive study guide I ask for, for any course. The sections How to Use These Rules, Format and Navigation, Math, Units and Dimensions, Text Style, Interactive Tools, Language Courses: Native Script, Content Beyond the Slides and Errors in Sources and Layout Checks also apply to homework and exam pages (see Homework and Exam Pages).

## How to Use These Rules: Base Plus Course-Type Profile

These rules are a **base** that applies to every course, plus **course-type profiles** that add, adapt or drop things for the kind of course.

1. **Pick the type(s)** of the course from its syllabus, slides and textbook (a course can have two, for example Biochemistry = Biology + Chemistry, or Computational Physics = Math/Physics + Programming), and say which in your reply.
2. **Apply the base**, then the profile(s) below. A profile never lowers the base's checks (themes, printing, layout, quiz, highlighter, naming); it changes which tools and content blocks the guide uses.
3. **Drop what does not fit** (for example no equations list in a pure-humanities course, no Units rules without units), and say so rather than leaving empty sections.
4. **Source type**: lecture-based courses follow the slides first; textbook-only courses use the textbook as the main source, tag content "from textbook" instead of "from slides", and label additions "Beyond the textbook" (the grey callout).

| Type | Add or emphasize | Adapt or drop |
|---|---|---|
| **Math, physics** | LaTeX throughout, boxed and numbered equations, derivations, hover variables, Guided examples, interactive plots with sliders, 3D when geometry helps | none |
| **Engineering** | everything in Math/Physics, plus 3D interactive and animated models, as many labs and plots as help, system and block diagrams, units and dimensions, physical-constants list, homework and exam helper pages | none |
| **Chemistry** | structures and reaction mechanisms as step-through animations (curved arrows, intermediates), 3D molecule viewer (rotate, ball-and-stick and space-filling), energy diagrams, equilibrium and kinetics sliders, periodic-trend plots, unit conversions | equation numbering only where equations carry the course |
| **Biology, anatomy, medicine** | detailed original figures with clickable labels and Test me, rotatable 3D for structures, pathway and flow strips, readable-prose forms (bullets, mini mind maps, tab summaries), clinical-case style quiz items | equations and constants only where used |
| **Language courses** | native script beside romanization (see Language Courses: Native Script), glossed examples, audio or pitch widgets only when the course teaches them, drills with instant feedback, conjugation or pattern builders | math, equations, units |
| **Finance, economics, markets** | interactive charts including candlestick or OHLC with zoom and indicator toggles, supply and demand and payoff diagrams with sliders, worked numerical examples with Guided mode, a formula sheet, scenario sliders (rates, volatility), glossary of terms | physical constants, 3D |
| **Programming, CS, data** | syntax-highlighted code blocks with copy buttons, step-through code or algorithm animations with a variable watch, complexity plots, trace tables, runnable mini-demos where safe, output-prediction quiz items | units and dimensions |
| **Statistics, probability** | distribution explorers with sliders, simulation labs (sampling, CLT, regression), worked examples with Guided mode, formula sheet, decision flowcharts for choosing a test | none |
| **Humanities, social science, law** | timelines, concept maps, comparison tables, key-term glossary, argument or case summaries in the readable-prose forms, primary-source quotes with citations, essay-style conceptual quiz questions | equations, labs, units, derivations |
| **Textbook-only courses** (any type) | textbook as main source, "from textbook" tags, grey "Beyond the textbook" callouts, chapter structure as the guide structure | slide-based rules (replace "slides" with "textbook") |

## Format and Navigation

1. **HTML format**, one self-contained file per guide.
2. **Linkable table of contents on the left**
   - highlights the current section while scrolling
   - collapsible subsections
   - collapses into a menu button on phone-width screens
3. **Light and dark modes** both ship in every guide and follow the system theme by default.
   - **Light mode** is the base theme (colors defined as tokens on `:root`, white surface, dark ink) and is checked as carefully as dark mode: contrast, boxes, red edges, highlights, diagrams and canvases all stay readable.
   - **Dark mode** is defined under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])` and again under `:root[data-theme="dark"]`, so a toggle can force either mode; boxes, red edges and highlights stay visible.
   - Nothing is hard-coded to one theme: no fixed white or black in text, plots, canvas drawings, figures or MathJax output.
   - **Theme toggle**: every guide has a fixed Light/Dark button in the top-right corner (class `theme-btn`). It starts on the system theme, sets `data-theme` on the root and saves the choice in `localStorage` (inside `try/catch`). On phones it sits across from the Contents button so they never overlap. It is hidden when printing and never covers the header text. (My app hides this button while reading and makes the page follow the app's own Light or Dark setting; the button is for when the page is opened outside the app.)
4. **Clean printing**: boxes and colors kept, table of contents hidden.
5. **Granularity**: per lecture or per chapter, following how the course's slides are organized.
6. **File naming**: `<COURSE> Chapter x Notes`, e.g. `<COURSE> Chapter 1 Notes.html`, with no space inside the course name.
7. **Delivery**: one zip per course containing all of its guides.
8. **Build source**: when the guides come from a build script (templates, shared JavaScript, checkers), keep it with the guides so a later chat can rebuild them.

## Page Structure (in order)

1. **Mind maps** (before section 1)
   - same font as the rest of the page (no handwriting font)
   - horizontal tree: chapter root box on the left (title + its key equation), numbered color-coded section boxes, then leaf boxes per subsection with the key idea or equation in LaTeX
   - each section box collapses/expands (▸/▾), with **Open all** and **Close all** buttons
   - ending sections appear as nodes too
   - every node is clickable and jumps to its section
   - **The root box fits its content.** The root's key equations are written one formula per line (split a long chain such as `a, \qquad b, \qquad c` into separate lines); the box grows to the widest formula (up to a cap) and no equation scrolls, clips or overlaps a neighbouring box. If one formula is wider than the cap, shorten the root equation instead of shrinking the font. The root keeps a clear gap to the section boxes (at least 20 px at 1360 px wide).
2. **Lecture/chapter sections** (numbered)
   - **local mind maps** may be added inside a section when they make the content easier to understand (e.g. classifying system types, connecting the forms of a law, comparing two cases); same visual style as the overview map, compact and always open, leaves may carry math and links to equation numbers
   - use them only where they help; don't add one to every section
3. **Ending sections**, in this order:
   1. **Equation Sheet**: opens with a **Physical Constants** list, then **Key Equations** (every red-edge equation, each number linking back to its derivation)
      - constants are listed in rows like the Key Equations list: name on the left, then the symbol, value and units in parentheses, and a ? note on what it does physically
      - the units are written inside the math, in the same style as units in the equations, e.g. \(e = 1.602\times10^{-19}\ (\mathrm{C})\)
      - a guide that computes with no physical constants (pure math, or ħ = 1 throughout) has no constants list
      - constants are not boxed (red and black edge boxes are only for equations), and carry no "used in" list
      - constant symbols are hoverable like equation variables (description, units, dimensions)
      - the values are the ones every number in the guide is computed with (slide values where the guide uses them, marked as such)
   2. **Errata**: errors in my lecture notes, the course slides, and the textbook, grouped by source
   3. **Quiz** (last), in three parts (see Quiz), followed by its own **Guided Numerical Practice** section

## Numerical Examples

1. **One worked numerical example at the end of each applicable section** (sections that are purely conceptual or cross-references get none).
2. **Taken from the lecture slides.** If the slides have one, use it; if they have two or more, use the most important one.
3. If the slides have none for that section, a constructed example may be used, clearly tagged *constructed* (slide examples are tagged *from slides*), with a source line naming the slide. Every example carries one of the two tags.
4. **Folded by default** (click to open); printed unfolded.
5. Same math rules as the notes: boxed equations, numbered (E5.1), (E5.2)…, final answer in a red box, units in parentheses, variable hover.
6. **System diagrams are interactive and animated** where that makes the example easier to understand: sliders or toggles for the given values, a button to run the process, live readouts that match the solution. Animations run only while the example is open and on screen, and respect reduced-motion settings.
7. **The system diagram sits at the top right of the example box**, with the problem statement beside it; the worked solution starts full width below. On phones the diagram stacks above the problem statement.

### Guided Mode (Interactive Steps)

Every numerical worked example has a second, interactive **Guided** mode next to the normal solution.

1. **Mode switch**: inside the example body, above the solution, a segmented control **Guided** (default) and **Worked solution**. Worked solution is the existing solution, unchanged; only one pane is visible at a time.
2. **Step 1 is always Assumptions**: before any method, the student picks the assumptions the problem needs (which model applies, what is neglected, what is constant). They are then shown as written text, not an equation box.
3. **Method steps are multiple choice**: each step asks one question about the method (which equation, which quantity, which unit conversion, what the result should look like) or a simple calculation. Three or four options, one correct, and every option carries a short reason shown after the choice. The wrong options are real student mistakes.
4. **The tool does the hard math**: after the right pick, the step shows the arithmetic as a boxed equation with substituted numbers and result, numbered (E5.1), (E5.2)…. The student never runs a calculator. A **Show me this step** button reveals a step without penalty.
5. **One step in view, in the same space**: finished steps are not stacked below and the example does not grow. Answering swaps the content in place and **Next step ▸** moves on.
6. **Progress bar changes colour only** (done, current): equal-width segments with "Step n of N", always the same height; they never grow, shrink or move. Guided-mode classes are prefixed (`g-`) so no dashed border, spacing or other style leaks in from a similarly named class.
7. **Wrong answers**: the option is marked, its reason shown, and the student tries again.
8. **Finish**: the final answer in a red-edge box with units in parentheses, a **Restart this example** button, and the Worked-solution toggle stays available.
9. **Math** follows the usual rules (LaTeX in options, reasons and boxes, `\vec` for vectors, units in parentheses with a center dot). Option order rotates per step and example, and reasons never refer to an option by position.
10. **Same content in both modes**: every number is computed once in code and matches the worked solution; the worked pane also lists the assumptions. Printing shows only the worked solution.
11. **Data format**: the examples' data is one JSON array, `window.GD_DATA = [{"id", "steps": [{"tag", "q", "o": [[text, 1|0, reason], ...], "done", "plain"?}], "final"}]`. Escape every backslash in the strings; `tag` is plain text. My app reads this array to run the guided practice of the Quiz (see Quiz, Part 3).
12. **Build notes**: clear the old equations before the new step renders, re-typeset one batch at a time (serialized), turn the MathJax font cache off so equations do not share glyph definitions, and call `typesetClear` before re-typesetting a re-rendered pane; name the finished-state class `g-fin`, not `done`.
13. Applies to every example of a guide, and to all guides of a course when the rule is added.

## Derivations (Chapter and Lecture Notes)

1. **Optional folded blocks**: the derivation of every important (red-edge) equation goes in the notes as a folded "✎ Derivation · optional · title" block (dashed left border, italic muted summary, pencil style), placed directly under the equation it derives. It is closed by default, opens when a link or hash points inside it, and opens for print.
2. **Which equations**: governing equations and final results whose derivation is in the lecture or is the standard route (definitions that are only stated, tables and data values get none). A derivation the lecture skips is still written when it is short and needed to trust the result.
3. **Build**: start from equations already numbered in the notes and link them; each step is one boxed equation with a black edge and a local label (a), (b), …; the last step names the numbered equation (red-edge, with its number, stays in the main text). Say what each step uses, one short sentence between boxes. No new notation: keep the chapter's symbols, hats and bars.
4. **Checks before delivery**: every expression parses in a LaTeX checker, math is not wider than the page at 390 (px), and the folds do not change the numbering or the table of contents.
5. **All notes of a course**: when the rule is added to a course, every chapter or lecture page gets the blocks, not only the one being edited, and {{REPUBLISH}} with the downloadable zip regenerated.

## Labs

1. **Named by section number**, for every course: `Section x.x Lab`. If one section has more than one lab: `Section x.x Lab 1`, `Section x.x Lab 2`, … (in page order).
2. Every reference to a lab in the text, errata or examples uses the same name.

## Interactive Tools

Everything that moves or reads out (labs, example diagrams, plots) is held to the same rules as the notes, and is checked by looking at it, not only by parsing it.

### Math in Interactive Elements

1. **All math is LaTeX everywhere in an interactive element** (a quantity such as \(v_e\) is a real subscript, never `v_e` with an underscore): titles and descriptions, slider labels, **button and toggle labels** (a transfer-function selector shows \(\frac{1}{s(s+1)(s+2)}\), not `1/[s(s+1)(s+2)]`), readouts, axis titles, legends, canvas labels, tooltips and quiz options. No Unicode math as plain text: Greek letters, subscripts, superscripts, `⁄`, `≈`, `≥`, `°` inside a formula. A bare word such as "open loop" stays text.
2. **A readout is a sentence with LaTeX inside**: write `\(y_{ss} = 0.9000\)`, `\(\zeta = 1.118\)`, `\(\angle L(s_0) = -180^\circ\)`, not `y_ss = 0.9000`. Numbers computed in JavaScript are inserted into the LaTeX string, then typeset after every update.
3. **No `/` for division** in any of these, including slider labels and button labels; use `\frac{}{}`. Units in tool text follow the Units rules.
4. **Pitfalls that broke guides**: `%` inside `\text{}` must be `\%`; write `<` and `>` as `\lt` and `\gt` inside JavaScript strings (never `&lt;` or `&gt;`); a label drawn on a canvas goes through the same LaTeX path as the page (no separate unconverted string); a string that still shows a literal `\(` on the page is a failure.
5. After a build, **scan the rendered page for plain-text math** in controls, readouts and labels (Greek letters, `_`, `^`, `⁄`, ` = ` between single letters outside `\(...\)`); every hit is converted.

### Controls and Spacing

1. **Every control row has the same inset as the slider rows** (at least 12 px from the lab box border on every side). A row of buttons or a segmented selector never touches or overhangs the box border, at any width.
2. Buttons in a row have the same height; LaTeX inside a button is vertically centred and does not change the row height between selections; the row wraps onto a second line instead of overflowing.
3. Slider labels, values and buttons never overlap each other or the plot above them.

### Labels and Overlaps

1. **Nothing is drawn on top of anything else that carries meaning.** Vector and phasor labels sit just beyond the arrow tip, along the arrow's direction; angle labels sit on the opposite side of the pole or point from the line they describe; labels of different objects never overlap each other.
2. **Collision handling**: every canvas that places several labels runs a simple placement pass (compare bounding boxes, push a colliding label along the arrow direction or up or down by one line height, repeat a few times). A label near an axis or arrow keeps a halo or opaque background so the line does not run through the text.
3. **Block diagrams**: every box and summing junction is filled opaquely so wires never show through a label; wires end at the box edge; a feedback wire does not cross a label.
4. **Plot limits** keep every marker, label and arrow inside the plot area at the default slider values and at both slider extremes.

### Continuous Traces

1. **A curve that is physically continuous is drawn continuous.** Root loci, Nyquist and Bode curves, phase portraits, trajectories and any parametric trace are sampled adaptively: where two consecutive samples differ by more than a small fraction of the plot size, insert more samples between them (bisect the parameter, up to a depth limit) until the jump is small. Branches are matched between neighbouring samples by nearest root with a global assignment, not by sorted order.
2. **A kink, gap or straight chord across a curve is a bug.** Check the plot where branches meet the real axis, at break-in and break-away points, at crossings of the imaginary axis, and near poles.
3. **Numerical check**: compute the largest jump between consecutive samples of each trace (in plot units) and fail the build above a small threshold, except at a true discontinuity, which is drawn as separate segments.

### Interactive Models, Plots and Labs for Engineering and STEM

For engineering and STEM courses, **use interactive visuals wherever they help understanding**, not only where the lecture happens to show a figure.

1. **3D interactive and animated models** (rotatable, with play/pause where motion matters) whenever the geometry or motion is easier to grasp in 3D: orbits, flows, fields, mechanisms, structures, thrusters, anatomy. Same controls and rules as Rotatable 3D Figures.
2. **As many interactive plots and labs as help visualize the content**: sliders for the parameters of an equation, live readouts, and plots that update. Prefer adding one to leaving a key equation, trend or effect as text.
3. Use them where they teach something (a dependence, a limit, a trade-off, a mechanism); skip decoration.

### Figures

1. **Every figure is a detailed, anatomically or physically accurate original drawing**, never a box-and-arrow placeholder. Use shading, real shapes and leader-line labels.
2. **Checked against the course textbook's matching figure, never traced from it.** If the textbook figure itself is wrong, log it in Errata instead of copying the mistake.
3. Every labelled part is clickable, and a **Test me** mode hides its name.
4. No "upload my textbook figure" button.

### Rotatable 3D Figures

1. Any figure that shows a 3D structure (planes, cutaways, layered solids) can be rotated: drag the figure, or use the arrow buttons, view presets (Front, Side, Top) and Reset.
2. A drag never triggers a part click.
3. With reduced motion set, the figure still works with no JavaScript motion.
4. When the geometry of a key equation benefits from it (for example a beam divergence angle), put a rotatable 3D interactive tool next to that equation.

### Plots and Charts

1. **Every plotted curve has its own distinct color**, different from every other series and from any field line, axis or reference line already in the figure.
2. **The legend shows a line sample matching each curve's dash style** and wraps onto several lines on phones.
3. **Bars and fills never turn black or too dark in dark mode**: do not reset fills in a way that wipes the series color; check every chart in dark mode.

### Looking at It

1. Every lab and example diagram of a new guide is **rendered and viewed** at 1360 and 390 (px), light and dark, at default values and with sliders at both extremes; a glitch found by eye is fixed on every guide of the same type.
2. Screenshots are taken after the math has finished rendering, not before.

## Math

1. **LaTeX** for all math and equations.
2. **No `/` for division**: use `\frac{}{}`.
3. **Vectors** always carry an arrow: `\vec{u}`, `\vec{F}`.
4. **Every equation is boxed**
   - black edge: regular equations
   - red edge: final results of derivations, plus governing equations and definitions needed for exams
5. **Equation numbering** by section, e.g. (3.2), so text, errata, and quiz can reference them.
6. **Variable hover**: hovering any variable in an equation highlights it and shows its meaning and units.
7. **Closed integrals use `\oint`**, never `\oiint` (or `\oiiint`): MathJax does not render them. For a closed surface integral write `\oint_{S}`.
8. **Braces on every subscript and superscript**: write `C_{n}H_{m}`, `C_{n}H_{2n+2}`, `x_{i}^{2}`, never `C_nH_m` or a bare `_` or `^` chained after another. KaTeX accepts the bare form but MathJax 3 fails with "Double subscripts" or "Double exponent".
9. **Check every formula with real MathJax 3** (the same version the page loads, not KaTeX alone) before delivering; any math error shown on the page is fixed on every chapter of the course.

## Units and Dimensions

1. **Units in parentheses**, e.g. (m), (kg).
2. **Multiplied units use a center dot**: (Pa·s), (N·m), (kg·m⁻³).
3. **Dimensions in square brackets**: [L] length, [T] time, [M] mass.

## Text Style

1. **Headers and section titles** use APA title-case capitalization.
2. **Helper boxes** (mouse hover) are all lowercase, except math symbols, which keep their case.
3. **Bullet points** where they make content easier to understand: lists of conditions, properties, cases or steps, and dense multi-point paragraphs. Keep connected reasoning (derivations, explanations) as prose.
4. **Readable prose, no walls of paragraphs.** A paragraph of more than about 80 words, or two long paragraphs in a row, is restructured, and every fact, number and key term is kept. Pick the form that fits the content:
   - **Bullets**: open with a bold lead term, with sub-bullets for details. Use for descriptive text.
   - **Small mind map**: a root node with a connector spine to 2 to 5 child cards, each with a title, a short key phrase and bullets. Use for content that splits into categories or comparisons. Each card collapses on click, and a **Hide details** button collapses every card to its heading for self-testing.
   - **Interactive summary**: a tabbed panel, or a numbered stepper for sequences, with Prev/Next, a position counter, arrow-key navigation and a **Show all** toggle. Use for parallel items and for multi-step processes.
   - Short flow strips (box → box) can show a pathway or lineage.
   - Every panel shows when printed.
   - After restructuring, check automatically that no number or bold term from the original text is missing.

## Quiz

The Quiz has **three parts**, all under the Quiz tab of my app, taking about 18 minutes in all. The Quiz section opens with a short line saying so, with the number of questions and the minutes of each part.

### Part 1: Conceptual Questions (Untimed)

1. **Conceptual multiple-choice questions only**, about 12 for a chapter (more for a long one), in `<div id="qBox">`, with the questions in the array `Q` (see App Format).
2. **Based on the lecture slides.** Textbook material or textbook problems are used only when that content is worth a lot, and those questions are tagged *textbook*.
3. **Every slide-based subsection gets at least 1 question**, up to 3 depending on its importance and length. Textbook-only subsections get a question only under rule 2.
4. Instant feedback with a short explanation of the correct answer.
5. **Each question is labeled** with the subsection it tests.
6. **Hint button** on every question: reveals a nudge without giving the answer away.
7. **Check notes button** on every question: jumps to the subsection it tests, and a floating **Back to quiz question N** button returns to the question.
8. **Help use is recorded**
   - per question: "hint used" and "notes checked ×n" tags, marked "after answering" if used after the answer
   - results panel: answered, correct, correct with no help, hints used, notes checked
   - review list linking to subsections that were missed or needed help
   - saved in the browser so it survives reloads; a Reset button clears it
9. **Answer options are shuffled**, so the correct answer is spread evenly across positions (never mostly the same letter). Each question keeps a fixed order between visits, so saved answers and results still line up. Explanations and hints never refer to an option by its position ("option B").

### Part 2: Speed Round (90 Seconds)

1. A round of **8 quick-reaction questions in 90 seconds**, drawn at random from a **bank of 12 to 15** (so a retake differs), written as `var BANK=[[question, [options], index of the correct option, explanation], ...]` and `N=8,LIMIT=90` in the page's script, inside `<div id="speed">` (the questions in `<div id="srBox">`) in the `quiz` section, below Part 1.
2. **None of the questions repeats a question of Part 1.** They are short (a commutator, a unit, a limit, a sign), three options, answered on instinct.
3. A clock and a bar count down; the next question appears as soon as one is answered; keys 1 to 3 pick. **Misses are reviewed at the end and come back first in the next round**; the best score is remembered in the browser. There is no Hint or Check notes.
4. Everything the page shows follows the Math and Units rules (LaTeX in questions and options).

### Part 3: Guided Numerical Practice

1. Its own section `<section id="gpractice">` with the heading **Guided Numerical Practice**, right after the `quiz` section (about 4 minutes for each problem, two problems for a chapter).
2. Each problem is a worked example in `<details class="example" id="ex-P1">`, `ex-P2`, ... in **Guided mode** (see Guided Mode), with a line saying why it was chosen (for example "Like HW 3 P2"): the problem types most likely on homework and exams.
3. The steps and options are in the `GD_DATA` array like every other example.

## Highlighter

1. **Select text, pick a color**: a small bar appears above any selection with four colors (yellow, green, pink, blue). Clicking an existing highlight lets you recolor it or remove it (✕).
2. **Highlights panel** (bottom left): every highlight in page order, labeled with its subsection or example; click to jump there (folded examples open); **Clear all** button.
3. **Works on** notes, definitions, tables, errata, examples, and whole equations (an equation is highlighted as one piece); a selection can span several paragraphs or list items.
4. **Not on** labs, interactive diagrams, the quiz, the mind map, or the table of contents.
5. **Saved in the browser, per guide** (`localStorage` key `sg:<document title>:highlights`), and restored when the page is reopened. It turns on once the math has finished rendering, so positions are measured on the final page. Highlights in a paragraph whose wording changes in a later version are dropped; all others stay. (My app also keeps them inside the stored page, so they survive a new import.)
6. Highlights print in color; the highlighter controls are hidden when printing.

## Language Courses: Native Script

For a language course (for example Japanese), **every example, term, phrase and sentence in the target language shows its native script next to the romanization**: kanji where a native writer would use it, kana otherwise. This covers prose, bold terms, interlinear glosses, drills, quiz options, guided-example options and widget text. Applies to any language with its own writing system (Japanese, Chinese, Korean and others).

1. Bare particles and affixes quoted inside an explanation, and English, stay romanization-only, except in sections that are about those particles.
2. Keep a per-chapter map (romanization to native script) in the build source and add the script from it automatically, including in widgets at runtime; new romanization needs a new map line.
3. Run a coverage check that clicks every widget and lists unmapped romanization; only particles and English may remain.
4. Do not reconstruct native-script text for in-copyright literary quotations that the source gives only in romanization; leave those romanized.

## Content Beyond the Slides and Errors in Sources

1. **Content added beyond the slides** (extra derivations, textbook material, clarifications) goes in a grey callout labelled **beyond the slides**, so slide content and additions are always distinguishable.
2. **A slide typo or a textbook error is never silently fixed.** The guide uses the correct form, and the error is recorded in the Errata section, grouped by source, with the check that exposed it.

## Layout Checks (Every Guide, Before Delivery)

1. **Short inline chips never split across lines**: legend samples (red edge / black edge), the ? button, type pills, quiz tags, example tags, equation numbers. Long labels (section names, source chips) are allowed to wrap.
2. **Header paragraphs share one width**, so there is no ragged empty block beside the legend.
3. **No sideways scrolling** at any width; wide content (tables, equations, the mind map) scrolls inside its own box.
4. **Only wide display equations may scroll horizontally, never inline math.** A CSS rule that sets overflow on math containers must target display equations only; inline math never gets a scroll bar. Checked by measuring every inline math element for a scroll width larger than its width.
5. **Math always renders at text size**, including inside diagrams, sliders and readouts: layout rules for drawings never apply to the math engine's own output. The check drops a test formula into every kind of container and fails if it renders oversized.
6. Checked automatically at 1360, 1100, 768 and 390 (px) wide, light and dark, with all examples unfolded. Any failure is fixed before the file is sent.
7. A formatting issue found on one page is fixed on every page of the same type, not just the one where it was noticed.
8. **Guided mode**: click through every step of every example (and of the Guided Numerical Practice) with no page errors; the Worked-solution toggle shows the original solution; the progress bar never changes size. Run a speed round to its end and check the review of the misses.
9. **Measured, not assumed**, in the same run:
   - the mind-map root box: no equation wider than its box, a gap to the section boxes, no inner scrollbar
   - every control row in a lab: left inset at least 12 px
   - plain-text math in controls, readouts and labels: zero hits (see Interactive Tools)
   - literal `\(` or `\[` visible on the page: zero
   - largest jump between consecutive samples of every continuous trace (see Continuous Traces)
   - canvas labels: no two label boxes overlap, none overlaps an arrow tip, in the default state of every lab
10. **Order of fixes**: after changing a shared style or script, rebuild every guide of the course and re-run all checks on all of them; send the zip only after that.
