"""
scene_parser.py
---------------
Takes a raw video script (transcript) + title and breaks it into ordered
"scene beats". For each beat it builds a search query that can be used to
find relevant YouTube footage and images.

No API keys, no LLM. Pure-Python heuristics:
  - sentence splitting
  - grouping sentences into beats
  - named-entity / keyword extraction (capitalised phrases + salient nouns)
  - a global "context" derived from the title + most frequent proper nouns,
    so every query is anchored to the actual subject of the video
    (e.g. "Scarface Tony Montana").
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List

# Words we never want to treat as keywords / entities.
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "as", "of", "to",
    "in", "on", "at", "by", "for", "with", "from", "into", "over", "under",
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does",
    "did", "have", "has", "had", "will", "would", "can", "could", "should",
    "shall", "may", "might", "must", "this", "that", "these", "those", "it",
    "its", "he", "she", "they", "them", "his", "her", "their", "you", "your",
    "we", "us", "our", "i", "me", "my", "him", "who", "whom", "whose", "which",
    "what", "when", "where", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "than", "too", "very", "just", "now", "out", "up", "down", "off",
    "about", "again", "here", "there", "one", "two", "three", "makes", "make",
    "made", "like", "still", "ever", "never", "every", "everything", "nothing",
    "something", "someone", "anyone", "him.", "really", "actually", "because",
    "while", "after", "before", "through", "around", "between", "without",
}


@dataclass
class Scene:
    index: int
    text: str
    query: str
    keywords: List[str] = field(default_factory=list)

    def slug(self) -> str:
        return f"scene_{self.index:03d}"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "query": self.query,
            "keywords": self.keywords,
        }


# --- sentence splitting ----------------------------------------------------

_ABBREV = {"mr", "mrs", "ms", "dr", "st", "vs", "etc", "jr", "sr"}


def _norm_token(tok: str) -> str:
    """Strip possessive 's / ’s and surrounding apostrophes."""
    tok = tok.strip("’'")
    tok = re.sub(r"(?:’s|'s)$", "", tok, flags=re.IGNORECASE)
    return tok


def split_sentences(text: str) -> List[str]:
    """Lightweight sentence splitter that tolerates common abbreviations."""
    text = re.sub(r"\s+", " ", text.strip())
    # Split on ., !, ? followed by whitespace + capital / quote / digit.
    raw = re.split(r"(?<=[.!?])\s+(?=[\"'A-Z0-9])", text)
    out: List[str] = []
    for s in raw:
        s = s.strip()
        if not s:
            continue
        # Merge fragments that ended on an abbreviation.
        last_word = re.sub(r"[^a-zA-Z]", "", s.split()[-1].lower()) if s.split() else ""
        if out and last_word in _ABBREV:
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out


# --- keyword / entity extraction -------------------------------------------

def build_proper_nouns(full_text: str) -> set:
    """
    Determine which capitalised words are *real* proper nouns by ignoring
    sentence-initial capitalisation. A token counts as a proper noun if it
    ever appears capitalised in a non-initial position of a sentence.
    Multi-word capitalised phrases are also collected.
    """
    proper: set = set()
    for sentence in split_sentences(full_text):
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9'’]*", sentence)
        for pos, tok in enumerate(tokens):
            if pos == 0:
                continue  # skip sentence-initial word (always capitalised)
            if tok[0].isupper() and tok.lower() not in STOPWORDS:
                proper.add(_norm_token(tok).lower())
    return proper


def extract_entities(text: str, proper_nouns: set | None = None) -> List[str]:
    """
    Pull out proper-noun phrases from a chunk of mixed-case text. Runs of
    capitalised words are kept together. When `proper_nouns` is supplied,
    single tokens must belong to it (filters out sentence-initial words);
    multi-word capitalised phrases are always kept.
    """
    phrases = re.findall(r"\b([A-Z][a-zA-Z0-9'’]+(?:\s+[A-Z][a-zA-Z0-9'’]+)*)\b", text)
    cleaned: List[str] = []
    for p in phrases:
        words = [_norm_token(w) for w in p.split() if w.lower() not in STOPWORDS]
        words = [w for w in words if w]
        if not words:
            continue
        phrase = " ".join(words)
        if len(phrase) <= 1:
            continue
        is_multiword = len(words) > 1
        if proper_nouns is not None and not is_multiword:
            if words[0].lower() not in proper_nouns:
                continue  # sentence-initial common word, skip
        cleaned.append(phrase)
    return cleaned


def extract_keywords(text: str, limit: int = 4) -> List[str]:
    """Salient lowercase content words, ranked by length (proxy for specificity)."""
    words = re.findall(r"[a-zA-Z][a-zA-Z'’]+", text.lower())
    cand = [w for w in words if w not in STOPWORDS and len(w) >= 5]
    # de-dup preserving order, then prefer longer (more specific) words
    seen = set()
    uniq = []
    for w in cand:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    uniq.sort(key=len, reverse=True)
    return uniq[:limit]


# --- global context derivation ---------------------------------------------

def derive_context(title: str, full_text: str, max_terms: int = 2) -> str:
    """
    Build a short anchor string that every query is prefixed with, e.g.
    "Scarface Tony Montana". Combines the most frequent proper nouns in the
    body with meaningful title tokens, collapsing substring duplicates
    (so "Tony" + "Tony Montana" -> "Tony Montana").
    """
    proper = build_proper_nouns(full_text)

    title_tokens = [
        t for t in re.findall(r"[A-Za-z0-9']+", title)
        if t.lower() not in STOPWORDS and len(t) > 1
    ]
    title_part = " ".join(title_tokens[:3]).strip()

    ents = extract_entities(full_text, proper)
    freq = Counter(e for e in ents if len(e.split()) <= 3)
    common = [name for name, _ in freq.most_common(6)]

    # Order candidates: most frequent body subjects first, then title.
    candidates = common + ([title_part] if title_part else [])

    chosen: List[str] = []
    for term in candidates:
        t_low = term.lower()
        if not t_low:
            continue
        # Collapse substrings: replace a shorter chosen term with this longer
        # one, or skip if this is contained in something already chosen.
        contained = any(t_low in c.lower() for c in chosen)
        if contained:
            continue
        chosen = [c for c in chosen if c.lower() not in t_low]
        chosen.append(term)
        if len(chosen) >= max_terms:
            break
    return " ".join(chosen[:max_terms]).strip()


# --- main entry ------------------------------------------------------------

def chunk_by_words(sentences: List[str], target_words: int = 150) -> List[List[str]]:
    """
    Group consecutive sentences into chunks of roughly `target_words` words
    (paragraph-sized scenes). A chunk closes once it reaches the target; very
    long single sentences become their own chunk.
    """
    chunks: List[List[str]] = []
    cur: List[str] = []
    cur_words = 0
    for s in sentences:
        wc = len(s.split())
        if cur and cur_words + wc > target_words:
            chunks.append(cur)
            cur, cur_words = [], 0
        cur.append(s)
        cur_words += wc
    if cur:
        chunks.append(cur)
    return chunks


def parse_script(
    title: str,
    script: str,
    sentences_per_scene: int = 1,
    words_per_scene: int | None = None,
    context: str | None = None,
) -> List[Scene]:
    """
    Returns an ordered list of Scene objects. `context` overrides the
    auto-derived global anchor if provided.

    If `words_per_scene` is given, the script is split into paragraph-sized
    scenes of about that many words; otherwise it groups `sentences_per_scene`
    sentences per scene.
    """
    if context is None:
        context = derive_context(title, script, max_terms=2)

    proper_nouns = build_proper_nouns(script)
    sentences = split_sentences(script)

    if words_per_scene:
        chunk_groups = chunk_by_words(sentences, words_per_scene)
    else:
        chunk_groups = [
            sentences[i:i + sentences_per_scene]
            for i in range(0, len(sentences), sentences_per_scene)
        ]

    scenes: List[Scene] = []
    idx = 0

    for chunk_sents in chunk_groups:
        chunk = " ".join(chunk_sents).strip()
        if not chunk:
            continue
        idx += 1

        entities = extract_entities(chunk, proper_nouns)
        # Drop entities already covered by context to avoid duplication.
        ctx_lower = context.lower()
        beat_entities = [e for e in entities if e.lower() not in ctx_lower]
        keywords = extract_keywords(chunk)

        # Build the query: context anchor + most distinctive beat terms.
        query_bits: List[str] = []
        if context:
            query_bits.append(context)
        if beat_entities:
            query_bits.append(beat_entities[0])
        elif keywords:
            query_bits.append(keywords[0])

        query = " ".join(query_bits).strip()
        if not query:
            query = title

        scenes.append(
            Scene(
                index=idx,
                text=chunk,
                query=query,
                keywords=(beat_entities[:3] + keywords)[:6],
            )
        )

    return scenes


if __name__ == "__main__":
    # quick self-test
    demo_title = "WHAT MAKES TONY MONTANA SO TERRIFYING"
    demo = (
        "Tony Montana has been dead since 1983. He has never been more popular. "
        "A Camorra boss in Naples reportedly built himself an exact replica of "
        "Tony's Miami mansion. Oliver Stone was deep in his own cocaine addiction."
    )
    ctx = derive_context(demo_title, demo)
    print("CONTEXT:", ctx)
    for sc in parse_script(demo_title, demo):
        print(f"[{sc.index}] q='{sc.query}' kw={sc.keywords}")
        print("    ", sc.text[:70])
