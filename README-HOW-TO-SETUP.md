# 🚀 How to Set Up Your Claude Project — "Face-Off Poster Generator"

This package gives you everything to create a Claude Project where you just type
celebrity names and get a ready-to-use image prompt + Facebook caption + hashtags.

- 2 names  → a 2-character (2-panel) prompt
- 3 names  → a 3-character (3-panel) prompt

---

## 📁 What's in this package

```
claude-project-faceoff-poster/
├── CLAUDE-PROJECT-INSTRUCTIONS.md   ← paste this into "Custom Instructions"
├── README-HOW-TO-SETUP.md           ← this file
└── knowledge/                       ← upload all of these to "Project Knowledge"
    ├── 01-PROMPT-MASTER-TEMPLATE.md
    ├── 02-THEME-STYLE-LIBRARY.md
    ├── 03-FONT-AND-COLOR-GUIDE.md
    ├── 04-CAPTION-AND-HASHTAG-GUIDE.md
    └── 05-EXAMPLES.md
```

---

## 🛠️ Step-by-step setup (5 minutes)

1. Go to **claude.ai** → left sidebar → **Projects** → **+ Create Project**.
2. Name it: **"Face-Off Poster Generator"** (or anything you like).
3. Open the project → find **"Set custom instructions"** (or "Instructions").
   - Open `CLAUDE-PROJECT-INSTRUCTIONS.md`, copy ALL of it, and paste it there.
   - Save.
4. Find **"Add content" / "Project knowledge"** (the files area).
   - Upload all 5 files from the `knowledge/` folder.
   - (Tip: you can also copy-paste each file's text as a knowledge doc if upload
     isn't available on your plan.)
5. Done! Your project is ready.

---

## ▶️ How to use it daily

Just open the project and type names. Examples:

- `John Cena & Triple H`
- `John Cena & Triple H & Bill Goldberg`
- `Elon Musk & Mark Zuckerberg`
- `Messi, Ronaldo, Neymar`

Claude will reply with 3 sections:
1. 🎨 IMAGE PROMPT  → copy it into ChatGPT/Gemini/Midjourney image generator.
2. 📝 FACEBOOK CAPTION  → 80–100 words, ready to post.
3. #️⃣ HASHTAGS  → 5–6 tags.

---

## 💡 Pro tips for the BEST images

- Paste the prompt into an image model that follows long prompts well
  (ChatGPT/GPT-4o image or Gemini work great for this style).
- For better face accuracy, also UPLOAD a clear reference photo of each
  celebrity to the image tool and add: "use this exact face."
- If text looks blurry in the result, tell the image tool:
  "make the bottom name text bigger, bolder and perfectly readable."
- If a line/border still appears, tell it:
  "remove the line, blend both sides into one seamless background."
- Always confirm the result is 4:5 — if not, add "strict 4:5 portrait, no cropping."

---

## 🔁 Want a different look?
The instructions tell Claude to VARY the theme every time (gothic, cyberpunk,
fantasy, arena, galaxy, etc.), so your feed stays fresh. If you want a SPECIFIC
theme, just say so, e.g.:
`Messi & Ronaldo — cyberpunk theme`
or
`John Cena & Triple H — gothic horror theme`

Enjoy! 🎉
