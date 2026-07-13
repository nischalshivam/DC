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
