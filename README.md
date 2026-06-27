# UVQ Demo

A Python program to assess video quality using Google's [UVQ (Universal Video Quality)](https://github.com/google/uvq) model, with JSON report output.

## Setup

**1. Clone the UVQ repository:**
```bash
git clone https://github.com/google/uvq
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

FFmpeg must also be on your PATH:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Usage

```bash
python uvq_demo.py <video_file> [options]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `video` | (required) | Path to the input video file |
| `--output` | `uvq_report.json` | Path for the output JSON report |
| `--model_version` | `1.5` | UVQ model version: `1.0` or `1.5` |
| `--device` | `cpu` | Inference device: `cpu` or `cuda` |
| `--fps` | `1` | Frame sampling rate (UVQ 1.5 only; `-1` = all frames) |
| `--uvq_path` | (auto-detected) | Path to cloned UVQ repo |
| `--ffmpeg_path` | `ffmpeg` | Path to ffmpeg binary |
| `--ffprobe_path` | `ffprobe` | Path to ffprobe binary |

### Examples

```bash
# Basic assessment with UVQ 1.5 (default)
python uvq_demo.py my_video.mp4

# Save report to a specific path
python uvq_demo.py my_video.mp4 --output /tmp/my_report.json

# Use UVQ 1.0 model
python uvq_demo.py my_video.mp4 --model_version 1.0 --output report_v1.json

# GPU inference with higher sampling rate
python uvq_demo.py my_video.mp4 --device cuda --fps 5 --output report.json

# Specify UVQ repo location explicitly
python uvq_demo.py my_video.mp4 --uvq_path /path/to/uvq --output report.json
```

## Report Format

The output is a JSON file with the following structure:

### UVQ 1.5 report
```json
{
  "generated_at": "2026-01-01T00:00:00Z",
  "video": {
    "path": "/abs/path/to/video.mp4",
    "filename": "video.mp4",
    "duration_seconds": 30.0,
    "frame_rate": 30,
    "total_frames": 900,
    "width": 1920,
    "height": 1080
  },
  "uvq_assessment": {
    "model_version": "1.5",
    "overall_score": 3.87,
    "score_label": "uvq1p5_score",
    "per_frame_scores": [3.9, 3.85, 3.88, ...],
    "frame_indices": [0, 30, 60, ...],
    "fps_sampled": 1,
    "transpose_applied": false,
    "video_length_seconds": 30
  }
}
```

### UVQ 1.0 report
```json
{
  "generated_at": "2026-01-01T00:00:00Z",
  "video": { "..." : "..." },
  "uvq_assessment": {
    "model_version": "1.0",
    "overall_score": 0.72,
    "score_label": "compression_content_distortion",
    "component_scores": {
      "compression": 0.81,
      "content": 0.74,
      "distortion": 0.69,
      "compression_content": 0.77,
      "compression_distortion": 0.75,
      "content_distortion": 0.71,
      "compression_content_distortion": 0.72
    },
    "fps_sampled": 5,
    "transpose_applied": false,
    "video_length_seconds": 30
  }
}
```

## Score Interpretation

- **UVQ 1.5**: MOS-like scale (1–5). Higher is better. ~4.0+ is good quality; ~2.0 and below indicates significant degradation.
- **UVQ 1.0**: Scores range 0–1. The `compression_content_distortion` composite is the primary quality indicator.

## Auto-detection of UVQ Path

The script searches for the UVQ repo in this order:
1. `--uvq_path` argument
2. `./uvq` or `./uvq-main` (next to the script)
3. `../uvq` or `../uvq-main`
4. `~/uvq` or `~/uvq-main`
