# How to set up the "Visual Instructor File Generator" Claude Project

A one-time setup. After this, you just paste a script and get a ready
visual instructor file.

## Steps
1. Go to **claude.ai** → left sidebar → **Projects** → **Create Project**.
2. Name it e.g. **"Footage / Visual Instructor Generator"**.
3. Open the project → find **"Set instructions"** (or "Custom instructions").
   Paste the ENTIRE contents of **PROJECT_INSTRUCTIONS.md** there. Save.
4. In the project, add **Project knowledge** (the "Add content" / paperclip area)
   and upload these two files:
   - **FORMAT_SPEC.md**
   - **EXAMPLE_The_Thing_visual_instructor.txt**
5. Done. The project is ready.

## How to use it (every video)
1. Open a new chat inside the project.
2. Paste your **clean narration script**. Optionally add one line:
   `Topic: <Movie Name + Year>` (e.g. `Topic: Heat 1995`). If you skip it,
   Claude will infer the topic.
3. Claude returns the full **Visual Instructor File** text.
4. Copy it → save as a `.txt` file (e.g. `my_video_visual_instructor.txt`).
5. Open the footage tool (run.bat) → pick that `.txt` as the
   **Visual instructor file** → set the **Topic** (same Movie + Year) →
   Generate.

## Tips for best results
- Give Claude the cleanest script you can (the actual narration).
- If a beat's clip comes out weak later, edit that beat's
  `Visual / Exact Clip to Use:` line to use a sharper CAPS scene name, or add a
  real `Clip Links:` line, then re-run the tool.
- Claude may not know real YouTube links reliably; that's fine — the strong
  scene names + `Spoken Line:` (exact dialogue) + Image Search terms are the
  reliable backbone, and the tool searches + verifies anyway.

## BEST for real YouTube links: use a web-searching AI (Genspark / Perplexity / ChatGPT-with-search)
A normal Claude Project cannot browse YouTube, so it relies on `Spoken Line:`.
But tools that actually search the web (e.g. **Genspark**) can return REAL links
with timestamps. To use that route:
1. Open **GENSPARK_PROMPT.md**, copy the whole prompt.
2. Paste it into Genspark, fill the Topic line, and paste your clean script.
3. It returns the visual instructor file WITH real `Clip Links:` + timestamps.
4. Save as `.txt` and run it in the tool exactly the same way.

The tool verifies every provided link and, using your `Spoken Line:`, refines to
the exact moment inside it — and silently falls back to search for any bad link.
So mixing Genspark links + Spoken Line gives the highest accuracy.

