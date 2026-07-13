# MAINTENANCE — keeping the tool working long-term (honest guide)

## What is stable vs what needs occasional care

| Part | Stability | Action |
|------|-----------|--------|
| The tool's own code (parsing, cropping, dedup, frames) | ✅ Stable, won't break on its own | none |
| **yt-dlp ↔ YouTube** | ⚠️ YouTube changes every 1–2 months and breaks yt-dlp | run **`update_tools.bat`** |
| **ddgs ↔ DuckDuckGo** (image search) | ⚠️ occasionally changes | run **`update_tools.bat`** |
| ffmpeg | ✅ Very stable | rarely needed |

> This is normal for ANY tool that pulls from YouTube — not a flaw in this tool.
> Big creators' pipelines do the same thing.

## The one habit that fixes ~90% of future problems
When clips suddenly stop downloading, or you see
"Requested format is not available" / "Sign in to confirm you're not a bot" again:
1. Double-click **`update_tools.bat`** (updates yt-dlp + image search).
2. Refresh your **cookies.txt** (re-export from the browser — logins expire).
3. Run again.

## Common symptoms → fix
| Symptom | Fix |
|---------|-----|
| Clips fail: "Requested format is not available" | `update_tools.bat` (yt-dlp is stale) |
| Clips fail: "Sign in to confirm you're not a bot" | refresh **cookies.txt** (Step 5 in SETUP_GUIDE) |
| Images: many "operation timed out" | slow network / DuckDuckGo rate-limit; re-run, or run later |
| "ffmpeg MISSING" at startup | run `setup.bat` in this folder (puts ffmpeg in `bin\`) |
| A real code bug / crash with a traceback | see "If a real bug appears" below |

## Long / heavy scripts (e.g. 1-hour documentaries)
A long script makes many beats → long run time + many downloads. Options:
- Run in **batches**: `--start-scene 1 --max-scenes 20`, then `--start-scene 21 --max-scenes 20`, etc.
- Lower per-scene counts: `--clips-per-scene 1 --images-per-scene 2`.
- The output folder is resumable: already-made scene folders stay; you can re-run
  remaining scenes with `--start-scene N`.

## If a real bug appears (a crash / traceback)
Everything lives in your GitHub repo, so it's fixable forever:
1. Copy the FULL error text from the window (the Python traceback).
2. Paste it to Claude / ChatGPT / Gemini along with the file it mentions
   (e.g. `youtube_clipper.py`) and say what you were doing.
3. Apply the fix (replace the file), re-run. (This is exactly how we built it.)

## Keeping things fresh (optional, every month or so)
- Run `update_tools.bat` once a month even if nothing's broken.
- If you cloned via git, `git pull` for any improvements; otherwise re-download
  the ZIP occasionally.

## Quick health check
Run any generate with clips on — the startup prints:
```
  yt-dlp : <version>
  ffmpeg : <path>
```
If both show real values, the engine is healthy.
