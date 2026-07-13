# TECHNICAL REFERENCE — Footage Collector (for an LLM that will edit the code)

Pair this with `00_PROJECT_HANDOFF.md`. This file maps the code so you can change
it safely. Language: Python 3.10+ (works on 3.14). External: `yt-dlp`, `ddgs`,
`requests`, `Pillow`, and system `ffmpeg`/`ffprobe`.

================================================================
## REPO LAYOUT (footage_collector/)
================================================================
- `collector.py`        — main entry + CLI + orchestration (the conductor)
- `instructor_parser.py`— parses the visual instructor file → scene specs/queries
- `scene_parser.py`     — fallback: split a raw script into beats + auto queries
- `youtube_clipper.py`  — YouTube search, transcript timestamping, clip download,
                          16:9 normalise, frame extraction, link parsing/verify
- `image_collector.py`  — DuckDuckGo image search + landscape/high‑res filter +
                          global de‑dup (md5 + perceptual hash)
- `gui.py`              — Tkinter desktop UI (calls collector.py as a subprocess)
- `requirements.txt`    — pip deps (yt-dlp, ddgs, requests, Pillow)
- `setup.bat`/`run.bat` — Windows one‑time setup (installs deps + ffmpeg to bin/) / launch
- `setup.sh`/`run.sh`   — macOS/Linux equivalents
- `update_tools.bat`    — upgrade yt-dlp + ddgs + requests + Pillow (run when broken)
- `update_ytdlp.bat`    — upgrade just yt-dlp
- `bin/`                — bundled ffmpeg.exe/ffprobe.exe (created by setup.bat)
- `SETUP_GUIDE.md`, `MAINTENANCE.md` — user guides
- `scripts/`            — sample scripts + instructor files (Tony Montana, The Thing)
- `plans/scarface_plan.json` — example of the older "plan" JSON input
- `claude_project/`     — kit to generate instructor files (Custom GPT / Gem /
                          Genspark prompts, FORMAT_SPEC, EXAMPLE, HOW_TO_SET_UP)
- `output/`, `output_thing/` — sample generated outputs
- `HANDOFF/`            — this documentation

================================================================
## DATA FLOW
================================================================
```
instructor .txt ──instructor_parser.parse_instructor()──► [Beat,...]
                                                              │
collector.specs_from_instructor()  (adds year to subject)     ▼
                                                       [SceneSpec,...]
collector.main() loop, per SceneSpec:
   clip_links? ─► youtube_clipper.clip_from_reference()  (verify+refine via Spoken Line)
        else  ─► youtube_clipper.collect_clip()          (search+rank+timestamp)
                     └─ search_videos() → best_timestamp(phrases) → download_section()
   frames    ─► youtube_clipper.extract_frames(clip)
   images    ─► image_collector.collect_images(queries, dedup=DedupState)
   write scene.txt + append to manifest.json
```

================================================================
## MODULE: collector.py
================================================================
- `SceneSpec` dataclass: index, text, image_queries[], clip_queries[], keywords[],
  summary, section, on_screen, notes, clip_links[], spoken_lines[]. `.slug()` → "scene_001".
- `_prepend_local_bin()` — adds `./bin` to PATH so bundled ffmpeg is found. Called first in main().
- `_augment_subject_with_year(subject, *texts)` — appends the most common
  19xx/20xx year found in the instructor/script if subject has none.
- `specs_from_instructor(path, args)` — derives subject (args.context or from
  clean script via scene_parser.derive_context, then year‑augmented), calls
  `instructor_parser.parse_instructor`, maps Beats → SceneSpecs.
- `specs_from_script(...)` and `specs_from_plan(...)` — alternative inputs (raw
  script auto‑mode; legacy plan JSON).
- `build_arg_parser()` — all CLI flags (see below).
- `main()` — prints header + preflight (`yt.check_tools()`), then per scene:
  - CLIPS: first loop over `scene.clip_links` via `yt.clip_from_reference(... phrases=scene.spoken_lines)`;
    remaining slots via `yt.collect_clip(... exclude_ids=used_video_ids, used_sections=clip_sections, phrases=scene.spoken_lines)`.
  - FRAMES: `yt.extract_frames(clip_path, args.frames_per_clip, scene_dir, prefix=...)`.
  - IMAGES: `ic.collect_images(scene.image_queries, scene_dir, count, min_width, dedup=dedup)`.
  - writes `scene.txt` and incrementally saves `manifest.json`.
  - Globals across scenes: `dedup = ic.DedupState()`, `clip_sections = set()`.

### CLI flags
`--instructor <f>` | `--plan <f>` | `--script <f>` (choose one input)
`--title`, `--out`, `--context` (topic anchor; year auto‑added if missing)
`--words-per-scene` (default 150, script mode), `--sentences-per-scene`
`--clip-duration` (5), `--clips-per-scene` (2), `--images-per-scene` (4),
`--frames-per-clip` (2)
`--search-n` (8), `--max-height` (720), `--min-image-width` (1280)
`--max-scenes`, `--start-scene` (batching/resume)
`--cookies <cookies.txt>`, `--cookies-from-browser <chrome|firefox|...>`, `--player-client`
`--dry-run` (parse + print queries only; downloads nothing)

================================================================
## MODULE: instructor_parser.py
================================================================
- `Beat` dataclass: index, section, narration, visual, on_screen, notes, is_film,
  clip_links[], spoken_lines[], image_terms[], image_queries[], clip_queries[].
- `_LABELS` — regexes for: narration (`Script Cue (narration):`), visual
  (`Visual / Exact Clip to Use:`), clip_links (`Clip Links:`/`Clips:`/`YouTube:`),
  spoken (`Spoken Line:`/`Dialogue:`), image_terms (`Image Search:`/`Images:`),
  onscreen (`On-Screen Text:`), notes (`Editor Notes:`).
- `parse_beats(text)` — state machine: section headers (ALL‑CAPS, no punctuation)
  set the current section; each `Script Cue` starts a new beat; continuation lines
  append to the current field.
- `build_queries(beat, subject, max_q=3)` — builds clip_queries + image_queries:
  - ALWAYS prefixes `subject`. Signals (in priority): CAPS scene names
    (`_caps_scene_names`), short quoted dialogue (`_quotes`), then anchored
    descriptive keywords (`_descriptive_keywords`). `Image Search:` terms override
    image_queries. Also sets `beat.spoken_lines` = explicit Spoken Line(s) +
    quoted dialogue from the Visual line.
- `parse_instructor(path, subject, max_q)` → [Beat] with queries filled.
- Helpers: `_split_links`, `_split_terms`, `_split_spoken`, `_polish_query`
  (trims, de‑dupes words so repeated "The Thing 1982" collapses), `_looks_like_section`.

================================================================
## MODULE: youtube_clipper.py
================================================================
- `YtAuth(cookies_file, cookies_from_browser, player_client)`; `.args()` → yt-dlp flags.
- `_YTDLP = [sys.executable, "-m", "yt_dlp"]` — ALWAYS call yt-dlp this way (PATH‑safe).
- `_exe(name)` — resolve ffmpeg/ffprobe from `./bin` or PATH. `_ffmpeg_location_args()`.
- `search_videos(query, limit=8, max_minutes=30, auth)` → [{id,title,duration,title_score}]
  sorted by `_title_score` (penalise explained/breakdown/reaction/review/essay/long;
  reward movie clip/scene/HD/short).
- `best_timestamp(video_id, keywords, duration, workdir, auth, phrases=None)` —
  fetches subs (`_fetch_subtitles` → `_parse_vtt`), scores cues by keyword overlap;
  a contiguous **phrase** (exact Spoken Line) match adds +100 → locks the precise
  cue. Returns (start, matched_text, score) or None.
- `download_section(video_id, start, duration, out_path, max_height=720, auth, normalize_169=True, target_w=1920, target_h=1080)` →
  (ok, reason). Tries a **format fallback list** (handles "format not available");
  downloads only the section (`--download-sections`), then ffmpeg re‑encodes to a
  clean 16:9 1080p 30fps mp4 (scale+pad).
- `collect_clip(query, keywords, out_path, duration=5, search_n=8, max_height=720, auth, exclude_ids=None, used_sections=None, phrases=None)` →
  (ClipResult|None, reason). Ranks candidates by `subtitle_match*3 + title_score`,
  centres window ~1s before the matched line, respects `used_sections` (no repeats).
- `extract_frames(clip_path, n, out_dir, prefix="frame")` → [paths]. ffmpeg grabs
  N evenly‑spaced stills (the editor‑style on‑topic images).
- `parse_youtube_ref(ref)` → (video_id, start|None, end|None). Handles `?t=`,
  `&t=1m30s`, ranges `1:23-1:30`, `@1:23`.
- `clip_from_reference(ref, keywords, out_path, duration=5, auth, used_sections=None, verify=True, phrases=None)` →
  (ClipResult|None, reason). Verifies the link is downloadable; if it has subs and
  the Spoken Line matches, refines to that exact moment; rejects links whose
  transcript clearly doesn't match (→ caller falls back to search).
- `check_tools()` → {"yt_dlp": version|MISSING, "ffmpeg": path|MISSING} (preflight).
- `ClipResult` dataclass: path, video_id, url, title, start, duration, matched_text, match_score.

================================================================
## MODULE: image_collector.py
================================================================
- `DedupState(urls, md5s, phashes)` — shared across the whole run. `is_dup_bytes()`
  rejects exact (md5) and near‑duplicate (8x8 average perceptual hash, Hamming ≤6).
- `search_images(query, min_width=1280, min_ar=1.4, max_ar=2.2, pool=80)` — uses
  `_ddgs_images` (DuckDuckGo, size=Wallpaper/Large, layout=Wide, 25s timeout + 1
  retry). Filters to landscape + min width; ranks by resolution + closeness to 16:9.
- `collect_images(queries, out_dir, count=4, min_width=1280, ..., name_prefix="image", dedup=None)` →
  [ImageResult]. Pools candidates across all queries, downloads up to `count`
  UNIQUE images; relaxes the resolution floor once if starved.
- `ImageResult`: path, source_url, query, width, height.

================================================================
## MODULE: scene_parser.py (fallback auto‑mode, used when no instructor file)
================================================================
- `parse_script(title, script, sentences_per_scene=1, words_per_scene=None, context=None)` → [Scene].
- `derive_context(title, full_text, max_terms=2)` — builds the topic anchor from
  frequent proper nouns + title (used to anchor instructor subject too).
- `chunk_by_words`, `build_proper_nouns` (filters sentence‑initial caps),
  `extract_entities`, `extract_keywords`. `Scene`: index, text, query, keywords.

================================================================
## ENVIRONMENT & RUN
================================================================
- Install: `pip install -r requirements.txt` + ffmpeg (setup.bat puts it in `bin/`).
- GUI: `python gui.py` (or run.bat). It shells out to `collector.py` and streams logs.
- CLI example:
  `python collector.py --instructor my.txt --context "The Thing 1982" --out out --cookies cookies.txt`
- yt-dlp is invoked as `python -m yt_dlp` (do NOT change to bare "yt-dlp").

================================================================
## EXTENSION POINTS (where to edit for common requests)
================================================================
- **New input field in the instructor file** → add a regex to `_LABELS`, a Beat
  field, handle it in `parse_beats._new()`/`flush()`, use it in `build_queries`
  or pass it through `SceneSpec` in `collector.specs_from_instructor`.
- **Vertical/Shorts (9:16) clips** → `download_section` ffmpeg `-vf` (change
  target_w/target_h + scale/pad), add a `--vertical` flag in `build_arg_parser`.
- **Clip length / counts / frames** → CLI flags `--clip-duration`,
  `--clips-per-scene`, `--frames-per-clip` (already exist).
- **Better clip relevance** → tune `_title_score` keyword lists and the combined
  ranking in `collect_clip` (`kscore*3 + title_score`).
- **Image source change / quality** → `image_collector.search_images` filters and
  `_score`; or add another provider alongside `_ddgs_images`.
- **Direct image URLs from the file** → add an `Image Links:` label + a downloader
  in `collect_images`.
- **Resume/batch long scripts** → `--start-scene` / `--max-scenes` (already exist);
  output is non‑destructive per scene folder.

================================================================
## FRAGILE POINTS (expect occasional upkeep)
================================================================
- YouTube vs yt-dlp: run `update_tools.bat` when clips break ("format not
  available" / bot‑check). Cookies expire → refresh cookies.txt.
- ddgs vs DuckDuckGo: occasional `pip install -U ddgs`.
- Always test changes with `--dry-run`, then `--max-scenes 3` before a full run.
