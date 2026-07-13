# HANDOFF — how to use these files

You have a complete record of this project. Two ways to use it later:

## To make changes / add features (give it to an LLM)
1. Open a new chat with Claude / ChatGPT / Gemini.
2. Attach (or paste) BOTH:
   - `00_PROJECT_HANDOFF.md`  (the full story, needs, decisions, workflow, limits)
   - `01_TECHNICAL_REFERENCE.md`  (the code map + extension points)
3. If the change touches code, also attach the specific file(s) it mentions
   (e.g. `youtube_clipper.py`, `collector.py`, `instructor_parser.py`).
4. Tell it what you want, e.g.:
   - "Add a 9:16 vertical mode for Shorts."
   - "Make clips 8 seconds and grab 3 frames each."
   - "Support an `Image Links:` line with direct image URLs."
5. Ask it to test with `--dry-run`, then a small `--max-scenes 3` run.

> Even better: if you keep the project on GitHub, just give the LLM the repo link
> plus these two files — it will have full context.

## To fix a bug
Paste the FULL error/traceback + say what you were doing. The LLM will use the
TECHNICAL REFERENCE to locate the function and fix it.

## To regenerate footage (normal use)
See `../SETUP_GUIDE.md` (setup + GUI) and `../claude_project/` (how to make the
visual instructor file with a Custom GPT / Gemini Gem / Genspark).

## To keep it working long‑term
See `../MAINTENANCE.md`. Short version: when clips/images break, run
`../update_tools.bat` and refresh your `cookies.txt`.

## File map (what to read first)
1. `00_PROJECT_HANDOFF.md`  — start here (the whole picture).
2. `01_TECHNICAL_REFERENCE.md` — the code, for making changes.
3. `../SETUP_GUIDE.md`, `../MAINTENANCE.md`, `../claude_project/*` — usage & upkeep.
