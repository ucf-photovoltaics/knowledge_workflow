"""Shared beginner guidance; descriptions never imply unrecorded results."""
from shiny import ui

STEPS = {
    "ingest": ("Research library", "Select distinct papers under the saved inclusion rules", "Literature corpus", "Which papers informed this result?", "Inspect included papers and exclusions; citation ranking is a selection rule, not a quality judgment."),
    "parse": ("Source papers", "Read text, sections and figures", "Parsed source material", "Was the relevant material read?", "Check coverage gaps before interpreting an absent finding. Unread material and no extracted claim are different outcomes."),
    "extract": ("Parsed passages", "Extract concepts, statements and measurements", "Claims with source references", "What does the literature report?", "Select a statement to inspect its quote, conditions and source paper. A text match does not verify the scientific claim."),
    "normalize": ("Original paper terms", "Consolidate terminology and retain lineage", "Shared names and original-to-shared links", "Were terms merged without losing meaning?", "Canonical means the shared name used in this run. Compare original contexts before accepting a merge."),
    "ontology": ("Shared concepts", "Place concepts under ontology categories", "Classes and parent assignments", "Why is this concept in this category?", "Read the definition, parent path and recorded placement rationale together."),
    "enrich": ("Placed concepts", "Add definitions and formal connections", "Attributed definitions and restrictions", "What meaning was added, and from where?", "Compare imported and generated definitions. Restrictions describe modeled constraints, not necessarily observed findings."),
    "interop": ("Local ontology", "Compare external vocabularies", "Mappings and reusable exports", "Can these terms be reused elsewhere?", "Read both definitions and the mapping type. Similar labels do not establish equivalence."),
    "integrate": ("Domain ontologies", "Record mappings and bridge concepts", "Integrated ontology with source links", "What connects the domains?", "Inspect both concepts and their domain evidence. A mapping or bridge is not automatically causal."),
    "reports": ("Saved results and assessments", "Summarize findings and limitations", "Reports, figures and reusable outputs", "What can I conclude and reuse?", "Read figure units and denominators alongside corpus coverage and quality findings. More concepts do not imply better results."),
}


def stage(stage):
    source, process, result, question, useful = STEPS[stage]
    return ui.div(ui.strong(question), ui.div(ui.span(source), ui.span("→ " + process + " →"), ui.span(result), class_="process-strip"),
                  ui.p(useful), ui.tags.a("Researcher's guide & glossary", href="research-guide.html#" + stage, target="_blank"), class_="page-guide")


def routes():
    return ui.div(*(ui.tags.button(ui.strong(title), ui.span(description), type="button", class_="research-route",
                     **{"data-page": page, "data-exploration-tab": tab}) for title, description, page, tab in (
        ("Explore a concept", "Search a topic and inspect its recorded relationships", "explore", "WebVOWL"),
        ("Read supporting evidence", "Follow statements back to passages and papers", "provenance", ""),
        ("Review quality", "See recorded checks, gaps and withheld records", "explore", "Quality review"))), class_="research-routes")
