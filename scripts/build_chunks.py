"""Turn the raw FastAPI docs into heading-aware chunks (data/chunks.jsonl).

Each chunk belongs to exactly one section: the nearest level-2/3 heading that
carries an explicit `{ #anchor }`. Level-4+ headings fold into their parent.
Fenced code blocks are never split.
"""

import argparse
import html
import json
import re
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "chunks.jsonl"
SITE = "https://fastapi.tiangolo.com/"

# Pages that are community/meta content or build artefacts, not documentation.
EXCLUDED_PAGES = {
    "contributing.md",
    "external-links.md",
    "fastapi-people.md",
    "management.md",
    "management-tasks.md",
    "newsletter.md",
    "translations.md",
    "help-fastapi.md",
    "release-notes.md",
    "_llm-test.md",
    "translation-banner.md",
}
EXCLUDED_PREFIXES = ("reference/",)

MIN_SECTION_TOKENS = 60  # smaller sections merge into the next one
TARGET_MAX = 500  # chunk budget
TAIL_MIN = 100  # a smaller trailing chunk is folded into the previous one
CODE_LINES = 60  # max lines inlined in --code resolve mode

FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ANCHOR = re.compile(r"\s*\{\s*#([\w.-]+)\s*\}\s*$")
INCLUDE_NEW = re.compile(r"^\s*\{\*\s*(\S+)(.*?)\*\}\s*$")
INCLUDE_OLD = re.compile(r"^\s*\{!>?\s*(\S+?)\s*!\}\s*$")
ADMON_OPEN = re.compile(r"^\s*/{3,}\s*([\w-]+)(?:\s*\|\s*(.*?))?\s*$")
ADMON_CLOSE = re.compile(r"^\s*/{3,}\s*$")
CODE_SPAN = re.compile(r"(`[^`]*`)")
ABBR = re.compile(r"<(abbr|dfn)\s+title=\"([^\"]*)\"[^>]*>(.*?)</\1>", re.DOTALL)
HTML_TAG = re.compile(
    r"</?(?:font|span|b|u|i|em|strong|code|div|img|a|abbr|dfn|br|p|sup|sub|small|kbd|mark)"
    r"(?:\s[^>]*)?/?>",
    re.IGNORECASE,
)
FENCE_NOISE = re.compile(r"</?(?:font|span|b|u|strong)(?:\s[^>]*)?>", re.IGNORECASE)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
LINE_RANGES = re.compile(r"\bln\[([\d:,\s]+)\]")
LANG_BY_SUFFIX = {".py": "python", ".js": "javascript", ".html": "html", ".css": "css"}


def count_tokens(text: str) -> int:
    """Cheap token estimate: words * 1.3."""
    return round(len(text.split()) * 1.3)


def clean_inline(text: str) -> str:
    """Strip HTML, images and link targets from prose, leaving inline code alone."""
    parts = CODE_SPAN.split(text)
    for i in range(0, len(parts), 2):
        p = ABBR.sub(lambda m: f"{m[3]} ({m[2]})", parts[i])
        p = HTML_TAG.sub("", p)
        p = IMAGE.sub("", p)
        p = LINK.sub(r"\1", p)
        parts[i] = html.unescape(p)
    return "".join(parts)


def pick_lines(lines: list[str], opts: str) -> list[str]:
    """Apply an include's `ln[a:b,c:d]` ranges (1-based, inclusive); no ranges keeps all."""
    m = LINE_RANGES.search(opts)
    if not m:
        return lines
    picked: list[str] = []
    for part in m[1].split(","):
        a, _, b = part.strip().partition(":")
        if not a:
            continue
        start, end = int(a), int(b or a)
        if picked:
            picked.append("# ...")
        picked += lines[start - 1 : end]
    return picked


def read_include(
    rel: str, mode: str, raw: Path, opts: str = "", fenced: bool = True
) -> str | None:
    """Return the replacement text for a code include, or None if it is unusable.

    The include path points at the repo-level docs_src/; anything before
    `docs_src/` is dropped and the result must stay inside `raw`. Inside an
    existing fence (`fenced=False`) the code comes back without its own fence.
    """
    _, sep, tail = rel.partition("docs_src/")
    if not sep:
        return None
    src = tail.strip()
    if mode == "placeholder":
        return f"[code example: docs_src/{src}]"
    path = (raw / "docs_src" / src).resolve()
    if not path.is_relative_to(raw.resolve()) or not path.is_file():
        return f"[code example: docs_src/{src}]"
    lines = pick_lines(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), opts
    )
    body = "\n".join(lines[:CODE_LINES])
    if len(lines) > CODE_LINES:
        body += "\n# ..."
    if not fenced:
        return body
    lang = LANG_BY_SUFFIX.get(path.suffix, "")
    return f"```{lang}\n{body}\n```"


class Section:
    """A run of lines under one anchored heading."""

    def __init__(self, anchor: str, heading: str):
        self.anchor = anchor
        self.heading = heading
        self.lines: list[str] = []


def parse_page(
    md: str, code_mode: str = "placeholder", raw: Path = RAW
) -> tuple[str, list[Section]]:
    """Parse markdown into (page title, sections) with all syntax noise cleaned."""
    title = ""
    sections = [Section("top", "")]
    fence_marker: str | None = None
    drop_fence = False
    admonitions = 0
    label: str | None = None  # admonition label not yet written

    def out(line: str) -> None:
        nonlocal label
        if label is not None and line.strip():
            if line.lstrip().startswith(("```", "~~~", "[code example")):
                sections[-1].lines.append(f"{label}:")
                sections[-1].lines.append(line)
            else:
                sections[-1].lines.append(f"{label}: {line.lstrip()}")
            label = None
        else:
            sections[-1].lines.append(line)

    for raw_line in md.splitlines():
        line = raw_line.rstrip()

        if fence_marker:  # inside a fenced block
            if line.strip().startswith(fence_marker):
                fence_marker = None
                if not drop_fence:
                    out(line)
                drop_fence = False
            elif not drop_fence:
                inc = INCLUDE_OLD.match(line)
                replacement = inc and read_include(inc[1], code_mode, raw, fenced=False)
                out(replacement or FENCE_NOISE.sub("", line))
            continue
        if m := FENCE.match(line):
            fence_marker = m[1]
            drop_fence = m[2].lower() == "mermaid"  # diagrams mean nothing in speech
            if not drop_fence:
                out(line)
            continue

        if ADMON_CLOSE.match(line):
            admonitions = max(0, admonitions - 1)
            label = None
            out("")
            continue
        if m := ADMON_OPEN.match(line):
            admonitions += 1
            kind, custom = m[1], m[2]
            label = (
                clean_inline(custom).replace("*", "").strip()
                if custom
                else kind.capitalize()
            )
            if kind == "tab" and (not custom or custom.startswith("Python")):
                label = None  # python-version tabs only repeat the same code
            continue

        if m := INCLUDE_NEW.match(line) or INCLUDE_OLD.match(line):
            opts = m[2] if m.re is INCLUDE_NEW else ""
            replacement = read_include(m[1], code_mode, raw, opts)
            if replacement:
                out("")
                for part in replacement.split("\n"):
                    out(part)
                out("")
            continue

        if m := HEADING.match(line):
            level, text = len(m[1]), m[2]
            a = ANCHOR.search(text)
            text = clean_inline(ANCHOR.sub("", text)).strip()
            if level == 1 and not title:
                title = text
                sections[0] = Section(a[1] if a else "top", text)
                continue
            if level in (2, 3) and a:
                sections.append(Section(a[1], text))
                continue
            out(text)  # level 4+ (or unanchored): fold into the parent as plain text
            continue

        out(clean_inline(line))
    return title, [s for s in sections if s.lines or s.heading]


def split_blocks(lines: list[str]) -> list[str]:
    """Group lines into paragraphs; a fenced block is always one block."""
    blocks: list[str] = []
    cur: list[str] = []
    fence: str | None = None

    def flush() -> None:
        if any(x.strip() for x in cur):
            blocks.append("\n".join(cur).strip("\n"))
        cur.clear()

    for line in lines:
        if fence:
            cur.append(line)
            if line.strip().startswith(fence):
                fence = None
                flush()
        elif m := FENCE.match(line):
            flush()
            fence = m[1]
            cur.append(line)
        elif not line.strip():
            flush()
        else:
            cur.append(line)
    flush()
    return blocks


def shrink_block(block: str) -> list[str]:
    """Split an oversized non-code block on line boundaries."""
    if FENCE.match(block.split("\n", 1)[0]) or count_tokens(block) <= TARGET_MAX:
        return [block]
    pieces, cur = [], []
    for line in block.split("\n"):
        if cur and count_tokens("\n".join([*cur, line])) > TARGET_MAX:
            pieces.append("\n".join(cur))
            cur = []
        cur.append(line)
    pieces.append("\n".join(cur))
    return pieces


def pack(blocks: list[str], header_tokens: int = 0) -> list[list[str]]:
    """Greedily pack blocks into groups of at most TARGET_MAX tokens."""
    groups: list[list[str]] = []
    cur: list[str] = []
    cur_t = header_tokens
    for block in (p for b in blocks for p in shrink_block(b)):
        bt = count_tokens(block)
        if cur and cur_t + bt > TARGET_MAX:
            groups.append(cur)
            cur, cur_t = [], header_tokens
        cur.append(block)
        cur_t += bt
    if cur:
        groups.append(cur)
    if len(groups) > 1:  # fold a stub tail into the previous chunk
        tail_t = sum(map(count_tokens, groups[-1]))
        prev_t = sum(map(count_tokens, groups[-2]))
        if tail_t < TAIL_MIN and prev_t + tail_t <= TARGET_MAX * 1.2:
            groups[-2].extend(groups.pop())
    return groups


def page_url(page: str, lang: str, anchor: str) -> str:
    """Public docs URL for a page path like 'tutorial/body.md'."""
    path = page.removesuffix(".md")
    path = "" if path == "index" else path.removesuffix("/index") + "/"
    return f"{SITE}{'es/' if lang == 'es' else ''}{path}#{anchor}"


def with_carry(
    carry: tuple[str, str, list[str]] | None, sec: Section
) -> tuple[str, str, list[str]]:
    """Section as (anchor, heading, blocks), prefixed by a carried tiny section."""
    blocks = split_blocks(sec.lines)
    if not carry:
        return sec.anchor, sec.heading, blocks
    anchor, heading, cblocks = carry
    return anchor, heading, [*cblocks, *([sec.heading] if sec.heading else []), *blocks]


def merge_flags(sections: list[Section]) -> list[bool]:
    """True for each section that is too small and carries into the next one."""
    flags, carry = [], None
    for sec in sections:
        entry = with_carry(carry, sec)
        small = sum(map(count_tokens, entry[2])) < MIN_SECTION_TOKENS
        carries = small and sec is not sections[-1]
        flags.append(carries)
        carry = entry if carries else None
    return flags


def chunk_page(
    md: str, page: str, lang: str, code_mode: str = "placeholder", raw: Path = RAW
) -> list[dict]:
    """Chunk one markdown page into records ready for chunks.jsonl."""
    title, sections = parse_page(md, code_mode, raw)
    title = title or Path(page).stem
    # Merge decisions always use placeholder sizes, so inlining code never changes
    # which section_ids exist (the frozen gold set refers to them).
    _, shape = parse_page(md, "placeholder", raw)
    assert len(shape) == len(sections), page
    carried = merge_flags(shape)

    # Merge tiny sections into the next one; the merged chunk keeps the first section_id.
    merged: list[tuple[str, str, list[str]]] = []  # (anchor, heading, blocks)
    carry: tuple[str, str, list[str]] | None = None
    for sec, carries in zip(sections, carried, strict=True):
        entry = with_carry(carry, sec)
        carry = entry if carries else None
        if not carries:
            merged.append(entry)

    records = []
    for anchor, heading, blocks in merged:
        if not blocks:
            continue
        head = title if heading in ("", title) else f"{title} > {heading}"
        for n, group in enumerate(pack(blocks, count_tokens(head))):
            text = head + "\n\n" + "\n\n".join(group)
            records.append(
                {
                    "chunk_id": f"{lang}:{page}#{anchor}:{n}",
                    "section_id": f"{page}#{anchor}",
                    "page": page,
                    "lang": lang,
                    "title": title,
                    "heading": heading or title,
                    "url": page_url(page, lang, anchor),
                    "text": text,
                    "n_tokens": count_tokens(text),
                }
            )
    return records


def select_pages(raw: Path) -> list[str]:
    """English pages to index: documentation pages that also exist in Spanish."""
    en, es = raw / "docs/en/docs", raw / "docs/es/docs"
    pages = []
    for p in sorted(en.rglob("*.md")):
        rel = p.relative_to(en).as_posix()
        if rel in EXCLUDED_PAGES or rel.startswith(EXCLUDED_PREFIXES):
            continue
        if (es / rel).is_file():
            pages.append(rel)
    return pages


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code", choices=["placeholder", "resolve"], default="placeholder")
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    pages = select_pages(args.raw)
    records: list[dict] = []
    for lang in ("en", "es"):
        for page in pages:
            md = (args.raw / f"docs/{lang}/docs/{page}").read_text(encoding="utf-8")
            records += chunk_page(md, page, lang, args.code, args.raw)

    ids = [r["chunk_id"] for r in records]
    assert len(ids) == len(set(ids)), "duplicate chunk_ids"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    sections = {
        lang: {r["section_id"] for r in records if r["lang"] == lang}
        for lang in ("en", "es")
    }
    print(f"mode={args.code}  pages (per language): {len(pages)}")
    for lang in ("en", "es"):
        toks = [r["n_tokens"] for r in records if r["lang"] == lang]
        print(
            f"{lang}: {len(toks)} chunks, {len(sections[lang])} sections, "
            f"median {statistics.median(toks):.0f} tokens, max {max(toks)}"
        )
    both = sections["en"] & sections["es"]
    print(
        f"section_ids in both languages: {len(both)}; "
        f"only en: {len(sections['en'] - both)}; only es: {len(sections['es'] - both)}"
    )
    buckets = Counter(min(r["n_tokens"] // 100, 8) for r in records)
    print("token histogram (per 100):", dict(sorted(buckets.items())))
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
