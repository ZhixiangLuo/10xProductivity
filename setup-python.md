---
name: setup-python
description: Detect OS and existing Python, install Python 3.12 via winget/brew/apt when available else python.org, create .venv, install Playwright + Chromium, prepare for setup.md. Use when the repo is open but Python or .venv is missing. Assumes project folder is already on disk — not for cloning; see README Quick start.
---

# Python environment — cold start

> **What this file is for:** The user already has this repository folder (opened in Cursor, copied from a ZIP, etc.). **Python 3** is missing, too old (&lt; 3.11), or not on PATH; or a fresh **virtualenv** and **Playwright** are needed before `setup.md` can run tool recipes.
>
> **Wrong file?** If Python and `.venv` already work, continue with **`setup.md`** for tool connections only.

---

## Non-negotiable rules

1. **Run every command yourself** from the **repo root** (the directory that contains `setup.md`). Do not ask the user to paste commands unless they prefer to.
2. **Do not document `git` here** — obtaining this folder happens before this playbook (Cursor, ZIP, IT image, etc.).
3. **You choose the Python version — never ask the user to pick.** For this repo, install or standardize on **Python 3.12** (latest **3.12.x**). If the machine already has **3.11+** on PATH and it works for the venv step below, you may **skip** a new system install.
4. **Install order:** detect → **try terminal/package manager** when present → **fall back to manual [python.org](https://www.python.org/downloads/)** if automation fails or is unavailable.

---

## Target version (fixed — no prompts)

| Policy | Detail |
|--------|--------|
| **Preferred runtime** | **Python 3.12.x** |
| **Accept without reinstall** | Existing `python3` / `py -3` already **≥ 3.11** and usable for `venv` + `pip` |
| **Install / upgrade when** | No Python, command missing, or version **&lt; 3.11** |

---

## Step 0: Detect (run first)

Gather facts without asking the user anything about “which Python”:

**macOS / Linux (shell):**

```bash
uname -s    # Darwin vs Linux
uname -m    # arm64, x86_64, etc.
command -v brew >/dev/null && echo "brew: yes" || echo "brew: no"
command -v apt-get >/dev/null && echo "apt: yes" || echo "apt: no"
python3 --version 2>/dev/null || echo "python3: missing"
```

**Windows (cmd or PowerShell):**

```bat
where py 2>nul && py -3 --version
where python 2>nul && python --version
where winget 2>nul && winget --version
```

Interpretation:

- **Darwin** → follow **macOS** path below (`arm64` / `x86_64` both use Homebrew’s arch-aware bottle, or python.org **universal2**).
- **Linux** → follow **Linux** path.
- **Windows** (`ver`, `OS=Windows_NT`) → follow **Windows** path.

---

## Optional: get Homebrew or winget (only if you want the terminal install path)

**You do not need these.** Step 1 already falls back to **[python.org](https://www.python.org/downloads/)** installers, which are often **simpler for non‑technical users** than installing a package manager first.

### macOS — Homebrew is missing

- **Official install:** open **[brew.sh](https://brew.sh)** and run the **one-line install command** shown there in Terminal. It may prompt for your **Mac password** and once for **Command Line Tools** (small, not full Xcode).
- **After install:** run the **PATH** lines the installer prints (Apple Silicon vs Intel differ — copy what Homebrew shows).
- **If install is blocked** (corporate policy, no admin) → **skip Homebrew**; use **python.org** in Step 1 (path 3).

### Windows — `winget` is missing

- **`winget`** ships with Microsoft **App Installer**. It often appears after **Windows Update**.
- **Try first:** **Microsoft Store** → search **App Installer** → **Get** or **Update**, then open a **new** terminal and run `winget --version`.
- **If Store or winget is disabled** (managed PC) → **skip winget**; use **python.org** in Step 1 (path 3).

---

## Step 1: Install Python 3.12 (only if Step 0 shows missing or &lt; 3.11)

### macOS

1. **If `python3` is already 3.11 or newer** → skip to **Step 2**.
2. **Else if Homebrew is available** (`command -v brew`):

```bash
brew install python@3.12
```

Use a **new shell** (or `rehash` in zsh) so `python3` resolves. Confirm:

```bash
python3 --version   # expect Python 3.12.x
```

If `brew` errors (permissions, network, policy), continue to (3).

3. **Else — manual fallback (no `brew` or brew failed):** open **[python.org → macOS](https://www.python.org/downloads/macos/)** and install the **macOS 64-bit universal2** **Python 3.12.x** `.pkg` (always the **newest 3.12** row — you pick the file, not the user). Restart the terminal after install. Confirm `python3 --version`.

**Full Xcode:** not required. **Command Line Tools:** only if a later `pip` build fails (rare); then Apple’s prompt or `xcode-select --install`.

### Windows

1. **If `py -3` or `python` is already 3.11+** → skip to **Step 2**.
2. **Else if `winget` is available:**

```bat
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
```

Open a **new** terminal, then `py -3 --version`. If `winget` fails (store disabled, policy), continue to (3).

3. **Else — manual fallback:** **[python.org → Windows](https://www.python.org/downloads/windows/)** → **Windows installer (64-bit)** for **Python 3.12.x** — enable **“Add python.exe to PATH”**, install, new terminal, verify `py -3 --version` or `python --version`.

### Linux

1. **If `python3` is already 3.11+** → skip to **Step 2**.
2. **Else if `apt-get` is available** (Debian/Ubuntu and derivatives) — may require user interaction for `sudo`:

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv
```

Confirm `python3.12 --version`; use **`python3.12`** in place of **`python3`** in Step 2 if that is the only 3.12 binary installed. If `apt` has no `python3.12` package, use (3).

3. **Else — manual fallback:** install **3.12.x** from **[python.org → source](https://www.python.org/downloads/source/)** or follow the distro’s documented way to get 3.12; then confirm `python3 --version`.

---

## Step 2: Create the virtual environment and Playwright (all platforms)

From the **repo root** (folder containing `setup.md`). Use **`python3`** on macOS/Linux; on Linux after `apt`, **`python3.12`** if that is the installed binary name. On Windows use **`py -3`** where shown.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install playwright
playwright install chromium
touch .env
```

If `python3` is too old but `python3.12` exists:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
# ... same pip / playwright / touch .env as above
```

**Windows (cmd from repo root):**

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install playwright
playwright install chromium
type nul > .env
```

PowerShell activation (if execution policy allows):

```powershell
.\.venv\Scripts\Activate.ps1
```

If `Activate.ps1` is blocked, use **cmd** and `activate.bat` as above.

---

## Step 3: Verify

With the venv **activated**:

```bash
python -c "import playwright; print('playwright OK')"
```

Then continue with **`setup.md`** — tool SSO scripts and verify snippets expect this `.venv` and Chromium.

---

## Outputs checklist

- [ ] Detection run; **no user-facing “which version?”** — you standardized on **3.12** or accepted **≥ 3.11** already present
- [ ] **Terminal install** (`brew` / `winget` / `apt`) tried when available; **python.org** (or distro) only if needed
- [ ] `python3` / `py -3` / `python3.12` reports **3.11+** (target **3.12.x**)
- [ ] `.venv/` exists and activates without error
- [ ] `pip show playwright` shows an installed version
- [ ] `playwright install chromium` completed
- [ ] Empty `.env` at repo root (or existing file preserved)

---

## Next step

Read **`setup.md`** and set up tool connections.
