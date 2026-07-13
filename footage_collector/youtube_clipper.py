"""
youtube_clipper.py
------------------
Keyless YouTube footage sourcing using yt-dlp + ffmpeg.

For a given search query it:
  1. searches YouTube (ytsearch, no API key),
  2. tries to locate the most relevant moment inside a candidate video by
     scanning its auto-generated subtitles for the scene's keywords,
  3. downloads only that ~N-second section and trims it to exact length.

Everything is best-effort with graceful fallbacks: if subtitles are missing
or no keyword matches, it falls back to a sensible offset into the video.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from typing import List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(_HERE, "bin")

# Call yt-dlp as a module of THIS Python interpreter. This works even when the
# `yt-dlp` command isn't on the system PATH (common on Windows after pip install).
_YTDLP = [sys.executable, "-m", "yt_dlp"]


def _exe(name: str) -> str:
    """Resolve ffmpeg/ffprobe: prefer a bundled ./bin copy, else system PATH."""
    for cand in (os.path.join(_BIN, name), os.path.join(_BIN, name + ".exe")):
        if os.path.isfile(cand):
            return cand
    return shutil.which(name) or shutil.which(name + ".exe") or name


def _ffmpeg_location_args() -> List[str]:
    """Tell yt-dlp where ffmpeg is, if we have a bundled copy."""
    if os.path.isdir(_BIN) and (os.path.isfile(os.path.join(_BIN, "ffmpeg"))
                                or os.path.isfile(os.path.join(_BIN, "ffmpeg.exe"))):
        return ["--ffmpeg-location", _BIN]
    return []


@dataclass
class ClipResult:
    path: str
    video_id: str
    url: str
    title: str
    start: float
    duration: float
    matched_text: str
    match_score: int

    def to_dict(self) -> dict:
        return asdict(self)


def _run(cmd: List[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


# --- authentication / anti-bot args ----------------------------------------
# YouTube blocks downloads from datacenter / unknown IPs with a
# "Sign in to confirm you're not a bot" error. On a normal machine where the
# user is logged into YouTube in their browser, passing cookies fixes this.

@dataclass
class YtAuth:
    cookies_file: Optional[str] = None          # path to a cookies.txt
    cookies_from_browser: Optional[str] = None  # e.g. "chrome", "firefox", "edge"
    player_client: Optional[str] = None         # e.g. "android", "web"

    def cookie_args(self) -> List[str]:
        """Just the cookie flags (no player-client), so callers can vary the
        client independently during format fallback."""
        out: List[str] = []
        if self.cookies_file:
            out += ["--cookies", self.cookies_file]
        if self.cookies_from_browser:
            out += ["--cookies-from-browser", self.cookies_from_browser]
        return out

    def args(self) -> List[str]:
        out = self.cookie_args()
        if self.player_client:
            out += ["--extractor-args", f"youtube:player_client={self.player_client}"]
        return out


DEFAULT_AUTH = YtAuth()

# yt-dlp player clients to fall back through when a video reports no usable
# formats ("Requested format is not available"). YouTube periodically breaks
# formats for the default (web) client via PO-token / SABR changes; the clients
# below usually still return a normal progressive/DASH stream. Varying the
# CLIENT — not just the -f format string — is the durable fix for the recurring
# "format is not available" breakage. Order = most reliable first.
_CLIENT_FALLBACKS = ["tv", "ios", "mweb", "web_safari", "android"]

# Errors where retrying other clients/formats is pointless (the video itself is
# gone or restricted). Stop immediately instead of grinding through every combo.
_TERMINAL_ERRORS = (
    "private video", "video unavailable", "removed by the user",
    "who has blocked it", "members-only", "join this channel",
    "not available in your country", "account has been terminated",
    "video has been removed",
)


def _is_format_error(reason: str) -> bool:
    r = reason.lower()
    return "format is not available" in r or "requested format" in r or "no video formats" in r


def _is_terminal_error(reason: str) -> bool:
    r = reason.lower()
    return any(t in r for t in _TERMINAL_ERRORS)


# --- search ----------------------------------------------------------------

# Titles that usually mean commentary/analysis (NOT actual movie footage).
_JUNK_TITLE = (
    "explained", "breakdown", "reaction", "react", "review", "analysis",
    "analy", "theory", "theories", "ranked", "ranking", "essay", "easter egg",
    "things you missed", "things you didnt", "facts", "top 10", "top ten",
    "retrospective", "podcast", "commentary", "explain", "iceberg",
    "why ", "how ", "vs ", "tier list", "deep dive", "recap", "summary",
    "discussion", "interview",
)
# Titles that usually ARE real movie footage.
_GOOD_TITLE = (
    "movie clip", "movie scene", "official clip", "scene", "clip", " hd",
    "4k", "remaster", "blu-ray", "bluray", "full scene",
)


def _title_score(title: str, duration: float) -> int:
    """Heuristic: positive = looks like real movie footage, negative = commentary."""
    t = " " + title.lower() + " "
    score = 0
    for kw in _JUNK_TITLE:
        if kw in t:
            score -= 4
    for kw in _GOOD_TITLE:
        if kw in t:
            score += 3
    # short clips are usually the actual scene; long videos are usually essays
    if duration:
        if duration <= 240:
            score += 2
        elif duration > 900:
            score -= 4
        elif duration > 480:
            score -= 2
    return score


def search_videos(query: str, limit: int = 8, max_minutes: int = 30,
                  auth: YtAuth = DEFAULT_AUTH) -> List[dict]:
    """
    Return candidate videos [{id, title, duration, title_score}, ...], best
    (most footage-like) first. Uses yt-dlp ytsearch (no API key).
    """
    cmd = _YTDLP + [
        f"ytsearch{limit}:{query}",
        "--flat-playlist",
        "--no-warnings",
        "--quiet",
        "--print", "%(id)s\t%(title)s\t%(duration)s",
    ] + auth.args()
    try:
        proc = _run(cmd, timeout=90)
    except subprocess.TimeoutExpired:
        return []
    results: List[dict] = []
    for line in proc.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 1 or not parts[0]:
            continue
        vid = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else ""
        dur_raw = parts[2].strip() if len(parts) > 2 else ""
        try:
            dur = float(dur_raw)
        except ValueError:
            dur = 0.0
        if max_minutes and dur and dur > max_minutes * 60:
            continue
        results.append({
            "id": vid, "title": title, "duration": dur,
            "title_score": _title_score(title, dur),
        })
    # Best-looking footage first.
    results.sort(key=lambda r: r["title_score"], reverse=True)
    return results


# --- subtitle based timestamp matching -------------------------------------

_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)


def _ts_to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _parse_vtt(path: str) -> List[tuple]:
    """Parse a .vtt/.srt file into [(start_sec, end_sec, text), ...]."""
    cues: List[tuple] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return cues

    blocks = re.split(r"\n\s*\n", content)
    for block in blocks:
        m = _TS_RE.search(block)
        if not m:
            continue
        start = _ts_to_sec(*m.group(1, 2, 3, 4))
        end = _ts_to_sec(*m.group(5, 6, 7, 8))
        # text = everything after the timestamp line
        lines = block.splitlines()
        text_lines = []
        seen_ts = False
        for ln in lines:
            if _TS_RE.search(ln):
                seen_ts = True
                continue
            if seen_ts:
                # strip vtt inline tags like <00:00:01.000><c> ... </c>
                clean = re.sub(r"<[^>]+>", "", ln).strip()
                if clean:
                    text_lines.append(clean)
        text = " ".join(text_lines)
        if text:
            cues.append((start, end, text))
    return cues


def _norm_txt(s: str) -> str:
    """lowercase + strip punctuation + collapse spaces (both sides of a phrase
    comparison get this, so curly vs straight apostrophes etc. never matter)."""
    s = re.sub(r"[^a-z0-9 ]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _phrase_cue_hits(cues: List[tuple], norm_phrases: List[str]) -> set:
    """Indices of cues where a full spoken phrase STARTS.

    Subtitle cues are only ~2-4s long, so a multi-sentence Spoken Line never
    fits inside a single cue and per-cue substring matching silently misses it.
    We search each phrase in the CONCATENATED transcript instead and map the
    match position back to the cue it starts in.
    """
    hits: set = set()
    if not cues or not norm_phrases:
        return hits
    joined = ""
    spans = []  # (start_char, end_char) of each cue's text inside `joined`
    for (_s, _e, txt) in cues:
        nc = _norm_txt(txt)
        a = len(joined)
        joined += nc + " "
        spans.append((a, a + len(nc)))
    for pn in norm_phrases:
        for m in re.finditer(re.escape(pn), joined):
            p = m.start()
            for i, (a, b) in enumerate(spans):
                if a <= p <= b:
                    hits.add(i)
                    break
    return hits


def _fetch_subtitles(video_id: str, workdir: str, auth: YtAuth = DEFAULT_AUTH) -> Optional[str]:
    """Download auto/manual English subs (vtt) without the video. Returns path."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_tmpl = os.path.join(workdir, "%(id)s.%(ext)s")
    cmd = _YTDLP + [
        url,
        "--skip-download",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", "en.*,en",
        "--sub-format", "vtt/srt/best",
        "--no-warnings", "--quiet",
        "-o", out_tmpl,
    ] + auth.args()
    try:
        _run(cmd, timeout=90)
    except subprocess.TimeoutExpired:
        return None
    for fn in os.listdir(workdir):
        if fn.startswith(video_id) and (fn.endswith(".vtt") or fn.endswith(".srt")):
            return os.path.join(workdir, fn)
    return None


def best_timestamp(
    video_id: str,
    keywords: List[str],
    duration: float,
    workdir: str,
    auth: YtAuth = DEFAULT_AUTH,
    phrases: Optional[List[str]] = None,
) -> Optional[tuple]:
    """
    Find the start time (seconds) of the best-matching subtitle window.
    If `phrases` (exact spoken lines) are given, a contiguous phrase match
    locks onto that exact moment (huge score) - this is how we hit the precise
    timestamp from dialogue the LLM provided, without needing a timestamp.
    Returns (start_sec, matched_text, score) or None.
    """
    sub_path = _fetch_subtitles(video_id, workdir, auth)
    if not sub_path:
        return None
    cues = _parse_vtt(sub_path)
    if not cues:
        return None

    kw = [k.lower() for k in keywords if len(k) >= 4]
    norm_phrases = []
    for p in (phrases or []):
        pn = re.sub(r"[^a-z0-9 ]", "", p.lower()).strip()
        pn = re.sub(r"\s+", " ", pn)
        if len(pn) >= 6:
            norm_phrases.append(pn)

    if not kw and not norm_phrases:
        return None

    # Full-phrase matches are found across cue boundaries (long Spoken Lines
    # span several cues); each hit marks the cue where the phrase starts.
    phrase_cues = _phrase_cue_hits(cues, norm_phrases)

    best = None  # (score, start, text)
    for i, (start, end, text) in enumerate(cues):
        low = text.lower()
        low_norm = _norm_txt(low)
        score = sum(1 for k in kw if k in low)
        # exact dialogue phrase match = strong lock on the precise moment
        if i in phrase_cues:
            score += 100
        else:
            for pn in norm_phrases:
                # partial: most words of the phrase present in this cue
                words = [w for w in pn.split() if len(w) >= 4]
                if words:
                    hit = sum(1 for w in words if w in low_norm)
                    if hit >= max(2, len(words) * 0.6):
                        score += 20
        if score == 0:
            continue
        if best is None or score > best[0]:
            best = (score, start, text)

    if best is None:
        return None
    return (max(0.0, best[1]), best[2], best[0])


# --- download + trim -------------------------------------------------------

def _ffprobe_duration(path: str) -> float:
    cmd = [
        _exe("ffprobe"), "-v", "error", "-show_entries", "format=duration",
        "-of", "json", path,
    ]
    try:
        proc = _run(cmd, timeout=30)
        data = json.loads(proc.stdout or "{}")
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception:
        return 0.0


def _err_reason(proc) -> str:
    """Pull a short, human-readable failure reason out of yt-dlp output."""
    text = (getattr(proc, "stderr", "") or "") + "\n" + (getattr(proc, "stdout", "") or "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if "ERROR" in ln or "error" in ln.lower():
            return ln[:220]
    return (lines[-1][:220] if lines else "unknown error")


def check_tools() -> dict:
    """Verify yt-dlp and ffmpeg are usable; used for a startup preflight line."""
    info = {}
    try:
        p = _run(_YTDLP + ["--version"], timeout=60)
        info["yt_dlp"] = p.stdout.strip() if p.returncode == 0 else "MISSING (pip install yt-dlp)"
    except Exception:
        info["yt_dlp"] = "MISSING (pip install yt-dlp)"
    ff = _exe("ffmpeg")
    try:
        p = _run([ff, "-version"], timeout=30)
        info["ffmpeg"] = (ff if p.returncode == 0 else "MISSING")
    except Exception:
        info["ffmpeg"] = "MISSING"
    return info


def download_section(
    video_id: str,
    start: float,
    duration: float,
    out_path: str,
    max_height: int = 720,
    auth: YtAuth = DEFAULT_AUTH,
    normalize_169: bool = True,
    target_w: int = 1920,
    target_h: int = 1080,
) -> tuple:
    """Download [start, start+duration] and normalise to 16:9 mp4.
    Returns (ok: bool, reason: str)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    end = start + duration
    workdir = tempfile.mkdtemp(prefix="ytclip_")
    raw_tmpl = os.path.join(workdir, "raw.%(ext)s")
    section = f"*{start:.2f}-{end:.2f}"

    # Try several format selectors. YouTube + an out-of-date yt-dlp often throws
    # "Requested format is not available"; falling back to plain best usually works.
    fmt_candidates = [
        f"bv*[height<={max_height}]+ba/b[height<={max_height}]",
        "bv*+ba/b",
        "b",
        "best",
    ]

    # Player clients to try, in order. If the user forced one, honour it first,
    # then fall through to the rest — YouTube frequently disables formats for a
    # single client (PO-token / SABR changes) while the others keep working, so
    # a "format not available" error is usually fixed by switching CLIENT, not
    # just the -f string. `None` = yt-dlp's own default client set.
    if auth.player_client:
        clients = [auth.player_client] + [c for c in _CLIENT_FALLBACKS
                                          if c != auth.player_client]
    else:
        clients = [None] + _CLIENT_FALLBACKS
    cookie_args = auth.cookie_args()

    proc = None
    raw = None
    last_reason = "download failed"
    got = False
    for client in clients:
        client_args = (["--extractor-args", f"youtube:player_client={client}"]
                       if client else [])
        for fmt in fmt_candidates:
            for fn in os.listdir(workdir):       # clear any partial leftovers
                try:
                    os.remove(os.path.join(workdir, fn))
                except OSError:
                    pass
            cmd = _YTDLP + [
                url,
                "--download-sections", section,
                "--force-keyframes-at-cuts",
                "-f", fmt,
                "--merge-output-format", "mp4",
                "--no-warnings",
                "-o", raw_tmpl,
            ] + _ffmpeg_location_args() + cookie_args + client_args
            try:
                proc = _run(cmd, timeout=300)
            except subprocess.TimeoutExpired:
                shutil.rmtree(workdir, ignore_errors=True)
                return False, "yt-dlp timed out"

            raw = None
            for fn in os.listdir(workdir):
                if fn.startswith("raw"):
                    raw = os.path.join(workdir, fn)
                    break
            if raw and os.path.getsize(raw) > 0:
                got = True
                break  # got it
            last_reason = _err_reason(proc)
            # The video is genuinely gone/restricted — stop trying everything.
            if _is_terminal_error(last_reason):
                shutil.rmtree(workdir, ignore_errors=True)
                return False, last_reason
            # Only cycle through the other -f strings for format errors. For any
            # other error (bot-check, extraction fail, etc.) break to the next
            # CLIENT, which often serves formats the current one refuses.
            if not _is_format_error(last_reason):
                break
        if got:
            break

    if not raw or os.path.getsize(raw) == 0:
        shutil.rmtree(workdir, ignore_errors=True)
        return False, last_reason

    # Re-trim to exact duration, normalise to a clean 16:9 1080p mp4.
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    ff = [_exe("ffmpeg"), "-y", "-i", raw, "-t", f"{duration:.2f}"]
    if normalize_169:
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30"
        )
        ff += ["-vf", vf]
    ff += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    try:
        ffproc = _run(ff, timeout=180)
    except subprocess.TimeoutExpired:
        shutil.rmtree(workdir, ignore_errors=True)
        return False, "ffmpeg timed out"

    shutil.rmtree(workdir, ignore_errors=True)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return True, ""
    return False, _err_reason(ffproc) or "ffmpeg produced no output"


# --- top-level orchestration ----------------------------------------------

PRE_ROLL = 1.0  # start the clip ~1s before the matched line for action context


def collect_clip(
    query: str,
    keywords: List[str],
    out_path: str,
    duration: float = 5.0,
    search_n: int = 8,
    max_height: int = 720,
    auth: YtAuth = DEFAULT_AUTH,
    exclude_ids: Optional[set] = None,
    used_sections: Optional[set] = None,
    phrases: Optional[List[str]] = None,
) -> tuple:
    """
    Full pipeline for one scene clip:
      1. search YouTube and rank candidates by how much they look like real
         movie footage (title) rather than commentary/reaction/essay videos
      2. read each candidate's subtitles and score keyword match (so we pick the
         video + timestamp that ACTUALLY has the moment)
      3. download a short window centred on the best-matching line
      4. normalise to a clean 16:9 1080p mp4

    `exclude_ids`    : video ids to skip entirely (global de-dup).
    `used_sections`  : set of "videoid@bucket" already used anywhere, so the
                       SAME clip section never repeats across scenes.
    Returns (ClipResult | None, reason).
    """
    exclude_ids = exclude_ids or set()
    used_sections = used_sections if used_sections is not None else set()
    candidates = search_videos(query, limit=search_n, auth=auth)
    candidates = [c for c in candidates if c["id"] not in exclude_ids]
    if not candidates:
        return None, "no YouTube search results"

    last_reason = "download failed"
    workdir = tempfile.mkdtemp(prefix="ytsubs_")
    try:
        # Score candidates: subtitle keyword match (x3) + footage-like title.
        scored = []
        for cand in candidates:
            vid = cand["id"]
            vdur = cand["duration"] or 0.0
            ts = best_timestamp(vid, keywords, duration, workdir, auth, phrases=phrases)
            if ts is not None:
                m_start, matched, kscore = ts
            else:
                m_start, matched, kscore = None, "", 0
            combined = kscore * 3 + cand.get("title_score", 0)
            scored.append((combined, kscore, cand, vdur, m_start, matched))

        scored.sort(key=lambda x: (x[0], -(x[3] or 1e9)), reverse=True)

        for combined, kscore, cand, vdur, m_start, matched in scored:
            vid = cand["id"]
            if m_start is not None and kscore > 0:
                start = max(0.0, m_start - PRE_ROLL)
            else:
                start = max(5.0, vdur * 0.2) if vdur else 30.0

            if vdur and start + duration > vdur:
                start = max(0.0, vdur - duration - 1)

            # Skip a section that was already used elsewhere (no repeats).
            bucket = f"{vid}@{int(start // 3)}"
            if bucket in used_sections:
                continue

            ok, reason = download_section(vid, start, duration, out_path, max_height, auth)
            if ok:
                used_sections.add(bucket)
                return ClipResult(
                    path=out_path,
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    title=cand["title"],
                    start=round(start, 2),
                    duration=duration,
                    matched_text=matched,
                    match_score=kscore,
                ), ""
            last_reason = reason or last_reason
        return None, last_reason
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def extract_frames(clip_path: str, n: int, out_dir: str, prefix: str = "frame") -> List[str]:
    """Grab N evenly-spaced still frames from a clip (on-point images straight
    from the matching footage). Returns list of saved image paths."""
    if n <= 0 or not os.path.isfile(clip_path):
        return []
    dur = _ffprobe_duration(clip_path) or 5.0
    os.makedirs(out_dir, exist_ok=True)
    paths: List[str] = []
    for i in range(n):
        frac = (i + 1) / (n + 1)
        t = max(0.1, dur * frac)
        outp = os.path.join(out_dir, f"{prefix}_{i + 1:02d}.jpg")
        cmd = [_exe("ffmpeg"), "-y", "-ss", f"{t:.2f}", "-i", clip_path,
               "-frames:v", "1", "-q:v", "2", outp]
        try:
            _run(cmd, timeout=60)
        except subprocess.TimeoutExpired:
            continue
        if os.path.exists(outp) and os.path.getsize(outp) > 0:
            paths.append(outp)
    return paths


def _parse_time(s: str):
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return float(s)
    if ":" in s:
        try:
            parts = [float(p) for p in s.split(":")]
        except ValueError:
            return None
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec
    m = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", s, re.I)
    if m and any(m.groups()):
        h, mi, se = (int(g) if g else 0 for g in m.groups())
        return float(h * 3600 + mi * 60 + se)
    return None


def parse_youtube_ref(ref: str):
    """From a YouTube URL (optionally with timestamp/range) return
    (video_id, start_sec|None, end_sec|None)."""
    vid = None
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{11})", ref)
    if m:
        vid = m.group(1)
    start = end = None
    ms = re.search(r"[?#&](?:t|start)=([0-9hms:]+)", ref, re.I)
    if ms:
        start = _parse_time(ms.group(1))
    me = re.search(r"[?#&]end=([0-9hms:]+)", ref, re.I)
    if me:
        end = _parse_time(me.group(1))
    # trailing range "1:23-1:30" or "@1:23" / "[1:23]"
    rng = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(\d{1,2}:\d{2}(?::\d{2})?)", ref)
    if rng:
        start = _parse_time(rng.group(1))
        end = _parse_time(rng.group(2))
    elif start is None:
        t1 = re.search(r"(?:@|\[)(\d{1,2}:\d{2}(?::\d{2})?)", ref)
        if t1:
            start = _parse_time(t1.group(1))
    return vid, start, end


def clip_from_reference(
    ref: str,
    keywords: List[str],
    out_path: str,
    duration: float = 5.0,
    auth: YtAuth = DEFAULT_AUTH,
    used_sections: Optional[set] = None,
    verify: bool = True,
    phrases: Optional[List[str]] = None,
) -> tuple:
    """
    Try to use an LLM/human-provided YouTube link (+ optional timestamp) for a
    scene. VERIFIES the video is downloadable and, if it has subtitles, that the
    scene keywords actually appear (LLMs hallucinate links!). If verification
    fails the caller should fall back to search.
    Returns (ClipResult | None, reason).
    """
    vid, start, end = parse_youtube_ref(ref)
    if not vid:
        return None, "not a valid YouTube link"

    workdir = tempfile.mkdtemp(prefix="ytref_")
    try:
        kwmatch, best_start, matched = 0, None, ""
        sub = _fetch_subtitles(vid, workdir, auth)
        if sub:
            cues = _parse_vtt(sub)
            kw = [k.lower() for k in keywords if len(k) >= 4]
            norm_phrases = []
            for p in (phrases or []):
                pn = _norm_txt(p)
                if len(pn) >= 6:
                    norm_phrases.append(pn)
            # full phrases are matched across cue boundaries (long Spoken
            # Lines never fit inside one 2-4s subtitle cue)
            phrase_cues = _phrase_cue_hits(cues, norm_phrases)
            best = None
            for i, (s, e, txt) in enumerate(cues):
                low = txt.lower()
                sc = sum(1 for k in kw if k in low)
                if i in phrase_cues:
                    sc += 100
                if sc > 0 and (best is None or sc > best[0]):
                    best = (sc, s, txt)
            if best:
                kwmatch, best_start, matched = best[0], best[1], best[2]

        # Verification: ONLY for links WITHOUT an explicit timestamp. A human/
        # web-search-provided "?t=" is the author telling us the exact moment —
        # honour it. Scene keywords describe what's ON SCREEN (visuals), and a
        # silent/action beat's transcript will never contain them, so a zero
        # keyword match must not veto a timestamped link. Timestamp-less links
        # still need SOME transcript evidence to anchor a start time.
        if (verify and sub and kwmatch == 0 and start is None
                and any(len(k) >= 4 for k in keywords)):
            return None, "provided link did not match scene transcript (falling back)"

        # Decide the start. If a provided link came with a coarse/large range,
        # but we found the exact dialogue line in the transcript, prefer that
        # precise moment. Otherwise honour the provided timestamp.
        refined = (kwmatch >= 100 and best_start is not None)
        if refined:
            start = max(0.0, best_start - PRE_ROLL)
            dur = duration
        elif start is not None:
            dur = duration
            if end and end > start:
                span = end - start
                dur = span if span <= 15 else duration  # ignore "full scene" ranges
        else:
            start = best_start if best_start is not None else 0.0
            if start > PRE_ROLL:
                start -= PRE_ROLL
            dur = duration

        bucket = f"{vid}@{int(start // 3)}"
        if used_sections is not None and bucket in used_sections:
            return None, "section already used"

        ok, reason = download_section(vid, start, dur, out_path, 720, auth)
        if ok:
            if used_sections is not None:
                used_sections.add(bucket)
            return ClipResult(
                path=out_path, video_id=vid, url=ref, title="(provided link)",
                start=round(start, 2), duration=dur,
                matched_text=matched, match_score=kwmatch,
            ), ""
        return None, reason
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "Scarface Tony Montana say hello to my little friend"
    print("Searching:", q)
    cands = search_videos(q, limit=3)
    for c in cands:
        print(" ", c)
    if cands:
        res, reason = collect_clip(
            q,
            keywords=["hello", "little", "friend"],
            out_path="/tmp/test_clip/clip.mp4",
            duration=6.0,
            search_n=3,
        )
        print("RESULT:", res)
        print("REASON:", reason)
