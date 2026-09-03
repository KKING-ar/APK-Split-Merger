#!/usr/bin/env python3
"""
APK Split Merger - GUI
-----------------------
A small standalone desktop tool that merges split APKs (base.apk +
split_config.*.apk, or a whole .apks/.xapk/.apkm bundle) into a single
regular, installable APK.

Zero third-party Python packages are used - only the standard library
(tkinter, subprocess, threading, os, json, zipfile, urllib). Nothing to
"pip install".

What it actually does under the hood:
    It drives APKEditor (https://github.com/REAndroid/APKEditor), a
    single executable .jar that performs the merge:
        java -jar APKEditor.jar m -i <input> -o <output> -f
    and, if auto-sign is enabled, uber-apk-signer
    (https://github.com/patrickfav/uber-apk-signer), another single
    executable .jar, to sign the result with its built-in debug
    certificate so it installs immediately:
        java -jar uber-apk-signer.jar --apks <output> --allowResign -o <tmp>
    Neither jar is bundled inside this script (they're separate projects
    with their own releases), so the things you need on the machine that
    runs this GUI are:
        1) A Java runtime (JRE 11+)      - https://adoptium.net
        2) APKEditor.jar                  - required, does the merge.
        3) uber-apk-signer.jar             - only needed if auto-sign is on.
    The app helps you locate both, or you can click the "Get …" buttons
    to open their release pages.
    Everything else (choosing files, building the command, running it,
    showing progress/log, handling errors) is done by this GUI.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
import zipfile
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "APK Split Merger"
CONFIG_FILE = os.path.join(
    os.path.expanduser("~"), ".apk_split_merger_config.json"
)
APKEDITOR_RELEASES_URL = "https://github.com/REAndroid/APKEditor/releases"
SIGNER_RELEASES_URL = "https://github.com/patrickfav/uber-apk-signer/releases"
ADOPTIUM_URL = "https://adoptium.net/"

SPLIT_ARCHIVE_EXTS = (".apks", ".xapk", ".apkm")


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def find_java():
    """Return path to a java executable, or None."""
    path = shutil.which("java")
    if path:
        return path
    # Common Windows install locations as a fallback.
    candidates = []
    for env_var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_var)
        if base:
            java_dir = os.path.join(base, "Java")
            if os.path.isdir(java_dir):
                for name in os.listdir(java_dir):
                    candidates.append(
                        os.path.join(java_dir, name, "bin", "java.exe")
                    )
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def guess_apkeditor_jar():
    """Look next to this script / exe, and in the working directory."""
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    search_dirs = [here, os.getcwd()]
    for d in search_dirs:
        try:
            for name in os.listdir(d):
                if name.lower().startswith("apkeditor") and name.lower().endswith(".jar"):
                    return os.path.join(d, name)
        except Exception:
            pass
    return None


def guess_signer_jar():
    """Look next to this script / exe, and in the working directory."""
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    search_dirs = [here, os.getcwd()]
    for d in search_dirs:
        try:
            for name in os.listdir(d):
                low = name.lower()
                if low.endswith(".jar") and ("uber-apk-signer" in low or "apksigner" in low):
                    return os.path.join(d, name)
        except Exception:
            pass
    return None


class MergerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x620")
        self.minsize(680, 540)

        self.cfg = load_config()
        self.input_items = []  # list of file paths chosen by the user
        self.output_dir = tk.StringVar(value=self.cfg.get("last_output_dir", ""))
        self.output_path = tk.StringVar(value="")
        self.jar_path = tk.StringVar(value=self.cfg.get("jar_path") or guess_apkeditor_jar() or "")
        self.java_path = tk.StringVar(value=self.cfg.get("java_path") or find_java() or "")
        self.signer_jar_path = tk.StringVar(value=self.cfg.get("signer_jar_path") or guess_signer_jar() or "")
        self.auto_sign = tk.BooleanVar(value=self.cfg.get("auto_sign", True))
        self.status_var = tk.StringVar(value="Ready.")
        self.log_queue = queue.Queue()
        self.worker = None

        self._build_ui()
        self._refresh_output_path()
        self.after(150, self._poll_log_queue)

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # --- Requirements bar -------------------------------------------------
        req = ttk.LabelFrame(self, text="Requirements")
        req.pack(fill="x", **pad)

        ttk.Label(req, text="Java runtime:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.java_entry = ttk.Entry(req, textvariable=self.java_path, width=55)
        self.java_entry.grid(row=0, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(req, text="Browse…", command=self._browse_java).grid(row=0, column=2, padx=4)
        ttk.Button(req, text="Get Java", command=lambda: webbrowser.open(ADOPTIUM_URL)).grid(row=0, column=3, padx=4)

        ttk.Label(req, text="APKEditor.jar:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.jar_entry = ttk.Entry(req, textvariable=self.jar_path, width=55)
        self.jar_entry.grid(row=1, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(req, text="Browse…", command=self._browse_jar).grid(row=1, column=2, padx=4)
        ttk.Button(req, text="Get APKEditor.jar", command=lambda: webbrowser.open(APKEDITOR_RELEASES_URL)).grid(row=1, column=3, padx=4)

        ttk.Label(req, text="uber-apk-signer.jar:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.signer_entry = ttk.Entry(req, textvariable=self.signer_jar_path, width=55)
        self.signer_entry.grid(row=2, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(req, text="Browse…", command=self._browse_signer).grid(row=2, column=2, padx=4)
        ttk.Button(req, text="Get signer.jar", command=lambda: webbrowser.open(SIGNER_RELEASES_URL)).grid(row=2, column=3, padx=4)
        ttk.Label(req, text="(only needed if auto-sign is on)", foreground="#777").grid(row=3, column=1, sticky="w", padx=6)

        req.columnconfigure(1, weight=1)

        # --- Input files ---------------------------------------------------
        inp = ttk.LabelFrame(self, text="Input: base.apk + split_config*.apk  (or one .apks / .xapk / .apkm)")
        inp.pack(fill="both", expand=True, **pad)

        list_frame = ttk.Frame(inp)
        list_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)

        btns = ttk.Frame(inp)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(btns, text="Add APK files…", command=self._add_files).pack(side="left", padx=4)
        ttk.Button(btns, text="Add a folder…", command=self._add_folder).pack(side="left", padx=4)
        ttk.Button(btns, text="Add .apks/.xapk/.apkm…", command=self._add_archive).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove selected", command=self._remove_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", command=self._clear_all).pack(side="left", padx=4)

        # --- Output ----------------------------------------------------------
        out = ttk.LabelFrame(self, text="Output folder  (file name is taken from the input automatically)")
        out.pack(fill="x", **pad)
        self.out_entry = ttk.Entry(out, textvariable=self.output_dir)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(out, text="Choose folder…", command=self._choose_output_dir).pack(side="left", padx=6)
        self.out_entry.bind("<KeyRelease>", lambda e: self._refresh_output_path())

        self.out_preview_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.out_preview_var, anchor="w", foreground="#555").pack(fill="x", padx=14)

        # --- Options -----------------------------------------------------
        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        self.clean_meta = tk.BooleanVar(value=True)
        self.validate_modules = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Strip split metadata (recommended)", variable=self.clean_meta).pack(side="left", padx=4)
        ttk.Checkbutton(opts, text="Validate versions match", variable=self.validate_modules).pack(side="left", padx=4)

        opts2 = ttk.Frame(self)
        opts2.pack(fill="x", **pad)
        ttk.Checkbutton(
            opts2,
            text="Auto-sign after merging, so it installs right away (debug signature)",
            variable=self.auto_sign,
        ).pack(side="left", padx=4)

        # --- Run bar -------------------------------------------------------
        run_bar = ttk.Frame(self)
        run_bar.pack(fill="x", **pad)
        self.run_btn = ttk.Button(run_bar, text="Merge", command=self._start_merge)
        self.run_btn.pack(side="left")
        self.progress = ttk.Progressbar(run_bar, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x", padx=12)

        # --- Log -------------------------------------------------------------
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    # ------------------------------------------------------------- actions --
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select base.apk and split_config*.apk files",
            filetypes=[("APK files", "*.apk"), ("All files", "*.*")],
        )
        for p in paths:
            if p not in self.input_items:
                self.input_items.append(p)
                self.listbox.insert(tk.END, p)
        self._refresh_output_path()

    def _add_folder(self):
        d = filedialog.askdirectory(title="Select a folder containing the split APKs")
        if not d:
            return
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".apk"):
                p = os.path.join(d, name)
                if p not in self.input_items:
                    self.input_items.append(p)
                    self.listbox.insert(tk.END, p)
        self._refresh_output_path()

    def _add_archive(self):
        p = filedialog.askopenfilename(
            title="Select a split archive",
            filetypes=[("Split archives", "*.apks *.xapk *.apkm"), ("All files", "*.*")],
        )
        if p:
            self.input_items = [p]  # an archive is used on its own
            self.listbox.delete(0, tk.END)
            self.listbox.insert(tk.END, p)
        self._refresh_output_path()

    def _remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            del self.input_items[i]
            self.listbox.delete(i)
        self._refresh_output_path()

    def _clear_all(self):
        self.input_items = []
        self.listbox.delete(0, tk.END)
        self._refresh_output_path()

    def _choose_output_dir(self):
        d = filedialog.askdirectory(title="Choose where to save the merged APK")
        if d:
            self.output_dir.set(d)
            self._refresh_output_path()

    def _derive_output_name(self):
        """Pick a sensible output file name from whatever was added as input."""
        if not self.input_items:
            return "merged.apk"
        if len(self.input_items) == 1:
            base = os.path.splitext(os.path.basename(self.input_items[0]))[0]
            return base + ".apk"
        # Multiple loose files: prefer the one that looks like the base apk
        # (i.e. not a split_config.* file), otherwise fall back to the
        # shared folder name, otherwise the first file's name.
        candidates = [p for p in self.input_items if "split_config" not in os.path.basename(p).lower()
                      and not os.path.basename(p).lower().startswith("config.")]
        pick = candidates[0] if candidates else self.input_items[0]
        name = os.path.splitext(os.path.basename(pick))[0]
        if name.lower() == "base":
            parent = os.path.basename(os.path.dirname(pick))
            if parent:
                name = parent
        return name + "_merged.apk"

    def _refresh_output_path(self):
        name = self._derive_output_name()
        d = self.output_dir.get().strip()
        full = os.path.join(d, name) if d else name
        self.output_path.set(full)
        self.out_preview_var.set("Will save as: " + full if d else "Will save as: " + name + "  (choose a folder above)")

    def _browse_jar(self):
        p = filedialog.askopenfilename(title="Locate APKEditor.jar", filetypes=[("Jar file", "*.jar")])
        if p:
            self.jar_path.set(p)

    def _browse_signer(self):
        p = filedialog.askopenfilename(title="Locate uber-apk-signer.jar", filetypes=[("Jar file", "*.jar")])
        if p:
            self.signer_jar_path.set(p)

    def _browse_java(self):
        filetypes = [("java executable", "java.exe" if os.name == "nt" else "java"), ("All files", "*.*")]
        p = filedialog.askopenfilename(title="Locate the java executable", filetypes=filetypes)
        if p:
            self.java_path.set(p)

    # -------------------------------------------------------------- merge --
    def _log(self, line):
        self.log_queue.put(line)

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, line + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.after(150, self._poll_log_queue)

    def _validate_before_run(self):
        if not self.input_items:
            messagebox.showerror(APP_TITLE, "Add at least a base.apk (plus splits), or one .apks/.xapk/.apkm archive.")
            return False
        if not self.output_dir.get().strip():
            messagebox.showerror(APP_TITLE, "Choose a folder to save the merged APK into.")
            return False
        self._refresh_output_path()
        java = self.java_path.get().strip() or find_java()
        if not java or not (shutil.which(java) or os.path.isfile(java)):
            messagebox.showerror(
                APP_TITLE,
                "Java was not found. Install a Java runtime (click 'Get Java'), "
                "or browse to java.exe manually.",
            )
            return False
        self.java_path.set(java)
        jar = self.jar_path.get().strip()
        if not jar or not os.path.isfile(jar):
            messagebox.showerror(
                APP_TITLE,
                "APKEditor.jar was not found. Click 'Get APKEditor.jar' to download it, "
                "then browse to the .jar file.",
            )
            return False
        if self.auto_sign.get():
            signer = self.signer_jar_path.get().strip()
            if not signer or not os.path.isfile(signer):
                messagebox.showerror(
                    APP_TITLE,
                    "Auto-sign is on, but uber-apk-signer.jar was not found. "
                    "Click 'Get signer.jar' to download it, then browse to the .jar file "
                    "(or turn off auto-sign).",
                )
                return False
        return True

    def _start_merge(self):
        if self.worker and self.worker.is_alive():
            return
        if not self._validate_before_run():
            return

        # Persist choices for next launch.
        self.cfg["jar_path"] = self.jar_path.get().strip()
        self.cfg["java_path"] = self.java_path.get().strip()
        self.cfg["last_output_dir"] = self.output_dir.get().strip()
        self.cfg["signer_jar_path"] = self.signer_jar_path.get().strip()
        self.cfg["auto_sign"] = self.auto_sign.get()
        save_config(self.cfg)

        self.run_btn.config(state="disabled")
        self.progress.start(12)
        self.status_var.set("Merging…")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

        self.worker = threading.Thread(target=self._run_merge_thread, daemon=True)
        self.worker.start()
        self.after(200, self._check_worker)

    def _check_worker(self):
        if self.worker.is_alive():
            self.after(200, self._check_worker)
        else:
            self.progress.stop()
            self.run_btn.config(state="normal")

    def _run_merge_thread(self):
        tmp_input_dir = None
        try:
            items = list(self.input_items)
            single = items[0] if len(items) == 1 else None
            is_archive = single and single.lower().endswith(SPLIT_ARCHIVE_EXTS)

            if is_archive:
                input_arg = single
            elif len(items) == 1 and items[0].lower().endswith(".apk"):
                # A single loose apk - just pass it through, nothing to merge.
                input_arg = items[0]
            else:
                # Multiple loose .apk files: APKEditor's merge command wants a
                # directory (or archive) as input, so stage the chosen files
                # into a temp folder.
                import tempfile
                tmp_input_dir = tempfile.mkdtemp(prefix="apkmerge_")
                for p in items:
                    dest = os.path.join(tmp_input_dir, os.path.basename(p))
                    shutil.copy2(p, dest)
                input_arg = tmp_input_dir

            out_path = self.output_path.get().strip()
            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.isdir(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            if os.path.exists(out_path):
                os.remove(out_path)

            cmd = [
                self.java_path.get().strip(),
                "-jar",
                self.jar_path.get().strip(),
                "m",  # merge
                "-i",
                input_arg,
                "-o",
                out_path,
                "-f",  # overwrite
            ]
            if self.clean_meta.get():
                cmd.append("-clean-meta")
            if self.validate_modules.get():
                cmd.append("-validate-modules")

            self._log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self._log(line.rstrip())
            code = proc.wait()

            if code == 0 and os.path.isfile(out_path):
                self._log("\nMerge done: " + out_path)

                signed_ok = None
                if self.auto_sign.get():
                    signed_ok = self._sign_apk(out_path)

                if self.auto_sign.get() and signed_ok:
                    self._log("Signed successfully - ready to install.")
                    self.status_var.set("Done (signed): " + out_path)
                    self.after(0, lambda: messagebox.showinfo(
                        APP_TITLE,
                        "Merge complete and signed!\n\n" + out_path +
                        "\n\nThis APK is ready to install right away "
                        "(signed with a debug certificate)."
                    ))
                elif self.auto_sign.get() and not signed_ok:
                    self.status_var.set("Merged, but signing failed - see log.")
                    self.after(0, lambda: messagebox.showwarning(
                        APP_TITLE,
                        "The merge succeeded, but auto-signing failed - see the log.\n\n"
                        + out_path +
                        "\n\nThe file was saved unsigned; you'll need to sign it manually "
                        "before it will install."
                    ))
                else:
                    self.status_var.set("Done: " + out_path)
                    self.after(0, lambda: messagebox.showinfo(
                        APP_TITLE,
                        "Merge complete!\n\n" + out_path +
                        "\n\nNote: the app's signature was broken by the merge, "
                        "so you'll need to sign it (e.g. with apksigner and a "
                        "debug/release keystore) before it will install, or turn on "
                        "'Auto-sign' next time."
                    ))
            else:
                self.status_var.set("Failed - see log.")
                self.after(0, lambda: messagebox.showerror(APP_TITLE, "Merge failed. See the log for details."))
        except Exception as e:
            self._log("ERROR: " + str(e))
            self.status_var.set("Failed - see log.")
            self.after(0, lambda: messagebox.showerror(APP_TITLE, f"Merge failed:\n{e}"))
        finally:
            if tmp_input_dir and os.path.isdir(tmp_input_dir):
                shutil.rmtree(tmp_input_dir, ignore_errors=True)

    def _sign_apk(self, apk_path):
        """Sign apk_path in place using uber-apk-signer.jar (debug keystore
        by default). Returns True on success, False on failure."""
        import tempfile

        self._log("\nSigning…")
        signer_jar = self.signer_jar_path.get().strip()
        tmp_out_dir = tempfile.mkdtemp(prefix="apksign_")
        try:
            cmd = [
                self.java_path.get().strip(),
                "-jar",
                signer_jar,
                "--apks",
                apk_path,
                "--allowResign",
                "-o",
                tmp_out_dir,
            ]
            self._log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self._log(line.rstrip())
            code = proc.wait()

            if code != 0:
                return False

            # uber-apk-signer writes the signed apk under tmp_out_dir with a
            # suffix like "-aligned-debugSigned.apk" - find it and put it
            # back at the exact path the user expects.
            produced = [
                os.path.join(tmp_out_dir, n)
                for n in os.listdir(tmp_out_dir)
                if n.lower().endswith(".apk")
            ]
            if not produced:
                return False
            signed_file = max(produced, key=os.path.getmtime)
            shutil.move(signed_file, apk_path)
            return True
        except Exception as e:
            self._log("Signing error: " + str(e))
            return False
        finally:
            shutil.rmtree(tmp_out_dir, ignore_errors=True)


def main():
    app = MergerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
