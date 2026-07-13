# 🎬 Footage Collector — PC Setup Guide (ekdum simple)

Ye guide bilkul beginner ke liye hai. Aapko coding aani zaroori nahi.
Tool aapki script + visual instructor file se har scene ke liye **YouTube clips
(cropped, 16:9)** aur **high-res images** download karke folders mein daal deta hai.

> **GUI app banega ya command line?**
> Aapke liye ek **simple app window (GUI)** ban gayi hai. Aapko terminal/command
> kuch nahi chalani — bas `run.bat` double-click karo, ek window khulegi, file
> daalo, button dabao. Command line sirf backup ke liye hai (neeche diya hai).

---

## Kya-kya chahiye (ek baar ka setup)
1. **Python 3.10+** (free)
2. Internet connection
3. Wahi browser jisme aap **YouTube pe logged-in** ho (Chrome/Edge/Firefox) — clips ke liye

---

## STEP 1 — Tool download karo
1. Repo kholo: `https://github.com/priyankaanischal-creator/claude`
2. Branch `add-footage-collector` select karo (ya PR merge ke baad `main`).
3. Green **"Code"** button → **"Download ZIP"**.
4. ZIP ko apne PC pe extract karo. Andar `footage_collector` folder milega — bas usi ke andar kaam hoga.

---

## STEP 2 — Python install karo (agar nahi hai)
1. `https://www.python.org/downloads/` kholo → **Download Python** dabao.
2. Installer chalao. ⚠️ **SABSE ZAROORI:** pehli screen pe **"Add python.exe to PATH"** wala checkbox **TICK** karo, phir "Install Now".
3. Install hone do.

> Check karne ke liye: Start menu me "cmd" type karke Command Prompt kholo,
> `python --version` likho. Agar version dikhe (jaise `Python 3.12.x`) to ho gaya.

---

## STEP 3 — One-time setup (ffmpeg + packages)
Folder `footage_collector` ke andar:

- **Windows:** `setup.bat` pe **double-click** karo.
  - Ye khud Python packages install karega aur **ffmpeg** download karke `bin\` folder me daal dega.
  - "Ho gaya!" dikhe to band kar do.
- **Mac/Linux:** Terminal me folder kholo aur chalao:
  ```
  bash setup.sh
  ```
  (Mac pe ffmpeg ke liye: `brew install ffmpeg` | Ubuntu: `sudo apt install ffmpeg python3-tk`)

> Ye step **sirf ek baar** karna hai.

---

## STEP 4 — App kholo aur footage banao
- **Windows:** `run.bat` pe **double-click** → app window khulegi.
- **Mac/Linux:** `bash run.sh`

App window me:
1. **Video title** — apni video ka title (optional).
2. **Topic / context** — sabse important! Jaise `The Thing 1982` ya `Scarface 1983`. Isse saare results topic se related rehte hain.
3. **Visual instructor file** — "Browse…" se apni instructor `.txt` file choose karo.
4. **Clean script (optional)** — apni original script `.txt` (chaaho to).
5. **Output folder** — kahan save karna hai (default `output`).
6. **Options:**
   - Clips / scene → kitni clips (default 2)
   - Images / scene → kitni images (default 4)
   - Clip length → 5 second (recommended)
   - **YouTube login** → wo browser choose karo jisme aap YouTube pe logged-in ho (clips ke liye zaroori, neeche dekho).
7. **▶ Generate Footage** dabao. Progress neeche window me dikhega.
8. Khatam hone pe **"Open output folder"** se folders dekho.

---

## STEP 5 — Clips ke liye "cookies" (SABSE ZAROORI step)

YouTube datacenter/anjaan jagah se download block karta hai
("Sign in to confirm you're not a bot"). Iska ek hi solution hai: YouTube ko
apni **login (cookies)** do. 2 tareeke hain — **Method A recommended hai**.

### ✅ Method A — cookies.txt file (sabse reliable, har browser pe chalti hai)
Naya Chrome cookies ko encrypt karta hai, isliye seedha browser-read aksar fail
hota hai. cookies.txt file is problem ko poori tarah bypass kar deti hai.

1. Chrome/Edge me ye free extension install karo: **"Get cookies.txt LOCALLY"**
   (Chrome Web Store me search karo).
2. `https://www.youtube.com` kholo aur **logged-in** raho.
3. Extension icon dabao → **Export** / "Export As" → ek `cookies.txt` file save hogi
   (jaise `Downloads\cookies.txt`).
4. App me **"OR cookies.txt file"** field me wahi file Browse karke choose karo.
5. Generate dabao. Bas! Clips download honi chahiye.

> cookies.txt ek private file hai (aapki login). Kisi ke saath share mat karna.

### Method B — browser se direct (try kar sakte ho, par kam reliable)
1. App me **YouTube login** dropdown me browser choose karo (jaise `firefox`).
2. ⚠️ Wo browser **poori tarah BAND** karo (Chrome khula ho to cookies lock ho jati hain).
3. **Firefox** is method me Chrome se zyada reliable hai.

> Agar Method B pe phir bhi "Sign in to confirm you're not a bot" aaye, to
> Method A (cookies.txt) use karo — wo pakka kaam karega.

> **Images ke liye cookies ki zaroorat NAHI** — wo waise bhi download ho jaati hain.

---

## Output kaisa milega
```
output/
  manifest.json              <- saari scenes ki list + queries + sources
  scene_001/
    scene.txt                <- is scene ka narration + queries (+ notes)
    clip_01.mp4              <- 5 sec, 16:9, 1080p
    clip_02.mp4
    image_01.jpg             <- high-res, landscape
    image_02.jpg ...
  scene_002/
  ...
```
Har scene ka apna folder — editing ke time ready "visual buffet".

---

## ❓ Common problems (troubleshooting)

| Problem | Fix |
|--------|-----|
| "Python nahi mila" / 'python' is not recognized | Python install nahi hua ya PATH tick nahi kiya. Step 2 dobara, PATH tick zaroor karo. |
| setup.bat me ffmpeg download fail | Internet check karo. Ya manual: ffmpeg Windows build download karke `ffmpeg.exe` + `ffprobe.exe` ko `footage_collector\bin\` me daal do. |
| Clips: "Requested format is not available" | yt-dlp purana hai (YouTube ne system badla). **`update_tools.bat` double-click karo** (ya `python -m pip install -U yt-dlp`), phir dobara chalao. |
| Clips download nahi ho rahi, "Sign in to confirm you're not a bot" | **cookies.txt file use karo (Method A, Step 5)** — ye pakka kaam karta hai. Browser-method aksar naye Chrome pe fail hota hai. |
| "could not copy chrome cookie database" / "Permission denied" | Chrome khula hai ya encrypted cookies. Chrome band karo, ya behtar: **cookies.txt file** (Method A) use karo. |
| Images aa rahi par clips nahi | Normal — sabse pehle YouTube login wala step set karo. Images bina login ke aati hain. |
| App window khulti hi nahi (Linux) | `sudo apt install python3-tk` chalao. |

---

## 💻 Command-line tareeka (backup, agar GUI na chahe)
Folder ke andar terminal/cmd me:
```bash
# ek baar:
pip install -r requirements.txt      # + ffmpeg installed/bin me ho

# footage banao:
python collector.py ^
  --instructor scripts/the_thing_visual_instructor.txt ^
  --script scripts/the_thing.txt ^
  --context "The Thing 1982" ^
  --title "WHAT THE THING'S ENDING REALLY MEANS" ^
  --out output ^
  --clips-per-scene 2 --images-per-scene 4 --clip-duration 5 ^
  --cookies "C:/Users/Dell/Downloads/cookies.txt"
```
(Windows me `^` line-continuation hai; Mac/Linux me `\` use karo.)
`--cookies <file>` sabse reliable hai. Browser-direct chahiye to uski jagah
`--cookies-from-browser firefox` use karo (browser band rakho).

Sirf images chahiye to `--clips-per-scene 0` aur `--cookies-from-browser` hata do.

---

## Image sources (NEW — better images, esp. for documentaries)
The tool can pull images from multiple sources and keep the best:
- **ddg** (DuckDuckGo) + **wikimedia** (real people/places/history) = default, keyless.
- **openverse** (Creative-Commons) = keyless, add it for more.
- **pexels** / **pixabay** = generic stock B-roll; need a FREE API key.

In the app, pick from the **Image sources** dropdown. On the command line:
`--image-sources ddg,wikimedia,openverse`

To enable Pexels/Pixabay, get a free key and set it before running:
- Windows (cmd): `set PEXELS_API_KEY=yourkey` then run, or `set PIXABAY_API_KEY=yourkey`
- Then add them: `--image-sources ddg,wikimedia,pexels,pixabay`

> For documentary/biography videos, **wikimedia** is the most valuable (real
> subjects, legal, hotlinkable). For movie scene stills, ddg + clip frames win.

## Naye video ke liye kya karna hai (har baar)
1. Claude/Gemini se us script ki **visual instructor file** banwao (CAPS scene-name +
   dialogue quotes + concrete words, sab topic se related — example ke liye
   `scripts/the_thing_visual_instructor.txt` dekho).
2. App kholo → instructor file + script daalo → topic likho → Generate dabao.
3. Folders ready! 🎉

---

## 🔝 Advanced: exact clip links + image search (highest accuracy)
Har beat me 2 optional lines add kar sakte ho. Tool inhe samajh kar use karega:

```
Script Cue (narration): "..."
Visual / Exact Clip to Use: THE BLOOD TEST SCENE. MacReady heats the wire.
Clip Links: https://youtu.be/Esy-776wcIo?t=118 , https://youtu.be/M2o2FRwn_hg
Image Search: macready blood test closeup | petri dish blood hot wire
```

- **Clip Links:** us scene ke exact YouTube links (timestamp `?t=118` ya range
  `1:23-1:30` ke saath bhi). Tool pehle inhe try karega aur **verify** karega
  (video chalti hai? transcript scene se match karta hai?). Sahi hua → wahi se
  clip. Galat/dead link → automatically purana search system. (LLMs kabhi-kabhi
  galat link bana dete hain, isliye verify zaroori hai — tool khud handle karta hai.)
- **Image Search:** us scene ke liye exact image search terms (`|` se alag karo).
  Tool inhe priority dega.

> Dono lines **optional** hain. Na do to tool waise hi (scene-name se) kaam karega.

### LLM ko file banwane ke liye prompt (copy-paste)
> "Is script ki beat-by-beat VISUAL INSTRUCTOR file banao. Har beat me 4 lines:
> (1) `Script Cue (narration):` exact narration. (2) `Visual / Exact Clip to Use:`
> shuruaat me CAPS me exact scene ka naam, phir quotes me famous dialogue, phir
> concrete location/character/action words — sab **[MOVIE NAME + YEAR]** se related.
> (3) `Clip Links:` us scene ke 2-3 real YouTube links agar pakka maloom ho
> (timestamp ke saath), warna ye line chhod do. (4) `Image Search:` us scene ke
> 2-3 exact image search terms. Topic anchor: **[MOVIE NAME + YEAR]**."
