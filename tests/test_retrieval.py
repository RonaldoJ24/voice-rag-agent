"""Unit tests for the chunker, BM25 and section dedupe. No model download needed."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from voice_rag_agent.retrieval.local import BM25, LocalHybridRetriever, rrf, tokenize

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_chunks.py"
_spec = importlib.util.spec_from_file_location("build_chunks", _SCRIPT)
bc = importlib.util.module_from_spec(_spec)
sys.modules["build_chunks"] = bc
_spec.loader.exec_module(bc)


def words(n: int, tag: str = "w") -> str:
    return " ".join(f"{tag}{i}" for i in range(n))


# ---- chunker ---------------------------------------------------------------


def test_anchors_and_sections():
    md = (
        "# Page Title { #page-title }\n\n"
        f"Intro text. {words(70)}\n\n"
        "## First { #first }\n\n"
        f"First body. {words(70)}\n\n"
        "### Nested { #nested }\n\n"
        f"Nested body. {words(70)}\n\n"
        "#### Deep { #deep }\n\n"
        f"Deep body stays with its parent. {words(10)}\n"
    )
    recs = bc.chunk_page(md, "tutorial/x.md", "en")
    ids = [r["section_id"] for r in recs]
    assert ids == [
        "tutorial/x.md#page-title",
        "tutorial/x.md#first",
        "tutorial/x.md#nested",
    ]
    assert all("{ #" not in r["text"] for r in recs)
    nested = recs[-1]
    assert "Deep body stays with its parent" in nested["text"]
    assert nested["text"].startswith("Page Title > Nested\n")
    assert nested["url"] == "https://fastapi.tiangolo.com/tutorial/x/#nested"
    assert bc.chunk_page(md, "tutorial/x.md", "es")[0]["url"].startswith(
        "https://fastapi.tiangolo.com/es/tutorial/x/"
    )


def test_index_page_urls():
    assert bc.page_url("index.md", "en", "a") == "https://fastapi.tiangolo.com/#a"
    assert (
        bc.page_url("tutorial/index.md", "es", "a")
        == "https://fastapi.tiangolo.com/es/tutorial/#a"
    )


def test_admonitions_and_html():
    md = (
        "# T { #t }\n\n"
        "/// tip\n\nUse **FastAPI**.\n\n///\n\n"
        "/// note | Nota\n\nTexto aquí.\n\n///\n\n"
        'The <abbr title="Large Language Model">LLM</abbr> is <font color="red">red</font> and `<div>` stays.\n'
        f"{words(60)}\n"
    )
    text = bc.chunk_page(md, "p.md", "en")[0]["text"]
    assert "Tip: Use **FastAPI**." in text
    assert "Nota: Texto aquí." in text
    assert "///" not in text
    assert "LLM (Large Language Model) is red and `<div>` stays." in text


def test_code_placeholder_and_resolve(tmp_path):
    src = tmp_path / "docs_src" / "demo"
    src.mkdir(parents=True)
    (src / "app.py").write_text("\n".join(f"x{i} = {i}" for i in range(100)))
    md = f"# T {{ #t }}\n\n{{* ../../docs_src/demo/app.py hl[1,2] *}}\n\n{words(70)}\n"

    placeholder = bc.chunk_page(md, "p.md", "en", "placeholder", tmp_path)[0]["text"]
    assert "[code example: docs_src/demo/app.py]" in placeholder
    assert "x0 = 0" not in placeholder

    resolved = bc.chunk_page(md, "p.md", "en", "resolve", tmp_path)[0]["text"]
    assert "```python\nx0 = 0" in resolved
    assert "x59 = 59" in resolved and "x60 = 60" not in resolved

    assert bc.read_include("../../../../etc/passwd", "resolve", tmp_path) is None
    outside = tmp_path.parent / "secret.py"
    outside.write_text("SECRET = 1")
    leaked = bc.read_include("docs_src/../../secret.py", "resolve", tmp_path)
    assert leaked is None or "SECRET" not in leaked


def test_never_splits_a_fence():
    code = "\n".join(f"line_{i} = {i}" for i in range(200))
    paras = "\n\n".join(f"Paragraph {i}. {words(80, f'p{i}_')}" for i in range(8))
    md = f"# T {{ #t }}\n\n{paras}\n\n```python\n# not a heading\n{code}\n\n{code}\n```\n\n{paras}\n"
    recs = bc.chunk_page(md, "p.md", "en")
    assert len(recs) > 2
    for r in recs:
        assert r["text"].count("```") % 2 == 0, r["chunk_id"]
    fenced = [r for r in recs if "```python" in r["text"]]
    assert len(fenced) == 1
    assert (
        fenced[0]["text"].count("line_199 = 199") == 2
    )  # the whole fence is in one chunk
    assert all(
        r["section_id"] == "p.md#t" for r in recs
    )  # "# not a heading" did not open a section
    assert [r["chunk_id"].rsplit(":", 1)[1] for r in recs] == [
        str(i) for i in range(len(recs))
    ]


def test_tiny_section_merges_into_next_and_keeps_first_id():
    md = f"# T {{ #t }}\n\nShort intro.\n\n## Big {{ #big }}\n\n{words(120)}\n"
    recs = bc.chunk_page(md, "p.md", "en")
    assert len(recs) == 1
    assert recs[0]["section_id"] == "p.md#t"
    assert "Short intro." in recs[0]["text"] and "w119" in recs[0]["text"]


# ---- BM25 -------------------------------------------------------------------


def test_tokenize_keeps_identifiers_and_strips_accents():
    assert tokenize("Use OAuth2PasswordBearer con Depends") == [
        "use",
        "oauth2passwordbearer",
        "depends",
    ]
    assert tokenize("¿Cómo inyección?") == ["inyeccion"]


def test_bm25_ranks_exact_identifier_first():
    docs = [
        "Security with tokens and passwords for every request",
        "Use OAuth2PasswordBearer to read the token from the Authorization header",
        "Request bodies are validated with Pydantic models",
    ]
    bm = BM25.build([tokenize(d) for d in docs])
    scores = bm.scores(tokenize("OAuth2PasswordBearer"))
    assert int(np.argmax(scores)) == 1
    assert scores[0] == scores[2] == 0
    again = BM25.from_json(bm.to_json())
    assert np.allclose(
        again.scores(tokenize("pydantic models")),
        bm.scores(tokenize("pydantic models")),
    )


def test_rrf_rewards_agreement():
    fused = rrf([[3, 1, 2], [1, 3]])
    assert fused[1] > fused[2] and fused[3] > fused[2]


# ---- retriever with a fake index --------------------------------------------


def chunk(section, lang, text, n=0):
    page, anchor = section.split("#")
    return {
        "chunk_id": f"{lang}:{section}:{n}",
        "section_id": section,
        "page": page,
        "lang": lang,
        "title": "T",
        "heading": anchor,
        "url": f"https://x/{lang}/{section}",
        "text": text,
        "n_tokens": 10,
    }


@pytest.fixture
def fake():
    chunks = [
        chunk("a.md#one", "en", "dependency injection with Depends"),
        chunk("a.md#one", "es", "inyeccion de dependencias con Depends"),
        chunk("b.md#two", "en", "background tasks run after the response"),
        chunk("b.md#two", "es", "tareas en segundo plano despues del response"),
        chunk("c.md#three", "en", "only english section about Depends"),
    ]
    vecs = np.array(
        [[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0], [0, 0.9, 0.1], [0.8, 0, 0.2]],
        dtype=np.float32,
    )
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    bm25 = BM25.build([tokenize(c["text"]) for c in chunks])

    def embed(query: str) -> np.ndarray:
        return (
            np.array([1.0, 0, 0], dtype=np.float32)
            if "depend" in query.lower()
            else np.array([0, 1.0, 0], dtype=np.float32)
        )

    return LocalHybridRetriever(chunks, vecs, bm25, embed)


def test_one_hit_per_section(fake):
    hits = fake.search("Depends", k=10)
    ids = [h.section_id for h in hits]
    assert len(ids) == len(set(ids))
    assert ids[0] == "a.md#one"
    assert fake.name == "local-hybrid"


def test_lang_preference_picks_chunk_in_that_language(fake):
    assert {
        h.lang
        for h in fake.search("Depends", lang="es", k=5)
        if h.section_id != "c.md#three"
    } == {"es"}
    assert fake.search("Depends", lang="en", k=1)[0].lang == "en"
    # scores are the section's best score regardless of which chunk is shown
    en, es = fake.search("Depends", lang="en")[0], fake.search("Depends", lang="es")[0]
    assert en.section_id == es.section_id and en.score == es.score


def test_lang_without_translation_falls_back(fake):
    hits = fake.search("only english Depends", lang="es", k=5)
    assert any(h.section_id == "c.md#three" and h.lang == "en" for h in hits)
