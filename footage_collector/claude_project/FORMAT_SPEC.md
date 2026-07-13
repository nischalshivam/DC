# FORMAT SPEC — Visual Instructor File (attach this as Project knowledge)

This is the exact format the footage tool parses. Labels are matched
case-insensitively. Lines it READS for searching: `Script Cue (narration):`,
`Visual / Exact Clip to Use:`, `Clip Links:`, `Image Search:`. Lines it IGNORES:
`On-Screen Text:`, `Editor Notes:`.

## Structure
```
TITLE IN CAPS
Topic / context anchor: <Movie Name + Year>

SECTION HEADER (ALL CAPS, no punctuation)
Script Cue (narration): "<exact narration words>"
Visual / Exact Clip to Use: <CAPS SCENE NAME>. "<short quote>". <concrete words>, about <Movie + Year>.
Spoken Line: <exact on-screen dialogue> | <another exact line>             (KEY for clip accuracy)
Image Search: <term one> | <term two> | <term three>                      (recommended)
Image Links: <direct image url .jpg/.png>, <another>                       (optional, downloaded first)
Clip Links: https://youtu.be/<VIDEO_ID>?t=<sec>                            (optional; youtu.be form!)
```

## How each line is used by the tool
| Line | Used for | Notes |
|------|----------|-------|
| `Script Cue (narration):` | famous short quotes (clip search) | exact script words |
| `Visual / Exact Clip to Use:` | clip + image queries | CAPS scene name = strongest signal |
| `Spoken Line:` | **finds exact timestamp** via transcript match | exact dialogue; blank if none |
| `Image Search:` | image queries | `|`-separated; concrete visual terms |
| `Image Links:` | downloaded FIRST (before search) | direct image file URLs; search fills rest |
| `Clip Links:` | tries these exact links FIRST | use `youtu.be/ID?t=sec`; verified; bad → fallback |
| `On-Screen Text:` / `Editor Notes:` | ignored by tool | kept only for a human editor |

## Timestamp formats accepted in Clip Links
- `https://youtu.be/VIDEOID?t=118`  (start at 118s)
- `https://www.youtube.com/watch?v=VIDEOID&t=1m58s`
- `https://youtu.be/VIDEOID 1:23-1:30`  (range)
- `https://youtu.be/VIDEOID @1:23`  (start at 1:23)

## Golden rules
1. Topic anchor MUST include the **year** (disambiguates titles).
2. Visual line ALWAYS starts with a CAPS scene name.
3. Quotes ≤ 6 words.
4. **`Spoken Line:` = exact on-screen dialogue → the tool finds the precise
   timestamp from it. Give it for every dialogue beat (most important field).**
5. Provide `Image Search:` for every beat. Provide `Clip Links:` only when sure.
6. Real-world beats (history/interviews/posters) → search the real subject.
7. Cover the whole script in order; ~1 beat per 1–3 sentences.
