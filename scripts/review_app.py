# /// script
# requires-python = ">=3.10"
# dependencies = ["shiny>=1.0", "openpyxl"]
# ///
"""Card view of an expert review workbook: one item at a time, answers saved straight into the workbook.

Put this file next to your reviewer-<name>.xlsx (close the workbook in Excel) and run:
    uv run review_app.py [path/to/reviewer-<name>.xlsx]
Keys: 1-6 pick an answer, left/right arrows move between cards. On a touch screen, swipe left or right.
"""
import sys
from pathlib import Path

from openpyxl import load_workbook
from shiny import App, reactive, render, run_app, ui

HERE = Path(__file__).resolve().parent
BOOK = Path(sys.argv[1]) if len(sys.argv) > 1 else next(iter(sorted(HERE.glob("reviewer-*.xlsx"))), None)
HIDE = {"Item", "Answer", "Notes", "Better parent"}


def load(book):
    """Cards from every review sheet; answers come from the sheet's drop-down, hints from the Start here sheet."""
    wb = load_workbook(book)
    hints, current = {}, None
    for a, _, _, d in wb["Start here"].iter_rows(max_col=4, values_only=True):
        if a and str(a).endswith(": answers"):
            current = str(a)[:-len(": answers")]
            hints[current] = {}
        elif a:
            current = None
        elif current and d and ":" in str(d):
            k, v = str(d).split(":", 1)
            hints[current][k.strip()] = v.strip()
    cards = []
    for ws in wb.worksheets[1:]:
        header = [c.value for c in ws[2]]
        cols = {h: i + 1 for i, h in enumerate(header)}
        answers = ws.data_validations.dataValidation[0].formula1.strip('"').split(",")
        for r in range(3, ws.max_row + 1):
            row = {h: ws.cell(r, cols[h]).value for h in header}
            cards.append({"sheet": ws.title, "row": r, "cols": cols, "question": ws.cell(1, 1).value,
                          "answers": answers, "hints": hints.get(ws.title, {}),
                          "fields": {h: row[h] for h in header if h not in HIDE and row[h]},
                          "answer": row.get("Answer") or "", "notes": row.get("Notes") or "",
                          "better": row.get("Better parent") or "", "has_better": "Better parent" in cols})
    return cards


CARDS = load(BOOK) if BOOK and BOOK.exists() else []
WHO = BOOK.stem.removeprefix("reviewer-").title() if BOOK else ""

CSS = """
body { background: #f4f5f7; }
.card { background: #fff; border-radius: 14px; padding: 22px 26px; box-shadow: 0 2px 10px rgba(0,0,0,.08); margin-top: 12px; }
.check { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
.question { font-size: 1.15rem; font-weight: 600; margin: 4px 0 16px; }
.concept { border-left: 4px solid #2563eb; padding: 4px 0 4px 14px; margin: 10px 0; }
.concept.parent { border-color: #16a34a; }
.role { font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
.name { font-size: 1.35rem; font-weight: 700; }
.def { margin-top: 2px; } .def b { font-weight: 600; }
.judged { background: #fff7e0; border-radius: 8px; padding: 8px 12px; margin-top: 6px; font-size: 1.05rem; }
.link { font-weight: 700; font-size: 1.05rem; color: #374151; margin: 4px 0 4px 18px; }
.note { font-size: .82rem; color: #6b7280; }
.quotes h6 { margin: 16px 0 6px; color: #6b7280; font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
blockquote { border-left: 3px solid #cbd5e1; margin: 0 0 8px; padding: 2px 0 2px 12px; }
blockquote p { margin: 0; font-style: italic; } blockquote cite { font-size: .8rem; color: #6b7280; }
.found { font-size: .82rem; color: #6b7280; margin-top: 10px; white-space: pre-wrap; }
.answers { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 12px; }
.answers button { border: 1px solid #cbd5e1; background: #fff; border-radius: 10px; padding: 10px 14px; cursor: pointer; }
.answers button.on { background: #2563eb; color: #fff; border-color: #2563eb; }
.answers button small { opacity: .6; margin-right: 6px; }
.hint { font-size: .85rem; color: #6b7280; min-height: 1.2em; }
.nav { display: flex; justify-content: space-between; margin-top: 14px; }
.bar { height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }
.bar div { height: 100%; background: #16a34a; }
"""
JS = """
const send = (name, value) => Shiny.setInputValue(name, {value: value, at: Date.now()});
document.addEventListener('keydown', e => {
  if (['TEXTAREA', 'INPUT'].includes(e.target.tagName)) return;
  if (e.key >= '1' && e.key <= '9') send('pick', Number(e.key) - 1);
  if (e.key === 'ArrowRight') send('nav', 1);
  if (e.key === 'ArrowLeft') send('nav', -1);
});
let x0 = null;
document.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; });
document.addEventListener('touchend', e => {
  if (x0 === null) return;
  const dx = e.changedTouches[0].clientX - x0; x0 = null;
  if (Math.abs(dx) > 70) send('nav', dx < 0 ? 1 : -1);
});
"""

def concept(role, name, definition, judged=False, note="", kind=""):
    """A term in bold with its definition underneath; the definition being judged is highlighted."""
    text = definition or "No definition given."
    return ui.div(ui.div(role, class_="role"), ui.div(name, class_="name"),
                  ui.div(text, class_="judged" if judged else "def"),
                  ui.div(note, class_="note") if note else None, class_=f"concept {kind}")


def quotes(text):
    """'[Paper title] quote' lines as block quotes with the paper as the citation."""
    out = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("(no "):
            continue
        source, sep, body = line[1:].partition("] ") if line.startswith("[") else ("", "", line)
        if not sep:
            source, body = "", line
        out.append(ui.tags.blockquote(ui.p(f"“{body}”"), ui.tags.cite(source) if source else None))
    return ui.div(ui.tags.h6("From the papers"), *out, class_="quotes") if out else None


def body(f):
    """Term, definition and parent (or target) in bold, then the paper quotes and where the term was found."""
    if "Parent" in f:
        main = [concept("Term", f.get("Term"), f.get("Term definition")), ui.div("is a kind of ↓", class_="link"),
                concept("Parent", f.get("Parent"), f.get("Parent definition"), kind="parent",
                        note=f"from {f['Parent from']}" if f.get("Parent from") else "")]
    elif "Relation" in f:
        main = [concept("Term", f.get("Term"), f.get("Term definition")), ui.div(f"{f['Relation']} ↓", class_="link"),
                concept("Outside term" if f.get("Kind") == "Mapping" else "Target", f.get("Target"),
                        f.get("Target definition"), kind="parent")]
    else:
        main = [concept("Term", f.get("Term"), f.get("Definition"), judged=True)]
    found = ui.div(f"Found in: {f['Found in']}", class_="found") if f.get("Found in") else None
    return [*main, quotes(f.get("Paper excerpts") or f.get("Evidence")), found]


app_ui = ui.page_fixed(
    ui.tags.style(CSS), ui.tags.script(JS),
    ui.h3(f"KWEAVE expert review: {WHO}" if WHO else "KWEAVE expert review"),
    ui.output_ui("progress"),
    ui.output_ui("card"),
)


def server(input, output, session):
    first = next((n for n, c in enumerate(CARDS) if not c["answer"]), 0)
    at = reactive.value(first)
    saved = reactive.value(0)

    def text(name, default):
        try:
            return input[name]() or ""
        except Exception:
            return default

    def persist(card):
        card["notes"] = text("notes", card["notes"])
        if card["has_better"]:
            card["better"] = text("better", card["better"])
        try:
            wb = load_workbook(BOOK)
            ws = wb[card["sheet"]]
            ws.cell(card["row"], card["cols"]["Answer"]).value = card["answer"] or None
            ws.cell(card["row"], card["cols"]["Notes"]).value = card["notes"] or None
            if card["has_better"]:
                ws.cell(card["row"], card["cols"]["Better parent"]).value = card["better"] or None
            wb.save(BOOK)
        except PermissionError:
            ui.notification_show("Couldn't save: close the workbook in Excel, then answer again.", type="error",
                                 duration=8)
        saved.set(saved() + 1)

    def go(step):
        persist(CARDS[at()])
        at.set(min(max(at() + step, 0), len(CARDS) - 1))

    @reactive.effect
    @reactive.event(input.pick)
    def _pick():
        card, n = CARDS[at()], int(input.pick()["value"])
        if n < len(card["answers"]):
            card["answer"] = card["answers"][n]
            go(1)

    @reactive.effect
    @reactive.event(input.nav)
    def _nav():
        go(int(input.nav()["value"]))

    @reactive.effect
    @reactive.event(input.next_open)
    def _next_open():
        todo = [n for n, c in enumerate(CARDS) if not c["answer"]]
        if todo:
            persist(CARDS[at()])
            at.set(next((n for n in todo if n > at()), todo[0]))

    @render.ui
    def progress():
        saved()
        done = sum(bool(c["answer"]) for c in CARDS)
        note = (ui.p(f"All {len(CARDS)} answered. Thank you! Send {BOOK.name} back to Brent.")
                if CARDS and done == len(CARDS) else ui.p(f"{done} of {len(CARDS)} answered"))
        return ui.div(note, ui.div(ui.div(style=f"width:{100 * done / max(len(CARDS), 1):.0f}%"), class_="bar"))

    @render.ui
    def card():
        if not CARDS:
            return ui.div(ui.p("No reviewer workbook found. Put this file next to your reviewer-<name>.xlsx, or run "
                               "uv run review_app.py path/to/reviewer-<name>.xlsx"), class_="card")
        n = at()
        saved()
        c = CARDS[n]
        buttons = [ui.tags.button(ui.tags.small(str(k + 1)), a, class_="on" if a == c["answer"] else "",
                                  title=c["hints"].get(a, ""),
                                  onclick=f"Shiny.setInputValue('pick', {{value: {k}, at: Date.now()}})")
                   for k, a in enumerate(c["answers"])]
        extra = [ui.input_text("better", "Better parent (optional)", c["better"], width="100%")] if c["has_better"] else []
        return ui.div(
            ui.div(f"{c['sheet']} · card {n + 1} of {len(CARDS)}", class_="check"),
            ui.div(c["question"], class_="question"),
            *body(c["fields"]),
            ui.div(*buttons, class_="answers"),
            ui.div(c["hints"].get(c["answer"], "Hover an answer to see what it means."), class_="hint"),
            *extra,
            ui.input_text_area("notes", "Notes (optional)", c["notes"], width="100%", rows=2),
            ui.div(ui.tags.button("← Back", onclick="Shiny.setInputValue('nav', {value: -1, at: Date.now()})"),
                   ui.input_action_button("next_open", "Next unanswered"),
                   ui.tags.button("Next →", onclick="Shiny.setInputValue('nav', {value: 1, at: Date.now()})"),
                   class_="nav"),
            class_="card")


app = App(app_ui, server)

if __name__ == "__main__":
    run_app(app, launch_browser=True)
