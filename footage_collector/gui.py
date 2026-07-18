#!/usr/bin/env python3
"""
gui.py  --  Footage Collector (desktop app, with a BATCH QUEUE)
===============================================================
A no-terminal window for the footage collector.

Two ways to use it:
  1. Single job  -> fill the form on top, click "Add to Queue", then "Start Queue".
  2. Batch (NEW) -> add several jobs (each with its own title / instructor file /
     script / output folder), then click "Start Queue" once. The tool runs them
     one after another automatically: job 1 finishes -> job 2 starts -> ...

Shared options (clips per scene, cookies, etc.) apply to every job in the queue.

Run it with:   python gui.py     (or double-click run.bat on Windows)
Tkinter ships with Python, so no extra install is needed for the window itself.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(HERE, "queue.json")


def save_queue_file(jobs: list, path: str = QUEUE_FILE) -> None:
    """Persist the queue so closing the app / shutting the laptop doesn't
    lose it. Best-effort: a failed save never breaks the UI."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def load_queue_file(path: str = QUEUE_FILE) -> list:
    """Load a previously saved queue. Jobs that were mid-run when the app
    died come back as Pending so Start Queue picks them up again (the
    collector's per-scene resume skips whatever they already finished)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        out = []
        for j in jobs:
            if isinstance(j, dict) and j.get("instructor"):
                if j.get("status") in ("Running", "Stopped", "Failed"):
                    j["status"] = "Pending"
                j.setdefault("status", "Pending")
                out.append(j)
        return out
    except Exception:
        return []

IMAGE_SOURCE_CHOICES = [
    "ddg,wikimedia", "ddg,wikimedia,openverse", "ddg", "wikimedia",
    "ddg,wikimedia,openverse,pexels,pixabay",
]
COOKIE_BROWSER_CHOICES = ["none", "chrome", "edge", "firefox", "brave", "opera"]


def build_cmd(job: dict, opts: dict) -> list:
    """Turn one queued job + the shared options into a collector.py command.
    Kept as a plain function (no Tk) so it can be unit-tested on its own."""
    out = job.get("out", "").strip() or os.path.join(HERE, "output")
    cmd = [
        sys.executable, os.path.join(HERE, "collector.py"),
        "--instructor", job["instructor"],
        "--out", out,
        "--clips-per-scene", str(opts["clips"]),
        "--images-per-scene", str(opts["images"]),
        "--clip-duration", str(opts["dur"]),
        "--frames-per-clip", str(opts["frames"]),
        "--image-sources", opts["sources"],
    ]
    if job.get("script", "").strip():
        cmd += ["--script", job["script"].strip()]
    if job.get("context", "").strip():
        cmd += ["--context", job["context"].strip()]
    if job.get("title", "").strip():
        cmd += ["--title", job["title"].strip()]
    try:
        start_scene = int(job.get("start_scene", 1) or 1)
    except (TypeError, ValueError):
        start_scene = 1
    if start_scene > 1:
        cmd += ["--start-scene", str(start_scene)]
    if not opts.get("resume", True):
        cmd += ["--no-resume"]
    if opts.get("cookies_file", "").strip():
        cmd += ["--cookies", opts["cookies_file"].strip()]
    elif opts.get("cookies_browser", "none") != "none":
        cmd += ["--cookies-from-browser", opts["cookies_browser"]]
    return cmd


def detect_scene_count(instructor_path: str):
    """How many scenes the tool will create for this instructor file.
    Returns int or None. Uses the same parser as collector.py, so the number
    always matches the real run."""
    try:
        import instructor_parser as ip
        with open(instructor_path, "r", encoding="utf-8", errors="ignore") as f:
            return len(ip.parse_beats(f.read()))
    except Exception:
        return None


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Footage Collector — Batch Queue")
        root.geometry("1100x950")
        root.minsize(900, 760)

        self.proc = None                       # currently running subprocess
        self.jobs: list[dict] = []             # the queue (list of job dicts)
        self.row_ids: list[str] = []           # Treeview iids, parallel to self.jobs
        self.running = False
        self.stop_flag = threading.Event()
        self.log_q: "queue.Queue[str]" = queue.Queue()

        pad = {"padx": 8, "pady": 4}
        outer = ttk.Frame(root, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        # ---------- SECTION 1: build a job ----------
        form = ttk.LabelFrame(outer, text="1)  Build a job", padding=8)
        form.grid(row=0, column=0, sticky="we")
        form.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(form, text="Video title").grid(row=r, column=0, sticky="w", **pad)
        self.title_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.title_var).grid(row=r, column=1, columnspan=2, sticky="we", **pad)

        r += 1
        ttk.Label(form, text="Topic / context\n(SHOW/MOVIE + year,\ne.g. Breaking Bad 2011)").grid(row=r, column=0, sticky="w", **pad)
        self.context_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.context_var).grid(row=r, column=1, columnspan=2, sticky="we", **pad)

        r += 1
        ttk.Label(form, text="Visual instructor file").grid(row=r, column=0, sticky="w", **pad)
        self.instructor_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.instructor_var).grid(row=r, column=1, sticky="we", **pad)
        ttk.Button(form, text="Browse…", command=lambda: self._pick(self.instructor_var)).grid(row=r, column=2, **pad)

        # scene auto-detect + start-from-scene (resume a killed/partial run)
        r += 1
        ttk.Label(form, text="Start from scene").grid(row=r, column=0, sticky="w", **pad)
        srow = ttk.Frame(form)
        srow.grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        self.start_scene_var = tk.IntVar(value=1)
        self.start_scene_spin = ttk.Spinbox(srow, from_=1, to=999, width=6,
                                            textvariable=self.start_scene_var)
        self.start_scene_spin.pack(side="left")
        self.scenes_lbl = ttk.Label(srow, text="(instructor file chuno — total scenes yahan dikhenge)")
        self.scenes_lbl.pack(side="left", padx=10)
        self.instructor_var.trace_add("write", self._update_scene_count)

        r += 1
        ttk.Label(form, text="Clean script (optional)").grid(row=r, column=0, sticky="w", **pad)
        self.script_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.script_var).grid(row=r, column=1, sticky="we", **pad)
        ttk.Button(form, text="Browse…", command=lambda: self._pick(self.script_var)).grid(row=r, column=2, **pad)

        r += 1
        ttk.Label(form, text="Output folder").grid(row=r, column=0, sticky="w", **pad)
        self.out_var = tk.StringVar(value=os.path.join(HERE, "output"))
        ttk.Entry(form, textvariable=self.out_var).grid(row=r, column=1, sticky="we", **pad)
        ttk.Button(form, text="Browse…", command=lambda: self._pick_dir(self.out_var)).grid(row=r, column=2, **pad)

        r += 1
        jobbtns = ttk.Frame(form)
        jobbtns.grid(row=r, column=0, columnspan=3, sticky="we", **pad)
        ttk.Button(jobbtns, text="➕  Add to Queue", command=self.add_job).pack(side="left", padx=3)
        ttk.Button(jobbtns, text="✏  Update selected", command=self.update_job).pack(side="left", padx=3)
        ttk.Button(jobbtns, text="Clear form", command=self.clear_form).pack(side="left", padx=3)
        ttk.Label(jobbtns, text="(tip: queue me row par double-click karke usse edit ke liye load karo)").pack(
            side="left", padx=10)

        # ---------- resizable split: queue (top) / progress (bottom) ----------
        # A vertical PanedWindow so the user can DRAG the divider between the
        # queue and the progress log — the log gets most of the space by
        # default and grows with the window.
        self.paned = ttk.PanedWindow(outer, orient="vertical")
        self.paned.grid(row=3, column=0, sticky="nsew", pady=(10, 0))

        # ---------- SECTION 3: the queue ----------
        qframe = ttk.LabelFrame(self.paned, text="3)  Queue  (jobs ek-ek karke chalenge — border kheench ke chota/bada karo)", padding=8)
        self.paned.add(qframe, weight=1)
        qframe.columnconfigure(0, weight=1)
        qframe.rowconfigure(0, weight=1)

        cols = ("num", "title", "out", "status")
        self.tree = ttk.Treeview(qframe, columns=cols, show="headings", height=4, selectmode="browse")
        self.tree.heading("num", text="#")
        self.tree.heading("title", text="Title")
        self.tree.heading("out", text="Output folder")
        self.tree.heading("status", text="Status")
        self.tree.column("num", width=36, anchor="center", stretch=False)
        self.tree.column("title", width=300)
        self.tree.column("out", width=340)
        self.tree.column("status", width=110, anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(qframe, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.bind("<Double-1>", self._load_selected_into_form)

        # status colours
        self.tree.tag_configure("Pending", foreground="#555555")
        self.tree.tag_configure("Running", foreground="#0a58ca")
        self.tree.tag_configure("Done", foreground="#198754")
        self.tree.tag_configure("Failed", foreground="#dc3545")
        self.tree.tag_configure("Stopped", foreground="#b8860b")

        qbtns = ttk.Frame(qframe)
        qbtns.grid(row=1, column=0, columnspan=2, sticky="we", pady=(6, 0))
        ttk.Button(qbtns, text="↑ Up", command=lambda: self._move(-1)).pack(side="left", padx=3)
        ttk.Button(qbtns, text="↓ Down", command=lambda: self._move(1)).pack(side="left", padx=3)
        ttk.Button(qbtns, text="🗑 Remove", command=self.remove_job).pack(side="left", padx=3)
        ttk.Button(qbtns, text="Clear queue", command=self.clear_queue).pack(side="left", padx=3)
        self.count_lbl = ttk.Label(qbtns, text="0 job(s)")
        self.count_lbl.pack(side="right", padx=6)

        # ---------- SECTION 2: shared options ----------
        opt = ttk.LabelFrame(outer, text="2)  Shared options  (poori queue par apply honge)", padding=8)
        opt.grid(row=1, column=0, sticky="we", pady=(10, 0))

        ttk.Label(opt, text="Clips / scene").grid(row=0, column=0, sticky="w", padx=6)
        self.clips_var = tk.IntVar(value=2)
        ttk.Spinbox(opt, from_=0, to=5, width=5, textvariable=self.clips_var).grid(row=0, column=1, padx=6)
        ttk.Label(opt, text="Images / scene").grid(row=0, column=2, sticky="w", padx=6)
        self.images_var = tk.IntVar(value=4)
        ttk.Spinbox(opt, from_=0, to=10, width=5, textvariable=self.images_var).grid(row=0, column=3, padx=6)
        ttk.Label(opt, text="Clip length (sec)").grid(row=0, column=4, sticky="w", padx=6)
        self.dur_var = tk.IntVar(value=5)
        ttk.Spinbox(opt, from_=3, to=10, width=5, textvariable=self.dur_var).grid(row=0, column=5, padx=6)
        ttk.Label(opt, text="Frames / clip").grid(row=0, column=6, sticky="w", padx=6)
        self.frames_var = tk.IntVar(value=2)
        ttk.Spinbox(opt, from_=0, to=6, width=5, textvariable=self.frames_var).grid(row=0, column=7, padx=6)

        ttk.Label(opt, text="YouTube login (for clips)").grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=6)
        self.cookies_var = tk.StringVar(value="none")
        ttk.Combobox(opt, textvariable=self.cookies_var, width=12, state="readonly",
                     values=COOKIE_BROWSER_CHOICES).grid(row=1, column=2, padx=6, pady=6)
        ttk.Label(opt, text="(browser jisme YouTube logged-in ho; us browser ko BAND rakho)").grid(
            row=1, column=3, columnspan=5, sticky="w", padx=6)

        ttk.Label(opt, text="OR cookies.txt file\n(most reliable)").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6, pady=6)
        self.cookies_file_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.cookies_file_var, width=34).grid(
            row=2, column=2, columnspan=3, padx=6, pady=6, sticky="we")
        ttk.Button(opt, text="Browse…", command=lambda: self._pick(self.cookies_file_var)).grid(row=2, column=5, padx=6)
        ttk.Label(opt, text="Image sources").grid(row=2, column=6, sticky="w", padx=6)
        self.sources_var = tk.StringVar(value="ddg,wikimedia")
        ttk.Combobox(opt, textvariable=self.sources_var, width=20, state="readonly",
                     values=IMAGE_SOURCE_CHOICES).grid(row=3, column=6, columnspan=2, padx=6, sticky="w")

        self.resume_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt, variable=self.resume_var,
            text="Resume: jin scenes ke clips pehle se output folder me hain unhe skip karo "
                 "(failed/adhura run dobara chalane par sirf bache hue scenes hote hain)"
        ).grid(row=3, column=0, columnspan=6, sticky="w", padx=6, pady=(6, 0))

        # ---------- SECTION 4: run controls ----------
        run = ttk.Frame(outer)
        run.grid(row=2, column=0, sticky="we", pady=(10, 0))
        self.run_btn = ttk.Button(run, text="▶  Start Queue", command=self.start_queue)
        self.run_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(run, text="■ Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        ttk.Button(run, text="Open output folder", command=self.open_output).pack(side="left", padx=4)

        # ---------- progress log (big, monospace, gets all extra space) ----------
        logf = ttk.LabelFrame(self.paned, text="Progress", padding=(4, 2))
        self.paned.add(logf, weight=4)
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        self.log = scrolledtext.ScrolledText(
            logf, height=18, wrap="word", state="disabled",
            font=("Consolas", 10))
        self.log.grid(row=0, column=0, sticky="nsew")
        # only the paned area (queue + progress) grows with the window
        outer.rowconfigure(3, weight=1)

        # restore the queue from the last session (jobs survive app close /
        # laptop shutdown; mid-run jobs come back as Pending)
        restored = load_queue_file()
        if restored:
            self.jobs = restored
            self._refresh_tree()
            self._append(f"[queue] {len(restored)} saved job(s) restored from last session. "
                         "Start Queue dabate hi ye wahin se continue karenge (done scenes skip).\n")

        self.root.after(100, self._drain_log)

    # ---------------- form <-> job helpers ----------------
    def _update_scene_count(self, *_args):
        path = self.instructor_var.get().strip()
        if path and os.path.isfile(path):
            n = detect_scene_count(path)
            if n:
                self.scenes_lbl.configure(text=f"total scenes in this file: {n}")
                self.start_scene_spin.configure(to=max(n, 1))
                return
        self.scenes_lbl.configure(text="(instructor file chuno — total scenes yahan dikhenge)")

    def _form_to_job(self) -> dict:
        try:
            start_scene = max(1, int(self.start_scene_var.get()))
        except Exception:
            start_scene = 1
        return {
            "title": self.title_var.get().strip(),
            "context": self.context_var.get().strip(),
            "instructor": self.instructor_var.get().strip(),
            "script": self.script_var.get().strip(),
            "out": self.out_var.get().strip(),
            "start_scene": start_scene,
            "status": "Pending",
        }

    def _job_to_form(self, job: dict):
        self.title_var.set(job.get("title", ""))
        self.context_var.set(job.get("context", ""))
        self.instructor_var.set(job.get("instructor", ""))
        self.script_var.set(job.get("script", ""))
        self.out_var.set(job.get("out", ""))
        self.start_scene_var.set(job.get("start_scene", 1))

    def _valid_job(self, job: dict) -> bool:
        if not job["instructor"] or not os.path.isfile(job["instructor"]):
            messagebox.showerror("Missing file", "Please pick a valid visual instructor file.")
            return False
        return True

    def clear_form(self):
        for v in (self.title_var, self.context_var, self.instructor_var, self.script_var):
            v.set("")
        self.out_var.set(os.path.join(HERE, "output"))
        self.start_scene_var.set(1)

    def add_job(self):
        job = self._form_to_job()
        if not self._valid_job(job):
            return
        self.jobs.append(job)
        self._refresh_tree()
        self.clear_form()

    def update_job(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("No selection", "Queue me ek job select karo, phir 'Update selected' dabao.")
            return
        job = self._form_to_job()
        if not self._valid_job(job):
            return
        job["status"] = self.jobs[idx].get("status", "Pending")
        self.jobs[idx] = job
        self._refresh_tree()

    def remove_job(self):
        idx = self._selected_index()
        if idx is None:
            return
        if self.running and self.jobs[idx].get("status") == "Running":
            messagebox.showinfo("Running", "Ye job abhi chal raha hai; pehle Stop karo.")
            return
        del self.jobs[idx]
        self._refresh_tree()

    def clear_queue(self):
        if self.running:
            messagebox.showinfo("Running", "Queue chal rahi hai; pehle Stop karo.")
            return
        self.jobs.clear()
        self._refresh_tree()

    def _move(self, delta: int):
        idx = self._selected_index()
        if idx is None:
            return
        j = idx + delta
        if j < 0 or j >= len(self.jobs):
            return
        self.jobs[idx], self.jobs[j] = self.jobs[j], self.jobs[idx]
        self._refresh_tree()
        if 0 <= j < len(self.row_ids):
            self.tree.selection_set(self.row_ids[j])

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return self.row_ids.index(sel[0])
        except ValueError:
            return None

    def _load_selected_into_form(self, _event=None):
        idx = self._selected_index()
        if idx is not None:
            self._job_to_form(self.jobs[idx])

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.row_ids = []
        for i, job in enumerate(self.jobs, 1):
            st = job.get("status", "Pending")
            iid = self.tree.insert(
                "", "end",
                values=(i, job.get("title") or "(no title)", job.get("out", ""), st),
                tags=(st,))
            self.row_ids.append(iid)
        self.count_lbl.configure(text=f"{len(self.jobs)} job(s)")
        save_queue_file(self.jobs)

    def _set_status(self, idx: int, status: str):
        """Thread-safe: schedule a status update on the Tk main thread."""
        def _apply():
            if 0 <= idx < len(self.jobs):
                self.jobs[idx]["status"] = status
                if idx < len(self.row_ids):
                    iid = self.row_ids[idx]
                    vals = list(self.tree.item(iid, "values"))
                    vals[3] = status
                    self.tree.item(iid, values=vals, tags=(status,))
                save_queue_file(self.jobs)
        self.root.after(0, _apply)

    # ---------------- file pickers / log ----------------
    def _pick(self, var):
        p = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if p:
            var.set(p)

    def _pick_dir(self, var):
        p = filedialog.askdirectory()
        if p:
            var.set(p)

    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_log(self):
        try:
            while True:
                self._append(self.log_q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def open_output(self):
        out = self.out_var.get() or os.path.join(HERE, "output")
        os.makedirs(out, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(out)  # type: ignore
        elif sys.platform == "darwin":
            subprocess.Popen(["open", out])
        else:
            subprocess.Popen(["xdg-open", out])

    # ---------------- queue runner ----------------
    def _current_opts(self) -> dict:
        return {
            "clips": self.clips_var.get(),
            "images": self.images_var.get(),
            "dur": self.dur_var.get(),
            "frames": self.frames_var.get(),
            "sources": self.sources_var.get(),
            "cookies_file": self.cookies_file_var.get(),
            "cookies_browser": self.cookies_var.get(),
            "resume": self.resume_var.get(),
        }

    def start_queue(self):
        if self.running:
            return
        # convenience: if the queue is empty but the form is filled, queue it.
        if not self.jobs:
            job = self._form_to_job()
            if not self._valid_job(job):
                return
            self.jobs.append(job)
            self.clear_form()
        # reset any previous statuses so a re-run starts clean
        for job in self.jobs:
            if job.get("status") in ("Done", "Failed", "Stopped"):
                job["status"] = "Pending"
        self._refresh_tree()

        opts = self._current_opts()
        self.stop_flag.clear()
        self.running = True
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        threading.Thread(target=self._run_queue, args=(opts,), daemon=True).start()

    def _run_queue(self, opts):
        total = len(self.jobs)
        for idx in range(total):
            if self.stop_flag.is_set():
                break
            job = self.jobs[idx]
            self._set_status(idx, "Running")
            cmd = build_cmd(job, opts)
            self.log_q.put("\n" + "#" * 70 + "\n")
            self.log_q.put(f"# JOB {idx + 1}/{total}: {job.get('title') or '(no title)'}\n")
            self.log_q.put("#" * 70 + "\n")
            self.log_q.put("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n\n")
            rc = None
            try:
                # force UTF-8 both ways: exotic characters in video titles used
                # to crash collector prints on Windows' cp1252 console
                env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    bufsize=1, cwd=HERE, env=env)
                for line in self.proc.stdout:
                    self.log_q.put(line)
                rc = self.proc.wait()
            except Exception as e:
                self.log_q.put(f"\nERROR: {e}\n")
                rc = -1
            finally:
                self.proc = None

            if self.stop_flag.is_set():
                self._set_status(idx, "Stopped")
                self.log_q.put(f"\n--- job {idx + 1} stopped by user ---\n")
                break
            self._set_status(idx, "Done" if rc == 0 else "Failed")
            self.log_q.put(f"\n--- job {idx + 1} finished ({'ok' if rc == 0 else 'failed'}) ---\n")

        self.log_q.put("\n" + "=" * 70 + "\n=== QUEUE FINISHED ===\n" + "=" * 70 + "\n")
        self.running = False
        self.root.after(0, self._reset_buttons)

    def _reset_buttons(self):
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def stop(self):
        self.stop_flag.set()
        if self.proc is not None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.log_q.put("\n--- stopping after current job… ---\n")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
