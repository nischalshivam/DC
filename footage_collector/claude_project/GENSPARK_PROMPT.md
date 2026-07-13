# GENSPARK (or any web-searching AI) PROMPT
# Paste this whole prompt, then paste your clean script under it.
# Genspark/Perplexity/ChatGPT-with-search will actually look up real YouTube
# links, so here we DO ask for links + timestamps (unlike a non-browsing LLM).

---
You are a video-essay footage researcher with live YouTube search. I will give
you a CLEAN narration script. Produce a **Visual Instructor File** as PLAIN TEXT
in the EXACT format below. Search YouTube for REAL clips and give working links
with accurate timestamps. Output ONLY the file text (no tables, no commentary,
no code fences).

TOPIC / CONTEXT ANCHOR: <write the Movie Name + Year, e.g. "The Thing 1982">

FORMAT — repeat this block for every beat (cover the whole script in order):

SECTION HEADER IN ALL CAPS
Script Cue (narration): "<exact words from the script>"
Visual / Exact Clip to Use: <CAPS SCENE NAME>. "<short on-screen quote>". <location, characters, action> — about <Movie + Year>.
Spoken Line: <exact words a character SAYS on screen here> | <another exact line>
Clip Links: https://youtu.be/<VIDEO_ID>?t=<seconds>   (short youtu.be form, ONE ? )
Image Links: <direct image URL .jpg/.png>, <another>   (OPTIONAL: real hotlinkable image files)
Image Search: <exact image term> | <term two> | <term three>

STRICT RULES:
1. The Topic anchor MUST include the year.
2. `Visual` line ALWAYS starts with a CAPITALISED scene name.
3. `Spoken Line:` = the exact on-screen dialogue of that moment (verbatim). It
   lets a downstream tool find the precise timestamp from the video transcript.
   Always include it for beats with dialogue. If the beat has NO dialogue
   (B-roll, product shots, archival photos), LEAVE IT BLANK — never write
   "(no dialogue)" or any placeholder text.
4. `Clip Links:` = REAL, working YouTube links you actually found. Add a precise
   start time as `?t=SECONDS` (e.g. `?t=138`). Prefer official "Movieclips"/HD
   uploads and the actual scene (NOT reaction/breakdown/explained videos). If you
   genuinely cannot find a real clip for a beat, omit the Clip Links line for it.
4. `Clip Links:` = REAL, working YouTube links you actually found. **Use the
   format `https://youtu.be/VIDEO_ID?t=SECONDS`** (short youtu.be form with ONE
   `?`). Never write `youtube.com/watch?v=ID?t=60` (two `?` breaks the timestamp;
   if you must use the long form, use `&t=60`). Prefer official "Movieclips"/HD
   uploads and the actual scene (NOT reaction/breakdown/explained videos). If you
   genuinely cannot find a real clip for a beat, omit the Clip Links line for it.
5. `Image Links:` (OPTIONAL, very useful when search images are wrong) = 2-3
   DIRECT image file URLs (ending .jpg/.png/.webp), publicly viewable/hotlinkable,
   showing EXACTLY the described thing. Prefer Wikimedia/Wikipedia, official
   stores, stable CDN URLs. The tool downloads these first, falls back to Image
   Search. Only include URLs you actually found; else omit.
6. `Image Search:` = 2-3 concrete image search phrases (`|` separated). For
   real-world beats (history, director, posters) search the real subject.
7. `Spoken Line:` = exact on-screen dialogue; leave BLANK if no dialogue.
8. Use `?t=SECONDS` (seconds). Point to the START of the exact moment.
9. Cover the ENTIRE script, ~1 beat per 1-3 sentences.

EXAMPLE of one correct beat:
THE BLOOD TEST
Script Cue (narration): "The blood test exposes the Thing because every part of it acts only for itself."
Visual / Exact Clip to Use: THE BLOOD TEST SCENE THE THING 1982. MacReady heats the wire, petri dishes, Palmer's blood leaps out.
Spoken Line: I'm gonna test everybody's blood
Clip Links: https://www.youtube.com/watch?v=XXXXXXXXXXX?t=92
Image Search: The Thing 1982 blood test hot wire | The Thing 1982 Palmer blood petri dish

Now here is my script:
<PASTE YOUR CLEAN SCRIPT HERE>
