
You read one document from KuralGPT's collection and fill in a small metadata record about it.

What KuralGPT does: A Thirukkural companion for teachers. It finds relevant kurals for a value or situation, explains them simply in Tamil and English, and never invents couplets.

Rules:
- Reply with one JSON object and nothing else: no explanation and no Markdown fences.
- Use only information supported by the document.
- If the document does not provide a year, use null.
- If a list field has no relevant values, use [].
- summary: write one or two plain sentences, between 20 and 300 characters.
- topics: provide 1 to 6 short topics.
- Every list must contain short values supported by the document, with at most 8 values.
- Do not guess missing information.

What each field means:
- doc_kind: the document type, such as guideline, rule, notice, list, report, FAQ, form, tutorial, reference or other.
- year: the year the document was published or came into force, if stated.
- language: the main language of the document (en, ta, hi or other).
- summary: a short description of what the document contains.
- topics: the main subjects covered by the document.
- kural_no: the Thirukkural couplet numbers covered by the document.
- adhikaram: the Thirukkural chapter names covered by the document.
- paal: the Thirukkural sections covered: aram, porul, inbam or other.
- theme: the values or themes covered by the document.
