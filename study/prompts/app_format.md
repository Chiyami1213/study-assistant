## All Pages

I will import the finished page into my study app, which recognizes a page only when it follows the format below. These requirements come first: when they conflict with the style rules, keep the style but never break the format.

1. **One self-contained `.html` file**: inline CSS and inline JavaScript, no build step, no external images, no links to other pages (links to places inside the same page, `#anchors`, are fine). The only outside resources allowed are MathJax and the Google Fonts stylesheet.
2. **Math**: MathJax 3.2.2 from `https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js`, written `\( ... \)` inline and `\[ ... \]` for display.
3. **Light and dark** through `prefers-color-scheme`.
4. **The `<title>` and the file name are the same**: `<FILE>`. The app reads the type of the page, the number and the course from the file name, so use exactly this name and never rename it.
5. **Delivery**: {{DELIVERY}}

## Study Guide

**File name:** `<FILE>.html` (for example `<COURSE> Chapter 1 Notes.html`). In my app the page is a Library file of type Notes with the lecture or chapter number.

The page is a list of `<section id="...">` blocks, each starting with an `<h2>`. My app shows one tab for each part it finds, recognized by the `id`:

| `id` | Part | Tab |
|---|---|---|
| `mindmap` | the overview mind map | Mind Map |
| `s1`, `s2`, `s3`, ... | the numbered lecture or chapter sections (everything that is not one of the parts below) | Notes (opens at the first) |
| `eqsheet` (or `sheet`) | Equation Sheet | Equation Sheet |
| `assumptions` | Assumptions (when the guide has them) | Assumptions |
| `errata` | Errata | Errata |
| `quiz` | Quiz | Quiz |

Rules:

1. Use these ids exactly, in this order: `mindmap` first, then `s1`, `s2`, ..., then `eqsheet`, `assumptions` (if any), `errata`, `quiz`. A part the guide does not have gets no section and no tab.
2. Give every subsection heading an id built from its section: `s2-1`, `s2-2`, ... (the heading `<h3 id="s2-2">`). Give every worked example an id `ex-1`, `ex-2`, ... in page order. My other pages link to these ids.
3. Equations carry their number in the box as in the style rules, and the equation sheet links back to them.
4. **The quiz data** follows the Quiz rules and is written as one JavaScript array in the page's script, named `Q`, one entry for each question in this exact shape (the app reads it for the Quiz tab of the course page, and the page can run its own quiz from the same array):

   ```js
   const Q = [
     ["s2-2", "Question text, with math as \( ... \)", ["Option 1", "Option 2", "Option 3", "Option 4"], 1, "Why the correct answer is right.", "A hint that does not give the answer away.", false],
   ];
   ```

   The entries are: the id of the subsection the question tests (`s2-2`), the question, the list of options, the **zero-based index of the correct option** (`1` is the second option), the explanation, the hint, and `true` only for a question that comes from the textbook (else `false`). Use plain strings only (no functions, no variables). Put the quiz itself inside the `quiz` section; if the page runs its own quiz script, give the element that holds it `id="qBox"` and the page runs it as it is.
5. Keep the page responsive; it is shown in a panel next to a slide or textbook viewer.

## Homework Helper

**File name:** `<FILE>.html`, which must contain the word **Helper** (for example `<COURSE> Homework 4 Helper.html`). In my app it is paired with the problem file of the same course and homework number and is shown beside it.

1. The title ends with the homework number: `<COURSE> Homework <N> Helper`.
2. **One card per problem**: `<section class="card" id="p1">`, `id="p2"`, ... where the number is exactly the problem number in the homework PDF. A click on a card shows that problem on the problem file.
3. **One block per sub-problem inside the card**: `<div class="part">` with its letter in a `.pl` label written exactly as the PDF writes it, for example `<span class="pl">a)</span>`. A click on a part shows that part's lines on the problem file. Problem numbers and letters must match the numbering of the problem PDF, because my app finds them by their text.
4. Links to my notes (see **Links**).

## Homework Grade Explanation

**File name:** `<FILE>.html`, which must contain the word **Grades** or **Explanation** (for example `<COURSE> Homework 4 Grades.html`). In my app it is shown beside the graded paper, under the app's own header (the total score and the buttons Open Homework / Open Solution), so do not repeat those buttons.

1. The title ends with the homework number: `<COURSE> Homework <N> Grades`.
2. **One card per problem**: `<section class="card" id="p1">`, `id="p2"`, ... with the number exactly as in the grade report. A click on a card shows that page of the graded paper and marks the place.
3. **The scoreboard tiles and the table-of-contents links** point to the cards: `href="#p1"`, `href="#p2"`, ...
4. **Each grader comment** is one element with class `gc` that contains a numbered badge: `<div class="gc"><span class="badge">3</span> ...</div>`. The number is the number of that comment in the grade report (the Gradescope report), counted in the report's own order. A click on the comment shows its place on the graded paper. Keep problem numbers and comment numbers the same as the report's; do not renumber.
5. Links to my notes and sibling pages (see **Links**).

## Exam Grade Explanation

**File name:** `<FILE>.html`, which must contain the word **Grades** (for example `<COURSE> Midterm 1 Grades.html` or `<COURSE> Final Exam Grades.html`). Exams have no helper page.

The same format as the Homework Grade Explanation. The exam name in the title (Midterm 1, Final Exam) pairs the page with the graded exam of the same course.

1. **One card per problem**: `<section class="card" id="p1">`, `id="p2"`, ... with the number exactly as in the grade report. A click on a card shows that page of the graded paper and marks the place.
2. **The scoreboard tiles and the table-of-contents links** point to the cards: `href="#p1"`, `href="#p2"`, ...
3. **Each grader comment** is one element with class `gc` that contains a numbered badge: `<div class="gc"><span class="badge">3</span> ...</div>`, where the number is the number of that comment in the grade report, in the report's own order. Do not renumber.
4. Links to my notes and sibling pages (see **Links**).

## Exam Reflection

**File name:** `<FILE>.html` (for example `<COURSE> Midterm 1 Reflection.html`). My app files it as an Exam Reflection of that exam. It opens on its own, so its links (see **Links**) must work from this page. There are no cards with problem ids.

## Exam Preparation

**File name:** `<FILE>.html` (for example `<COURSE> Midterm 2 Preparation.html` or `<COURSE> Final Exam Preparation.html`). My app files it as an Exam Preparation of that exam. It opens on its own, so its links (see **Links**) must work from this page.

## Links

My app turns a link into an action by reading its **visible text** and, for notes, the `#id` at the end of its address. {{LINK_ADDRESS}} Keep the visible text in these forms:

1. **A section of my notes**: the address of the notes page followed by the section id, for example `{{LINK_EXAMPLE}}`, with the visible text `Lec N §x.y · Title` (for example `Lec 3 §2.2 · Eigenpairs`). The app reads the lecture number from the text and the section from the `#id`, and opens the course's notes of that lecture number at that id. A link to a worked example uses the example's id (`#ex-3`) and the text `(Lec N)`. A link to a chapter without a section id uses `Ch2 · Title` and opens that chapter's notes at the top. A link with no lecture number takes the lecture number of another link to the same address on the page.
2. **Other pages of the same course**, with exactly this visible text (the number is the page's own number): `Midterm 2 Preparation`, `Final Exam Preparation`, `Midterm 1 Reflection`, `Midterm 1 Grades`, `Final Exam Grades`, `Homework 4 Helper`, `Homework 4 Solution`. A Grades link opens the graded paper with its explanation beside it, a Helper link opens the problem file with its helper, a Solution link opens the posted solution.
3. Links to places inside the same page are plain `#anchors`.
