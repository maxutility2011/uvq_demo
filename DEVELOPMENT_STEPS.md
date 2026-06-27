# Development Steps: UVQ Video Quality Assessment Tool

## Overview

This document summarizes every step taken to build and publish `uvq_demo.py`,
a Python program that assesses video quality using Google's UVQ model and
writes a structured JSON report.

---

## Step 1: Research the UVQ Repository

**What:** Fetched and read the UVQ GitHub repository (`https://github.com/google/uvq`)
— its README, source files, and CLI entry point (`uvq_inference.py`).

**Why:** UVQ is not published to PyPI and has no installable package. To write a
correct wrapper, we needed to understand:
- How the model is loaded and called (`uvq1p5.UVQ1p5`, `uvq1p0.UVQ1p0`)
- What `infer()` parameters it expects (`video_filename`, `video_length`, `fps`, `transpose`, etc.)
- What outputs it returns (overall score, per-frame scores, frame indices)
- What supporting utilities exist (`utils/probe.py` for FFprobe-based metadata)
- That FFmpeg must be on PATH (used internally for frame extraction)

---

## Step 2: Check the Environment

**What:** Inspected the system for Python version, FFmpeg, pip, git, and existing
packages.

**Why:** The target machine had an unusual setup:
- Python 3.14 (system) had no `pip` or `ensurepip`
- `git` was not installed initially
- A Google Cloud SDK snap (`/snap/google-cloud-cli/`) provided a bundled
  Python 3.14 with a working `pip3`
- FFmpeg was available at `/usr/bin/ffmpeg`

This determined which Python binary and pip to use for installing dependencies.

---

## Step 3: Install Python Dependencies

**What:** Ran pip via the gcloud snap's Python to install:
`torch`, `torchvision`, `tqdm`, `numpy`, `pandas`

**Command:**
```bash
/snap/google-cloud-cli/470/platform/bundledpythonunix/bin/pip3 install \
    torch torchvision tqdm numpy pandas
```

**Why:** UVQ requires PyTorch for model inference, torchvision for image
transforms, tqdm for progress bars, numpy for tensor operations, and pandas
for data handling. These are listed in UVQ's `requirements.txt`.

---

## Step 4: Download the UVQ Repository

**What:** Downloaded the UVQ repo as a zip archive and extracted it to
`/home/maxutility2011_gmail_com/uvq-main/`.

**Why:** `git` was not yet installed at this point. The UVQ repo is not an
installable package — it must be on the Python path so the program can import
`uvq1p5_pytorch`, `uvq_pytorch`, and `utils.probe`. Python's built-in
`urllib.request` and `zipfile` modules were used as an alternative to git/unzip
(neither was available).

---

## Step 5: Write the Main Program (`uvq_demo.py`)

**What:** Created `/home/maxutility2011_gmail_com/src/uvq_demo.py`.

**Why / Design decisions:**

| Decision | Reason |
|---|---|
| Auto-detect UVQ repo path | Avoids requiring `--uvq_path` every time; searches common locations relative to the script and home directory |
| Support both UVQ 1.5 and 1.0 | UVQ 1.5 gives a single MOS-like score; UVQ 1.0 gives 7 component scores useful for diagnosing specific quality issues |
| Use `utils.probe` for video metadata | Reuses UVQ's own FFprobe wrappers to get duration, FPS, frame count, and dimensions accurately |
| Auto-detect portrait orientation | UVQ requires `transpose=True` for portrait (width < height) videos to process correctly |
| `video_length` = duration in seconds | A key insight from reading the source: UVQ's `infer()` expects whole-second duration, not frame count. An initial version mistakenly passed `ceil(nb_frames / fps_sampled)`, which inflated the length and caused the model to attempt reading far more frames than existed |
| JSON output with full metadata | Report includes video metadata (path, dimensions, FPS, duration) alongside scores, making reports self-contained and auditable |

---

## Step 6: Fix `video_length` Bug

**What:** During testing, the program crashed (exit code 137, OOM / process killed)
with a UVQ warning:

```
WARNING:root:Decoding may be truncated: 43545600 bytes (7 frames) <
933120000 bytes (150 frames), or video length (150s) may be too incorrect
```

For a 5-second, 30fps video the initial `compute_video_length()` returned:
`ceil(150 frames / 1 fps_sampled) = 150` — treating it as 150 seconds instead of 5.

**Fix:** Rewrote `compute_video_length()` to always derive duration in seconds
from `probe` metadata (`ceil(duration)` or `ceil(nb_frames / orig_fps)` as fallback),
independent of the sampling rate.

**Why:** `video_length` passed to `infer()` represents the video's actual
duration in seconds, not the number of frames that will be sampled. The sampling
rate only controls how many frames are extracted within that duration.

---

## Step 7: End-to-End Test

**What:** Generated a synthetic 5-second 1280×720 test video using FFmpeg, then
ran the program against it:

```bash
ffmpeg -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 \
    -c:v libx264 /tmp/test_video.mp4

python uvq_demo.py /tmp/test_video.mp4 \
    --uvq_path /home/maxutility2011_gmail_com/uvq-main \
    --output /tmp/uvq_report.json
```

**Result:**
```
UVQ 1.5 score: 3.4671
Per-frame range: 3.4474 – 3.4841 (5 frames sampled)
Report saved to: /tmp/uvq_report.json
```

**Why:** Confirmed that the full pipeline — video probing, model loading, frame
extraction, inference, and JSON output — works correctly before pushing to GitHub.

---

## Step 8: Write Supporting Files

**What:** Created `requirements.txt` and `README.md` in `/home/maxutility2011_gmail_com/src/`.

**Why:**
- `requirements.txt` lets users install dependencies with a single `pip install -r requirements.txt`
- `README.md` documents setup, all CLI arguments, usage examples, and the report JSON schema — necessary context for anyone using the repo

---

## Step 9: Push to GitHub

**What:** Initialized a git repo in `/home/maxutility2011_gmail_com/src/`, committed
the three files, and pushed to `https://github.com/maxutility2011/uvq_demo`.

**Complications encountered:**
1. `git` was not installed → user ran `sudo apt-get install git`
2. `git config` needed the correct GitHub email (`maxutility2011@gmail.com`, not the session email)
3. HTTPS push required a GitHub Personal Access Token with `repo` scope (the push URL format is `https://TOKEN@github.com/...`)
4. The initial token attempt returned HTTP 403 (wrong token scope or permissions); the user regenerated a correct token and the push succeeded

**Commands:**
```bash
git config --global user.name "maxutility2011"
git config --global user.email "maxutility2011@gmail.com"
git init && git branch -m main
git remote add origin https://github.com/maxutility2011/uvq_demo.git
git add uvq_demo.py requirements.txt README.md
git commit -m "Add UVQ video quality assessment tool"
git push https://TOKEN@github.com/maxutility2011/uvq_demo.git main
```

---

## Final Result

| Artifact | Location |
|---|---|
| Main program | `/home/maxutility2011_gmail_com/src/uvq_demo.py` |
| Dependencies | `/home/maxutility2011_gmail_com/src/requirements.txt` |
| Documentation | `/home/maxutility2011_gmail_com/src/README.md` |
| GitHub repo | `https://github.com/maxutility2011/uvq_demo` |
| UVQ repo (local) | `/home/maxutility2011_gmail_com/uvq-main/` |
| Python runtime | `/snap/google-cloud-cli/470/platform/bundledpythonunix/bin/python3.14` |
