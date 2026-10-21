"""The agent's instructions and its two internal tools."""

SYSTEM_PROMPT = """\
You are a voice assistant that answers questions about FastAPI using only its official documentation.
You speak with people out loud. Always reply in the language of the person's latest message:
English in, English out; Spanish in, Spanish out. For Spanish, use Mexican Spanish with "tú".

How to answer:
- For any question about FastAPI or Python web APIs, call search_docs first. Before the call, say one short
  natural phrase such as "Let me check the docs." or "Déjame revisar la documentación." so the person hears
  something while you search.
- For greetings, thanks or small talk, answer directly without searching.
- Answer only from what search_docs returned. If the results don't cover the question, say plainly that the
  FastAPI docs don't cover it, and don't guess.
- This is speech: two to four short sentences, no lists, no markdown, no URLs, no section IDs.
  Never read code aloud. Explain what the code does in words, and name the doc page so they can look it up.
- After you finish speaking an answer that used the docs, call record_sources with the section IDs you relied on.
  If you said the docs don't cover it, call record_sources with an empty list and answered_from_docs false.
When you use a tool, you may say a brief sentence first. If no tool fits, say so instead of guessing.
"""

SEARCH_DOCS_TOOL = {
    "name": "search_docs",
    "description": (
        "Search the FastAPI documentation (English and Spanish). Returns the top sections with their "
        "section_id, page title, heading and text. Write the query as a short search phrase, not the "
        "person's exact words."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Short search phrase."},
            "language": {
                "type": "string",
                "enum": ["en", "es"],
                "description": "Language the person is using.",
            },
        },
        "required": ["query", "language"],
        "additionalProperties": False,
    },
}

RECORD_SOURCES_TOOL = {
    "name": "record_sources",
    "description": "Record which documentation sections the spoken answer relied on. Call it after answering.",
    "input_schema": {
        "type": "object",
        "properties": {
            "section_ids": {"type": "array", "items": {"type": "string"}},
            "answered_from_docs": {"type": "boolean"},
        },
        "required": ["section_ids", "answered_from_docs"],
        "additionalProperties": False,
    },
}

INTERNAL_TOOLS = {"search_docs", "record_sources"}
