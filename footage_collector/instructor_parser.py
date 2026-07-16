"""
instructor_parser.py
--------------------
Parses a beat-by-beat "visual instructor" file into scene specs with precise
clip + image search queries. NO LLM / API needed - the visual instructions
already contain the analysis; we just translate them into search queries.

Expected beat format (labels are matched loosely / case-insensitively):

    SECTION HEADER (optional, all-caps line)
    Script Cue (narration): "..."
    Visual / Exact Clip to Use: ...
    On-Screen Text: ...
    Editor Notes: ...

For every beat we extract:
  - the narration line
  - the visual description (the source of the queries)
  - the on-screen text + editor notes (saved for the editor, not searched)

Query building (heuristic, ordered most-specific first):
  1. ALL-CAPS scene names in the visual  -> "{subject} {scene name} scene"
  2. quoted famous lines                 -> "{subject} {line} scene"
  3. named entities (people/places)       -> anchored or standalone
  4. fallback: subject + salient nouns
Beats explicitly marked non-film (e.g. "NOT Scarface", "archival", "abstract")
are searched WITHOUT the film anchor so we get real-world / stock footage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# --- label patterns --------------------------------------------------------

_LABELS = {
    # Narration starts a new beat. Accept the canonical "Script Cue (narration):"
    # plus the common variants LLMs emit (Narration:, Voiceover:, VO:, Script:).
    "narration": re.compile(
        r"^\s*(?:Script Cue\s*(?:\(\s*narration\s*\))?|Narration(?:\s*Cue)?|"
        r"Voice\s?over|VO|Script)\s*:\s*(.*)$", re.I),
    "visual": re.compile(
        r"^\s*Visual(?:\s*/?\s*Exact Clip(?:\s*to Use)?|\s*Direction|\s*Cue)?\s*:\s*(.*)$", re.I),
    "clip_links": re.compile(r"^\s*(?:Clip Links?|Clips?|Video Links?|YouTube|YT Links?)\s*:\s*(.*)$", re.I),
    "image_links": re.compile(r"^\s*(?:Image Links?|Image URLs?|Img Links?|Picture Links?)\s*:\s*(.*)$", re.I),
    "spoken": re.compile(r"^\s*(?:Spoken Line|Spoken Lines|Dialogue|Exact Dialogue|Line)\s*:\s*(.*)$", re.I),
    "image_terms": re.compile(r"^\s*(?:Image Search|Image Terms?|Image Queries|Images?)\s*:\s*(.*)$", re.I),
    "onscreen": re.compile(r"^\s*On-?Screen Text\s*:\s*(.*)$", re.I),
    "notes": re.compile(r"^\s*Editor Notes\s*:\s*(.*)$", re.I),
}

# words that look like proper nouns only because they start a sentence
_INITIAL_NOISE = {
    "Quick", "Then", "Continue", "Hold", "Hard", "Show", "Brief", "Slow",
    "Final", "Optional", "Photo", "Archival", "Split", "Abstract", "End",
    "Or", "And", "The", "A", "An", "Let", "Establish", "Focus", "Build",
    "These", "This", "That", "Two", "Same", "Keep", "Pull", "Cut", "Close",
    "Documentary", "Stock", "Still", "Text", "Tony",  # Tony handled via subject anchor
    "His", "He", "She", "Her", "Him", "Its", "Their", "Your", "They", "We",
    "You", "When", "Where", "While", "After", "Before", "Most", "Here",
    "There", "Then", "Now", "But", "Not", "Brief", "Insert", "Continue",
}

# markers that mean "do NOT use the film as the source"
_NONFILM_MARKERS = (
    "not scarface", "non-film", "archival", "stock shot", "stock footage",
    "real-world", "documentary", "abstract", "universal", "newspaper",
    "rap album", "music video", "end card", "skyline", "establishing shot",
    "text card", "mpaa",
)


@dataclass
class Beat:
    index: int
    section: str
    narration: str
    visual: str
    on_screen: str = ""
    notes: str = ""
    is_film: bool = True
    clip_links: List[str] = field(default_factory=list)
    image_links: List[str] = field(default_factory=list)
    spoken_lines: List[str] = field(default_factory=list)
    image_terms: List[str] = field(default_factory=list)
    image_queries: List[str] = field(default_factory=list)
    clip_queries: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --- low-level parsing ------------------------------------------------------

def _split_links(raw: str) -> List[str]:
    """Pull YouTube URLs (optionally with timestamps) out of a Clip Links line."""
    if not raw:
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    out = []
    for p in parts:
        p = p.strip().strip("()<>[]")
        if "youtu" in p.lower() and p.lower().startswith("http"):
            out.append(p)
    return out


def _split_img_links(raw: str) -> List[str]:
    """Pull direct image URLs out of an Image Links line."""
    if not raw:
        return []
    parts = re.split(r"[\s,;|]+", raw.strip())
    out = []
    for p in parts:
        p = p.strip().strip("()<>[]")
        if p.lower().startswith("http"):
            out.append(p)
    return out


def _split_terms(raw: str) -> List[str]:
    """Split an Image Search line into individual search terms."""
    if not raw:
        return []
    # allow comma, semicolon, pipe, or ' / ' separators
    parts = re.split(r"\s*[|;,]\s*|\s+/\s+", raw.strip())
    return [p.strip() for p in parts if p.strip()]


_SPOKEN_PLACEHOLDER = re.compile(
    r"no dialogue|host on-?camera|original footage|b-?roll|voice ?over|"
    r"narration only|product (?:shot|flat|close|montage)|screen (?:capture|recording)|"
    r"graphic|flat-?lay|montage|photo comparison|side-?by-?side|product",
    re.I,
)


def _split_spoken(raw: str) -> List[str]:
    """Split Spoken Line(s) on | only (lines may contain commas). Drop common
    placeholders like '(no dialogue - B-roll)' / '(host on-camera)' that some
    LLMs write when there is no real on-screen dialogue."""
    if not raw:
        return []
    parts = re.split(r"\s*\|\s*", raw.strip())
    out = []
    for p in parts:
        p = p.strip().strip('"“”\u2018\u2019')
        if not p:
            continue
        if p.startswith("(") and p.endswith(")"):
            continue
        if _SPOKEN_PLACEHOLDER.search(p):
            continue
        out.append(p)
    return out


# Leading markdown noise: heading (#), blockquote (>), bullets (-, *, +, •),
# or an ordered-list marker ("1.", "2)"). LLMs love wrapping instructor files
# in markdown, which slides every label off the line-start the regexes anchor to.
_MD_LEAD = re.compile(r"^\s*(?:[#>]+\s*|[-*+•]\s+|\d+[.)]\s+)+")


def _clean_line(line: str) -> str:
    """Strip leading markdown markers + inline bold/italic emphasis so label
    matching works whether or not the file is markdown-formatted."""
    s = _MD_LEAD.sub("", line)
    s = s.replace("**", "").replace("__", "")
    return s


def _looks_like_section(line: str) -> bool:
    s = line.strip()
    if not s or any(p.match(line) for p in _LABELS.values()):
        return False
    if s[0].isdigit():  # e.g. "1.  Visual Direction (Beat-by-Beat)"
        return False
    if any(ch in s for ch in ".·:()\""):  # section headers are bare labels
        return False
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    return upper_ratio > 0.8 and len(s) < 48


def parse_beats(text: str) -> List[Beat]:
    lines = text.splitlines()
    beats: List[Beat] = []
    section = ""
    cur: Optional[dict] = None
    field_name: Optional[str] = None

    def _new(sec):
        return {"section": sec, "narration": "", "visual": "", "onscreen": "",
                "notes": "", "clip_links": "", "image_terms": "", "spoken": "",
                "image_links": ""}

    def flush():
        nonlocal cur
        if cur and (cur["narration"] or cur["visual"]):
            beats.append(Beat(
                index=len(beats) + 1,
                section=cur["section"],
                narration=cur["narration"].strip(),
                visual=cur["visual"].strip(),
                on_screen=cur["onscreen"].strip(),
                notes=cur["notes"].strip(),
                clip_links=_split_links(cur["clip_links"]),
                image_links=_split_img_links(cur["image_links"]),
                spoken_lines=_split_spoken(cur["spoken"]),
                image_terms=_split_terms(cur["image_terms"]),
            ))
        cur = None

    for raw_line in lines:
        # Normalise away markdown so labels match whether or not the file is
        # markdown-formatted (**bold**, "- ", "# ", "1. " prefixes, etc.).
        line = _clean_line(raw_line)
        matched_label = None
        for name, pat in _LABELS.items():
            m = pat.match(line)
            if m:
                matched_label = name
                inline = m.group(1)
                if name == "narration":
                    flush()  # a new narration line starts a new beat
                    cur = _new(section)
                if cur is None:
                    cur = _new(section)
                cur[name] += (" " + inline if cur[name] else inline)
                field_name = name
                break

        if matched_label:
            continue

        # A section header can appear between beats (while the previous beat is
        # still held in `cur`). Detect it first so it never pollutes a field.
        if _looks_like_section(line):
            section = line.strip()
            field_name = None
            continue

        if cur is None:
            continue

        if field_name and line.strip():
            cur[field_name] += " " + line.strip()

    flush()
    return beats


# --- query extraction -------------------------------------------------------

# Quotes: straight/curly DOUBLE quotes, and curly SINGLE pairs only.
# We deliberately exclude the straight apostrophe so "It's" / "Tony's" are safe,
# and curly ’ alone won't match (needs an opening ‘).
_DOUBLE_RE = re.compile(r"[\"“]([^\"”]{3,70}?)[\"”]")
_CURLY_SINGLE_RE = re.compile(r"‘([^’]{3,70}?)’")
_CAPS_RE = re.compile(r"\b([A-Z][A-Z0-9'\-]+(?:\s+[A-Z0-9'\-&]+){1,6})\b")
_PROPER_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")

_LEADING_ARTICLE = re.compile(r"^(THE|A|AN)\s+", re.I)


def _polish_query(s: str) -> str:
    """Trim a query: cut at ellipsis, drop colon/dash tails, cap length."""
    s = s.strip()
    # cut everything from the first ellipsis
    s = re.split(r"…|\.\.\.", s)[0]
    # drop a trailing 'scene' label temporarily to manage length
    had_scene = s.endswith(" scene")
    core = s[:-6] if had_scene else s
    # remove colon segments / stray punctuation
    core = core.split(":")[0]
    core = core.replace("—", " ").replace(">", " ").replace('"', " ")
    core = re.sub(r"\s+", " ", core).strip(" ,;-")
    # cap to 10 words to keep searches focused
    words = core.split()
    if len(words) > 10:
        core = " ".join(words[:10])
    if not core:
        return ""
    out = f"{core} scene" if had_scene else core
    # collapse duplicate words (case-insensitive), keep first occurrence. This
    # removes redundancy when the visual line repeats the subject/topic, e.g.
    # "The Thing 1982 Final Shot The Thing 1982" -> "The Thing 1982 Final Shot".
    seen, deduped = set(), []
    for w in out.split():
        k = w.lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(w)
    return " ".join(deduped)


_BAD_QUOTE_WORDS = {
    "rating", "mpaa", "excessive", "cumulative", "violence", "language",
    "overlay", "title", "card",
}


def _clean_quote(q: str) -> Optional[str]:
    q = q.strip().strip("….,;:!- ").strip()
    if ":" in q or any(c.isdigit() for c in q):
        return None
    words = q.split()
    if len(words) < 2 or len(words) > 6:          # real dialogue lines are short
        return None
    if any(w.lower().strip(".,!?") in _BAD_QUOTE_WORDS for w in words):
        return None                                # skip text-card / overlay strings
    return q.lower() if q.isupper() else q


def _quotes(text: str, allow_double: bool) -> List[str]:
    found = list(_CURLY_SINGLE_RE.findall(text))
    if allow_double:
        found += list(_DOUBLE_RE.findall(text))
    out = []
    for q in found:
        c = _clean_quote(q)
        if c:
            out.append(c)
    seen, res = set(), []
    for q in out:
        if q.lower() not in seen:
            seen.add(q.lower())
            res.append(q)
    return res


def _caps_scene_names(text: str) -> List[str]:
    # Remove parentheticals AND quoted spans first, so on-screen / text-card
    # content (e.g. "MPAA RATING: X ...") is never mistaken for a scene name.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[\"“][^\"”]*[\"”]", " ", text)
    text = re.sub(r"‘[^’]*’", " ", text)
    names = []
    for c in _CAPS_RE.findall(text):
        phrase = _LEADING_ARTICLE.sub("", c).strip()  # only strip a leading article
        words = phrase.split()
        if len(words) >= 2 and not phrase.isdigit():
            names.append(phrase.title())
    seen, res = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            res.append(n)
    return res


def _proper_nouns(text: str) -> List[str]:
    # strip parentheticals to reduce noise like "(Scarface)"
    text = re.sub(r"\([^)]*\)", " ", text)
    out = []
    for p in _PROPER_RE.findall(text):
        words = p.split()
        # drop if the whole phrase is just sentence-initial noise
        if all(w in _INITIAL_NOISE for w in words):
            continue
        # drop a single noise word
        if len(words) == 1 and words[0] in _INITIAL_NOISE:
            continue
        out.append(p)
    seen, res = set(), []
    for p in out:
        if p.lower() not in seen:
            seen.add(p.lower())
            res.append(p)
    return res


_CRAFT_STOP = {
    "montage", "shot", "shots", "clip", "clips", "scene", "scenes", "cut",
    "cuts", "dissolve", "cross", "hold", "holds", "establish", "establishing",
    "insert", "inserts", "intercut", "still", "stills", "footage", "camera",
    "frame", "frames", "slow", "fast", "quick", "brief", "push", "pull",
    "zoom", "pan", "reveal", "card", "text", "overlay", "flash", "real",
    "world", "then", "continue", "optional", "back", "wide", "close",
    "splash", "silence", "tone", "music", "energy", "beat", "beats",
    "version", "same", "document", "documentary", "stock", "archival",
    "photo", "image", "reference", "into", "onto", "with", "from", "that",
    "this", "their", "there", "here", "your", "have", "been", "were", "where",
    "which", "while", "after", "before", "about", "across", "over", "under",
    "him", "his", "her", "she", "they", "them", "tony", "scarface",  # subject
    "film", "movie", "late", "early", "previous", "next", "sharp", "visual",
    "contrast", "thesis", "audience", "viewer", "feeling", "something",
    "abstract", "universal", "respectful", "minimal", "factual", "build",
    "show", "focus", "establishing", "behind", "across", "between", "against",
    # common verbs / adverbs / adjectives that aren't visual subjects
    "hard", "down", "here", "again", "just", "simple", "split", "holding",
    "standing", "final", "reflective", "dissolves", "fires", "alive",
    "wanting", "channel", "recreation", "turns", "named", "company",
    "reportedly", "story", "listened", "wanted", "young", "delivering",
    "watching", "looking", "talk", "makes", "every", "people", "like",
}


def _descriptive_keywords(text: str, limit: int = 4) -> List[str]:
    """Salient content words from the Visual line (used only to add specificity;
    always combined with the subject anchor, so results stay on-topic)."""
    text = re.sub(r"\([^)]*\)", " ", text)
    # remove quoted spans entirely (text cards / on-screen / dialogue handled elsewhere)
    text = re.sub(r"[\"“][^\"”]*[\"”]", " ", text)
    text = re.sub(r"‘[^’]*’", " ", text)
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    out, seen = [], set()
    for w in words:
        if w in _CRAFT_STOP or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out[:limit]


# Greedy leading (.*) locks onto the LAST "about" in the line — Visual text
# often contains an earlier literal "about" ('...on the phone about the
# Albanian deal... — about Rugrats 1991 "Runaway Angelica".') and matching the
# first one used to turn half the sentence into the query anchor.
_ABOUT_RE = re.compile(
    r"^(.*)[\s,—–\-(]about\s+([^.]{3,80}?)[\s.\)\"”’]*$", re.I | re.S)


def _about_anchor(visual: str):
    """Split the Visual line's trailing '— about <Movie/Show + Year>' clause.

    The FORMAT_SPEC asks every Visual line to end with the beat's true topic
    anchor (e.g. '— about Breaking Bad "Box Cutter" 2011.'). Returns
    (anchor, visual_without_the_clause). The anchor (quotes stripped) replaces
    the global subject for this beat's queries, and removing the clause keeps
    its words (like the quoted episode title) from being mistaken for scene
    names, dialogue quotes, or descriptive keywords.
    """
    m = _ABOUT_RE.match(visual.strip())
    if not m:
        return "", visual
    anchor = re.sub(r"[\"“”‘’()\[\]]", " ", m.group(2))
    anchor = re.sub(r"\s+", " ", anchor).strip(" ,;:-—–")
    if len(anchor.split()) < 2:  # too vague to anchor a search
        return "", visual
    cleaned = m.group(1).rstrip(" ,;—–-")
    return anchor, (cleaned or visual)


def build_queries(beat: Beat, subject: str, max_q: int = 3) -> None:
    """
    Populate beat.image_queries and beat.clip_queries.

    STRICT relevance rules:
      - EVERY query is anchored to `subject` (the script's topic). The anchor is
        never dropped, so results stay on-topic only.
      - Only high-confidence signals are used as specifics:
          1. explicit CAPS scene names from the Visual line (quotes/parens removed)
          2. short quoted dialogue lines (<=6 words, no text-card/overlay strings)
      - On-Screen Text and Editor Notes are NEVER used for searching.
      - If a beat has no reliable specific, we fall back to the bare subject
        (still on-topic) rather than inventing an unrelated query.
    """
    subject = subject.strip()
    low = f"{beat.narration} {beat.visual}".lower()
    beat.is_film = not any(mk in low for mk in _NONFILM_MARKERS)  # info only

    # Per-beat anchor: the Visual line's own '— about <Movie + Year>' clause
    # beats the global subject (which may just be the essay's title). This is
    # what makes the tool FOLLOW the instructor file even when the GUI topic
    # field is off (e.g. topic "Why Gus Fring Killed Victor" but the beat says
    # 'about Breaking Bad "Box Cutter" 2011').
    anchor, visual_sig = _about_anchor(beat.visual)
    if anchor:
        subject = anchor

    # Signals come ONLY from the narration + Visual line (minus the about-
    # clause, whose quoted episode title is NOT dialogue or a scene name).
    scenes = _caps_scene_names(visual_sig)
    quotes = _quotes(visual_sig, allow_double=True) + _quotes(beat.narration, allow_double=False)

    specifics: List[str] = []
    for s in scenes[:2]:
        specifics.append(s)
    for q in quotes[:2]:
        specifics.append(q)

    # de-dup specifics (case-insensitive), keep order
    seen, uniq = set(), []
    for sp in specifics:
        if sp.lower() not in seen:
            seen.add(sp.lower())
            uniq.append(sp)

    # Fill remaining slots with descriptive keyword phrases from the Visual line
    # (still anchored to subject -> stays on-topic), so generic beats become
    # more specific instead of falling back to the bare subject.
    if len(uniq) < max_q:
        kws = _descriptive_keywords(visual_sig, limit=4)
        phrases = []
        if len(kws) >= 2:
            phrases.append(f"{kws[0]} {kws[1]}")
        if len(kws) >= 4:
            phrases.append(f"{kws[2]} {kws[3]}")
        elif len(kws) == 3:
            phrases.append(kws[2])
        elif len(kws) == 1:
            phrases.append(kws[0])
        for p in phrases:
            if len(uniq) >= max_q:
                break
            if p.lower() not in seen:
                seen.add(p.lower())
                uniq.append(p)

    uniq = uniq[:max_q]

    clip_q: List[str] = []
    img_q: List[str] = []
    for sp in uniq:
        base = f"{subject} {sp}".strip()
        img_q.append(base)
        # add a "scene" hint for video search unless the name already has it
        clip_q.append(base if re.search(r"scene$", base, re.I) else f"{base} scene")

    if not uniq:  # no reliable specific -> stay on-topic with the bare subject
        img_q.append(subject)
        clip_q.append(f"{subject} scene")

    def dedup(seq):
        s, res = set(), []
        for x in seq:
            x = _polish_query(x)
            if x and x.lower() not in s:
                s.add(x.lower())
                res.append(x)
        return res[:max_q]

    beat.clip_queries = dedup(clip_q)
    beat.image_queries = dedup(img_q)

    # Spoken lines (exact movie dialogue) help the tool lock the precise
    # timestamp via the transcript. Use explicit Spoken Line(s) plus any
    # double-quoted dialogue written in the Visual line (about-clause already
    # removed — its quoted episode title is a TITLE, not dialogue, and used to
    # mis-lock timestamps onto random mentions of it).
    vquotes = _quotes(visual_sig, allow_double=True)
    seenp, sp = set(), []
    for p in list(beat.spoken_lines) + vquotes:
        if p and p.lower() not in seenp:
            seenp.add(p.lower())
            sp.append(p)
    beat.spoken_lines = sp

    # Explicit image search terms from the instructor file take priority.
    if beat.image_terms:
        explicit = []
        for t in beat.image_terms:
            t = _polish_query(t.replace(" scene", "")) or t
            if subject.lower() not in t.lower():
                t = f"{subject} {t}"
            explicit.append(t)
        # de-dupe
        seen, out = set(), []
        for q in explicit + beat.image_queries:
            if q and q.lower() not in seen:
                seen.add(q.lower())
                out.append(q)
        beat.image_queries = out[:max(max_q, len(explicit))]


def parse_instructor(path: str, subject: str, max_q: int = 3) -> List[Beat]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    beats = parse_beats(text)
    for b in beats:
        build_queries(b, subject, max_q=max_q)
    return beats


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "scripts/tony_montana_visual_instructor.txt"
    subj = sys.argv[2] if len(sys.argv) > 2 else "Scarface 1983 Tony Montana"
    beats = parse_instructor(p, subj)
    print(f"Parsed {len(beats)} beats\n")
    for b in beats:
        tag = "FILM" if b.is_film else "EXTERNAL"
        print(f"[{b.index:02d}] ({b.section}) [{tag}]")
        print(f"     narr : {b.narration[:70]}")
        print(f"     CLIP : {b.clip_queries}")
        print(f"     IMG  : {b.image_queries}")
        print()
