# UPDATE LOG — fixes on top of the original handoff (read after 00 + 01)

Newest first. These are hard-won fixes; do NOT regress them.

## 2026-07 — "tool ignores my provided Clip Links" + batch queue

### youtube_clipper.py
1. **Trust explicit timestamps in provided links.** `clip_from_reference` used
   to reject a link whenever the video had subtitles but none of the scene
   keywords appeared in the transcript. Scene keywords describe VISUALS
   ("enters superlab", "hazmat"), which nobody speaks — silent/action beats
   therefore rejected EVERY link. Now the transcript check only gates links
   WITHOUT a `?t=` timestamp; a timestamped link is honoured (the author
   already located the moment). Timestamp-less links still need transcript
   evidence (hallucination guard).
2. **Cross-cue Spoken Line matching.** Subtitle cues are ~2-4s; a
   multi-sentence Spoken Line never fits in one cue, so per-cue substring
   matching silently failed. `_phrase_cue_hits()` searches phrases in the
   concatenated transcript and maps hits back to the starting cue. Used by
   both `clip_from_reference` and `best_timestamp`.
3. **Player-client fallback in `download_section`.** "Requested format is not
   available" is usually YouTube disabling formats for ONE yt-dlp client
   (PO-token/SABR churn), not a bad `-f` string. The download loop now retries
   across clients (`tv, ios, mweb, web_safari, android` — `_CLIENT_FALLBACKS`)
   × the format list, stopping early on terminal errors (private/removed).
   `YtAuth.cookie_args()` exists so cookies can be sent while the client varies.

### instructor_parser.py
4. **Markdown-tolerant parsing.** `_clean_line()` strips `**bold**`, `#`, `-`,
   `1.` etc. before label matching, and the narration/visual labels accept
   common variants (`Narration:`, `Voiceover:`, `Visual Direction:`, …). LLMs
   often emit markdown instructor files, which previously parsed to 0 scenes.
5. **Per-beat "about" anchor.** The Visual line's trailing
   `— about <Movie/Show + Year>` clause (per FORMAT_SPEC) now OVERRIDES the
   global subject for that beat's queries (`_about_anchor`). This makes the
   tool follow the file even when the GUI "Topic" is the essay's own title
   (e.g. topic "Why Gus Fring Killed Victor" but beats say
   `about Breaking Bad "Box Cutter" 2011` / `"Full Measure" 2010`). The clause
   is also REMOVED from signal extraction, so its quoted episode title is no
   longer mistaken for dialogue (it used to become a fake Spoken Line and lock
   timestamps onto random mentions of the title).

### collector.py
6. **0-scene fallback.** If the instructor file parses to zero scenes but a
   clean script was provided, fall back to script auto-mode with a clear
   warning instead of finishing in 0s with nothing.

### gui.py
7. **Batch queue UI.** Build multiple jobs (each with its own title/instructor/
   script/output folder), reorder/edit/remove them, and run them sequentially
   with one click; per-job status (Pending/Running/Done/Failed/Stopped) and a
   shared options panel. `build_cmd()` is a pure function (unit-testable).

### update_ytdlp.bat / update_tools.bat
8. Install `yt-dlp[default]` and print the version; when stable is broken,
   they point to the nightly: `python -m pip install -U --pre "yt-dlp[default]"`.

## 2026-07 (b) — network resets, section reuse, GUI split

### youtube_clipper.py
9. **Transient-network retry + ffmpeg reconnect.** Windows surfaces ffmpeg's
   winsock deaths as "ffmpeg exited with code 4294957242" (= -10054,
   connection reset by YouTube mid-section-download). `download_section` now
   (a) passes `--downloader-args ffmpeg_i:-reconnect 1 -reconnect_streamed 1
   -reconnect_delay_max 5` so ffmpeg survives mid-stream resets, and
   (b) retries the same client+format once after 2s on any transient error
   (`_TRANSIENT_ERRORS`/`_is_transient_error`) before moving to the next
   client. `_err_reason` decodes the huge unsigned codes into plain English.
10. **"section already used" no longer drops provided links.** Instructor
   files legitimately reuse one video across several beats. When a provided
   link's 5s window collides with an earlier scene's, `clip_from_reference`
   nudges forward (+dur, +2dur, +3dur) to adjacent unused footage; if all
   nearby windows are taken it accepts the repeat — a curated link always
   beats the search fallback. Search results (`collect_clip`) still respect
   the strict no-repeat rule.

### gui.py
11. **Resizable queue/progress split.** Queue and Progress now live in a
   vertical `ttk.PanedWindow` — drag the divider to resize. Progress is a
   monospace (Consolas 10) pane that takes ~4/5 of the extra space; the queue
   defaults to 4 rows with its own scrollbar. Window default 1100x950.

## 2026-07 (c) — freeze fix, YouTube rate-limit backoff, last-about anchor

### youtube_clipper.py
12. **Frozen-run fix (supersedes the reconnect args in item 9a).** The ffmpeg
   `-reconnect*` downloader-args are REMOVED: they can make ffmpeg reconnect
   in a loop, and killing yt-dlp on timeout left that orphaned ffmpeg holding
   our stdout pipe — `subprocess.run` then blocked forever and the whole run
   looked frozen on one scene with no error. `_run` is now Popen-based and
   `_kill_tree()` kills the ENTIRE process tree on timeout (Windows:
   `taskkill /F /T`; POSIX: process-group SIGKILL). `download_section` also
   has a hard ~270s budget for its whole client×format matrix, plus
   `--socket-timeout 30 --retries 3`.
13. **Session-wide rate-limit backoff.** YouTube's "Video unavailable ...
   session has been rate-limited for up to an hour" kills every request,
   including good provided links. Detection (`_is_rate_limited`) is checked
   BEFORE the terminal-error check (the message also contains "Video
   unavailable"). On detection the run arms a 10-min pause (`_rl_note`) and
   every network entry point (`download_section`, `search_videos`,
   `_fetch_subtitles`) waits it out via `_rl_gate()` — max 3 pauses per run,
   then fail-fast. All yt-dlp calls now carry `--sleep-requests 0.75` to
   avoid triggering the limiter in the first place.

### instructor_parser.py
14. **Anchor = LAST "about" clause.** `_ABOUT_RE` now uses a greedy prefix so
   a literal mid-sentence "about" ("on the phone about the Albanian deal ...
   — about Rugrats 1991") no longer hijacks half the sentence into the query
   anchor.

### collector.py
15. Liveness logs: "[clip] fetching provided link: ..." / "[clip] searching:
   ..." print BEFORE each network attempt, so a slow download never looks
   like a frozen run.

## 2026-07 (d) — post-rate-limit "no formats" soft-block: fast-fail + missing_pot

### youtube_clipper.py
16. **`formats=missing_pot` on every download attempt.** After a rate-limit,
   YouTube often keeps search working but withholds formats that lack a PO
   token, so every video dies with "Requested format is not available". The
   extractor-args now include `formats=missing_pot` (with and without a
   player_client), letting yt-dlp use those withheld formats when possible.
17. **Session-wide format-block detection.** `_note_fmt_outcome` tracks
   consecutive videos whose ENTIRE client matrix format-failed; at 2 the
   session is considered soft-blocked (`_fmt_blocked`): a one-time [warn] is
   printed with the real fixes (yt-dlp nightly / wait ~1h), download_section
   shrinks to 2 clients x 2 formats with a 90s budget, and collect_clip
   probes only the top 3 candidates and aborts a query after 2 format-failed
   candidates. A blocked scene now costs seconds instead of an hour — this
   was the "20 min stuck on scene 1" report. Any successful download resets
   the streak to 0.
18. **Per-candidate liveness**: collect_clip prints "[try] <title> ..." before
   each candidate download.

## 2026-07 (e) — resume/skip system, start-from-scene UI, more rate-limit stamina

### collector.py
19. **Resume by default.** Before processing a scene, if its folder already
   holds >= clips_per_scene non-empty `clip_*.mp4` files (from an earlier
   run), the scene is skipped with a log line. Re-running the SAME job with
   the SAME output folder therefore only works on scenes that are still
   missing clips — this is the recovery path for laptop-shutdown / net-drop /
   rate-limited-tail runs. `--no-resume` forces a full redo. When clips
   failed, the DONE summary now tells the user to re-run the same job after
   ~1h.

### youtube_clipper.py
20. **More rate-limit stamina.** 6 auto-pauses per run (was 3), pause length
   grows 10 -> 15 -> 20 -> 25 min (capped), and after the FIRST rate-limit of
   a run every yt-dlp call switches from `--sleep-requests 0.75` to `1.5`
   (`_sleep_req_args`). Rationale: a 48-scene run burned all 3 short pauses
   by scene 17 and lost 15 scenes.
21. **ascii-safe candidate prints.** Video titles with exotic characters
   crashed `print()` on Windows cp1252 (UnicodeEncodeError in scene 32 of the
   Candace run); the [try] line now ascii-replaces.

### instructor_parser.py
22. **Anchor junk-dash cleanup.** When the Visual line has a mid-sentence
   "about" and no real "about <Title Year>" clause ("singing about feeling
   the universe against her — Candace Against the Universe 2020"), keep only
   the part after the last dash and reject anchors > 8 words (falls back to
   the global subject).

### gui.py
23. **Start-from-scene + scene auto-detect.** Picking an instructor file
   parses it immediately (`detect_scene_count`, same parser as the collector)
   and shows "total scenes in this file: N"; a "Start from scene" spinbox
   (per job, default 1) passes `--start-scene N`. A shared "Resume" checkbox
   (default ON) controls `--no-resume`.
24. **UTF-8 child process.** collector.py now runs with PYTHONIOENCODING=
   utf-8 / PYTHONUTF8=1 and the GUI reads its output as UTF-8 with
   errors=replace — kills the whole UnicodeEncodeError class.

## 2026-07 (f) — out-of-range provided timestamps (ffmpeg exit -34)

### youtube_clipper.py
25. **Clamp provided timestamps to the real video length.** LLM-written Clip
   Links regularly carry a "?t=" past the video's end (real link, invented
   timestamp) — the requested section came back empty and ffmpeg exited with
   -34 (shown as 4294967262), which the log mislabeled a "network hiccup".
   `clip_from_reference` now estimates length from the last subtitle cue (or
   one cached `_video_duration` metadata call when there are no subs) and,
   when start+dur exceeds it, pulls the window back to the video's tail with
   a `[fix] t=Xs is past the video's end (~Ys) -> using t=Zs` log line.
   `_err_reason` decodes -34 correctly and `_is_transient_error` no longer
   retries it (it can never succeed).

## 2026-07 (g) — persistent queue

### gui.py
26. **Queue survives app close.** The job list is saved to
   `footage_collector/queue.json` on every change (add/edit/remove/reorder/
   status) and restored on startup; jobs that were Running/Stopped/Failed
   when the app died come back as Pending. Combined with the collector's
   per-scene resume, reopening the app and pressing Start Queue continues a
   killed batch exactly where it left off (finished scenes skip in seconds).
   `queue.json` is gitignored (user-local state).
