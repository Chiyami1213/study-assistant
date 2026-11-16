# Interactive Study Guide Rules

Applies to every interactive study guide I ask for, for any course. The sections Format and Navigation, Math, Units and Dimensions, Text Style and Layout Checks also apply to homework and exam pages (see Homework and Exam Pages).

## Format and Navigation

1. **HTML format**, one self-contained file per guide.
2. **Linkable table of contents on the left**
   - highlights the current section while scrolling
   - collapsible subsections
   - collapses into a menu button on phone-width screens
3. **Dark mode** follows the system theme; boxes, red edges and highlights stay visible.
4. **Clean printing**: boxes and colors kept, table of contents hidden.
5. **Granularity**: per lecture or per chapter, following how the course's slides are organized.
6. **File naming**: `<COURSE> Chapter x Notes`, e.g. `<COURSE> Chapter 1 Notes.html`.
7. **Delivery**: one zip per course containing all of its guides.

## Page Structure (in order)

1. **Mind maps** (before section 1)
   - same font as the rest of the page (no handwriting font)
   - horizontal tree: chapter root box on the left (title + its key equation), numbered color-coded section boxes, then leaf boxes per subsection with the key idea or equation in LaTeX
   - each section box collapses/expands (▸/▾), with **Open all** and **Close all** buttons
   - ending sections appear as nodes too
   - every node is clickable and jumps to its section
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
   3. **Quiz** (last)

## Numerical Examples

1. **One worked numerical example at the end of each applicable section** (sections that are purely conceptual or cross-references get none).
2. **Taken from the lecture slides.** If the slides have one, use it; if they have two or more, use the most important one.
3. If the slides have none for that section, a constructed example may be used, clearly tagged *constructed* (slide examples are tagged *from slides*), with a source line naming the slide.
4. **Folded by default** (click to open); printed unfolded.
5. Same math rules as the notes: boxed equations, numbered (E5.1), (E5.2)…, final answer in a red box, units in parentheses, variable hover.
6. **System diagrams are interactive and animated** where that makes the example easier to understand: sliders or toggles for the given values, a button to run the process, live readouts that match the solution. Animations run only while the example is open and on screen, and respect reduced-motion settings.
7. **The system diagram sits at the top right of the example box**, with the problem statement beside it; the worked solution starts full width below. On phones the diagram stacks above the problem statement.

## Derivations (Chapter and Lecture Notes)

1. **Optional folded blocks**: the derivation of every important (red-edge) equation goes in the notes as a folded "✎ Derivation · optional · title" block (dashed left border, italic muted summary, pencil style), placed directly under the equation it derives. It is closed by default, opens when a link or hash points inside it, and opens for print.
2. **Which equations**: governing equations and final results whose derivation is in the lecture or is the standard route (definitions that are only stated, tables and data values get none). A derivation the lecture skips is still written when it is short and needed to trust the result.
3. **Build**: start from equations already numbered in the notes and link them; each step is one boxed equation with a black edge and a local label (a), (b), …; the last step names the numbered equation (red-edge, with its number, stays in the main text). Say what each step uses, one short sentence between boxes. No new notation: keep the chapter's symbols, hats and bars.
4. **Checks before delivery**: every expression parses in a LaTeX checker, math is not wider than the page at 390 (px), and the folds do not change the numbering or the table of contents.
5. **All notes of a course**: when the rule is added to a course, every chapter or lecture page gets the blocks, not only the one being edited, and {{REPUBLISH}} with the downloadable zip regenerated.

## Labs

1. **Named by section number**, for every course: `Section x.x Lab`. If one section has more than one lab: `Section x.x Lab 1`, `Section x.x Lab 2`, … (in page order).
2. Every reference to a lab in the text, errata or examples uses the same name.

## Math

1. **LaTeX** for all math and equations.
2. **No `/` for division**: use `\frac{}{}`.
3. **Vectors** always carry an arrow: `\vec{u}`, `\vec{F}`.
4. **Every equation is boxed**
   - black edge: regular equations
   - red edge: final results of derivations, plus governing equations and definitions needed for exams
5. **Equation numbering** by section, e.g. (3.2), so text, errata, and quiz can reference them.
6. **Variable hover**: hovering any variable in an equation highlights it and shows its meaning and units.

## Units and Dimensions

1. **Units in parentheses**, e.g. (m), (kg).
2. **Multiplied units use a center dot**: (Pa·s), (N·m), (kg·m⁻³).
3. **Dimensions in square brackets**: [L] length, [T] time, [M] mass.

## Text Style

1. **Headers and section titles** use APA title-case capitalization.
2. **Helper boxes** (mouse hover) are all lowercase, except math symbols, which keep their case.
3. **Bullet points** where they make content easier to understand: lists of conditions, properties, cases or steps, and dense multi-point paragraphs. Keep connected reasoning (derivations, explanations) as prose.

## Quiz

1. **Conceptual multiple-choice questions only.**
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

## Highlighter

1. **Select text, pick a color**: a small bar appears above any selection with four colors (yellow, green, pink, blue). Clicking an existing highlight lets you recolor it or remove it (✕).
2. **Highlights panel** (bottom left): every highlight in page order, labeled with its subsection or example; click to jump there (folded examples open); **Clear all** button.
3. **Works on** notes, definitions, tables, errata, examples, and whole equations (an equation is highlighted as one piece); a selection can span several paragraphs or list items.
4. **Not on** labs, interactive diagrams, the quiz, the mind map, or the table of contents.
5. **Saved in the browser, per guide**, and restored when the page is reopened. It turns on once the math has finished rendering, so positions are measured on the final page. Highlights in a paragraph whose wording changes in a later version are dropped; all others stay.
6. Highlights print in color; the highlighter controls are hidden when printing.

## Layout Checks (Every Guide, Before Delivery)

1. **Short inline chips never split across lines**: legend samples (red edge / black edge), the ? button, type pills, quiz tags, example tags, equation numbers. Long labels (section names, source chips) are allowed to wrap.
2. **Header paragraphs share one width**, so there is no ragged empty block beside the legend.
3. **No sideways scrolling** at any width; wide content (tables, equations, the mind map) scrolls inside its own box.
4. **Math always renders at text size**, including inside diagrams, sliders and readouts: layout rules for drawings never apply to the math engine's own output. The check drops a test formula into every kind of container and fails if it renders oversized.
5. Checked automatically at 1360, 1100, 768 and 390 (px) wide, light and dark, with all examples unfolded. Any failure is fixed before the file is sent.
6. A formatting issue found on one page is fixed on every page of the same type, not just the one where it was noticed.
