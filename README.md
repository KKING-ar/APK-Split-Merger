# APK Split Merger

A simple desktop app that merges **split APKs** (`base.apk` + `split_config.*.apk`,
or a whole `.apks` / `.xapk` / `.apkm` bundle) into **one regular, installable
APK file**.

No install, no command line, no Python packages to set up — just add your
files, pick a save folder, click **Merge**. If your bundle also has OBB
expansion files, they're pulled out and clearly labeled for you too —
see [About OBB files](#-about-obb-files).

![status](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![python](https://img.shields.io/badge/python-3.8%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## What this is for

Apps downloaded as "split APKs" (from tools that pull APKs off a device, or
from third-party APK sites) come as several files instead of one:

```
base.apk
split_config.arm64_v8a.apk
split_config.xxhdpi.apk
split_config.en.apk
```

Android itself installs all of these together, but a lot of older tools,
sideloading methods, and some devices only accept a **single** `.apk` file.
This app combines the pieces back into one universal APK you can install
normally.

---

## ✅ What you need before you start

You need these free things, downloaded once:

| # | Requirement | Why | Get it |
|---|---|---|---|
| 1 | **Java (JRE 11 or newer)** | The merge (and signing) engine runs on Java. | [adoptium.net](https://adoptium.net/) — download, run the installer, done. |
| 2 | **APKEditor.jar** | The file that performs the merge. This app is a friendly front-end for it. | [APKEditor releases](https://github.com/REAndroid/APKEditor/releases) — download the `.jar` file (no install needed). |
| 3 | **uber-apk-signer.jar** *(only if you want Auto-sign)* | Signs the merged APK with a built-in debug certificate so it installs immediately, without you needing your own keystore. | [uber-apk-signer releases](https://github.com/patrickfav/uber-apk-signer/releases) — download the `.jar` file. |

That's it. Nothing else to install — the app itself is a single Python
script with **zero third-party dependencies** (it only uses Python's
built-in libraries).

> 💡 Tip: put both `.jar` files in the **same folder** as this app — it
> will find them automatically and you won't need to browse for them
> every time.

---

## 🚀 How to use it

1. Make sure you have **Python 3.8+** installed
   ([python.org/downloads](https://www.python.org/downloads/) — on
   Windows, tick **"Add python.exe to PATH"** during install).
2. Download this repo's files (or click **Code → Download ZIP**, or grab
   the zip from [Releases](../../releases)) and unzip them into one folder.
3. Launch the app:
   ```
   python apk_merger_gui.py
   ```
   On Windows you can also just double-click `apk_merger_gui.py` once
   Python is installed.

---

## 📋 Step-by-step: merging your first APK

1. **Open the app.**
2. At the top, check the **Requirements** boxes:
   - *Java runtime* — should auto-fill if Java is installed. If it's blank,
     click **Get Java**, install it, then restart the app.
   - *APKEditor.jar* — should auto-fill if the jar is next to the app. If
     it's blank, click **Get APKEditor.jar** to download it, then **Browse…**
     to select the file you downloaded.
   - *uber-apk-signer.jar* — only needed if you leave **Auto-sign** turned
     on (it is, by default). Same idea: click **Get signer.jar** if it's
     blank, then **Browse…** to it.
3. **Add your files** — pick whichever matches what you have:
   - **Add APK files…** → select `base.apk` + all the `split_config*.apk` files together.
   - **Add a folder…** → select a folder that already contains all the split APKs.
   - **Add .apks/.xapk/.apkm…** → select a single bundle file if that's what you have.
4. **Choose a folder** under *Output* — this is just the destination folder.
   The app automatically names the merged file for you (matching your
   original app's name), so you don't need to type anything.
5. Click **Merge**. Progress and any messages appear in the **Log** box at
   the bottom.
   - If your `.xapk`/`.apks` bundle also contains **OBB expansion files**
     (extra game/app data stored outside the APK), you'll get a heads-up
     before the merge starts — see [About OBB files](#-about-obb-files)
     below.
6. When it finishes, you'll see a confirmation with the saved file's
   location.

---

## ✍️ About signing

Merging changes the app's internal files, which **breaks its original
digital signature**. Android refuses to install an unsigned or
"incorrectly" signed APK — so by default this app **signs the merged APK
for you automatically**, right after merging, using a built-in debug
certificate. That means the file it saves is ready to install immediately;
you don't need to do anything else.

If you'd rather sign it yourself (e.g. with your own release keystore),
just turn off the **Auto-sign** checkbox before clicking Merge, and sign
the output afterward with your tool of choice — `apksigner`, or an app
like **APK Editor Studio** can do it too.

> Note: a debug-signed APK is fine for personal installs and testing, but
> it is **not** meant for distributing an app to other people through an
> app store — for that you'd want your own release keystore.

---

## 📦 About OBB files

Some `.xapk` / `.apks` bundles (mostly games) carry **OBB expansion
files** alongside the split APKs — these are large asset/data files
(`main.*.obb`, `patch.*.obb`) that Android stores separately from the
APK, normally under `Android/obb/<package name>/` on the device. They're
**not part of the APK** and can't be merged into it — that's just how
Android handles them.

If the archive you add contains any, this app:

1. **Flags it up front** — an orange notice appears under the file list
   as soon as you pick the archive, telling you how many OBB files were
   found.
2. **Warns you again right before merging** — a confirmation dialog
   explains that the merge will proceed as normal and the OBB files will
   be pulled out separately, so nothing gets lost or silently dropped.
3. **Extracts them automatically** during the merge, into a
   `<merged apk name>_OBB` folder saved next to the merged APK, keeping
   the `<package name>/main.*.obb` structure intact.

Once merging is done, **copy that folder's contents onto the device's
`Android/obb/` folder** (so you end up with
`Android/obb/<package name>/main.*.obb`, etc.) alongside installing the
merged APK. Without this step, the app will install fine but may fail to
load its assets or prompt to "download additional data" on first launch.

---

## 🔧 Options explained

| Option | What it does |
|---|---|
| **Strip split metadata (recommended)** | Removes leftover "this app expects to be installed as split parts" info from the manifest, so the merged APK installs cleanly as a normal single APK. Leave this checked unless you have a specific reason not to. |
| **Validate versions match** | Double-checks that all the split files came from the *same* app version before merging, and stops if they don't match. Useful if you're not 100% sure your files belong together. |
| **Auto-sign after merging (on by default)** | Signs the merged APK right away with a built-in debug certificate, so the file you get is immediately installable. Turn this off if you plan to sign with your own keystore instead. |

---

## ❓ Troubleshooting

- **"Java was not found"** — install Java from the link above, then restart
  the app. If it's still not found, click **Browse…** next to *Java runtime*
  and manually select `java.exe` (usually under `C:\Program Files\Java\...`).
- **"APKEditor.jar was not found"** — download it from the link above and
  click **Browse…** next to *APKEditor.jar* to select the file.
- **"uber-apk-signer.jar was not found"** — same idea: download it, or
  just turn off **Auto-sign** if you don't need automatic signing.
- **Merged APK still won't install even though it was auto-signed** — this
  is rare, but try re-running with *Strip split metadata* checked, or sign
  manually with your own keystore to compare (see [About signing](#️-about-signing) above).
- **"App not installed" error even after signing** — double check the
  *Strip split metadata* option was enabled during the merge.
- **App installs but assets are missing / it asks to "download additional
  data"** — check whether a `<name>_OBB` folder was created next to your
  merged APK (see [About OBB files](#-about-obb-files) above), and copy
  its contents into `Android/obb/<package name>/` on the device.

---

## Credits

This app is a GUI front-end around two excellent open-source tools that do
the real work:
- [APKEditor](https://github.com/REAndroid/APKEditor) by REAndroid — merging.
- [uber-apk-signer](https://github.com/patrickfav/uber-apk-signer) by
  patrickfav — signing.

This project just makes them accessible without the command line.

## License

MIT — see [LICENSE](LICENSE).
