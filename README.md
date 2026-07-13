# DC — Data Collector (Footage Collector)

Turns a video-essay script into ready-to-edit footage: for every beat of a
"visual instructor file" it downloads a short **YouTube clip** (verified /
timestamped, normalised to 16:9 1080p), grabs **still frames** from the clip,
and collects **high-res landscape images** — all organised into
`output/scene_NNN/` folders with a `manifest.json`.

## Layout
- **`footage_collector/`** — the tool itself (GUI with batch queue + CLI).
  - Start here: `footage_collector/SETUP_GUIDE.md` (one-time setup) then `run.bat`.
  - Keeping it alive: `footage_collector/MAINTENANCE.md` + `update_tools.bat`.
  - For LLMs making changes: `footage_collector/HANDOFF/` (read `00`, `01`, `02`).
- **`CLAUDE-PROJECT-INSTRUCTIONS.md`**, **`knowledge/`**, **`README-HOW-TO-SETUP.md`** —
  the "brain" side: how to set up the Custom GPT / Gemini Gem / Claude Project
  that writes the visual instructor files this tool consumes.

## Quick start (Windows)
1. `footage_collector/setup.bat` (one time — installs deps + ffmpeg)
2. `footage_collector/run.bat` → add one or more jobs to the queue → **Start Queue**
3. Per-scene folders appear in your chosen output folder.

> Note: `bin/` (ffmpeg) and `output*/` folders are not committed — `setup.bat`
> recreates ffmpeg, and outputs are regenerated per run.
