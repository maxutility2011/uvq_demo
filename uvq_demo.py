"""
Video quality assessment using Google's UVQ (Universal Video Quality) model.

Usage:
    python uvq_demo.py <video_file> [options]

Example:
    python uvq_demo.py input.mp4 --output report.json
    python uvq_demo.py input.mp4 --model_version 1.0 --output report.json --device cuda
"""

import argparse
import json
import math
import os
import sys
import datetime


def find_uvq_repo(uvq_path: str | None) -> str:
    """Locate the UVQ repository directory."""
    if uvq_path:
        if not os.path.isdir(uvq_path):
            raise FileNotFoundError(f"UVQ path not found: {uvq_path}")
        return uvq_path

    candidates = [
        os.path.join(os.path.dirname(__file__), "uvq"),
        os.path.join(os.path.dirname(__file__), "uvq-main"),
        os.path.join(os.path.dirname(__file__), "..", "uvq"),
        os.path.join(os.path.dirname(__file__), "..", "uvq-main"),
        os.path.expanduser("~/uvq"),
        os.path.expanduser("~/uvq-main"),
    ]
    for path in candidates:
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "uvq_inference.py")):
            return os.path.abspath(path)

    raise FileNotFoundError(
        "UVQ repository not found. Clone it with:\n"
        "  git clone https://github.com/google/uvq\n"
        "Then pass --uvq_path /path/to/uvq"
    )


def probe_video(video_path: str, probe_module, ffprobe_path: str) -> dict:
    """Gather video metadata needed for UVQ inference."""
    duration = probe_module.get_video_duration(video_path, ffprobe_path)
    orig_fps = probe_module.get_r_frame_rate(video_path, ffprobe_path)
    nb_frames = probe_module.get_nb_frames(video_path, ffprobe_path)
    dimensions = probe_module.get_dimensions(video_path, ffprobe_path)

    return {
        "duration": duration,
        "orig_fps": orig_fps,
        "nb_frames": nb_frames,
        "dimensions": dimensions,
    }


def compute_video_length(meta: dict) -> int:
    """Return video duration in whole seconds for UVQ's infer() call."""
    duration = meta["duration"]
    nb_frames = meta["nb_frames"]
    orig_fps = meta["orig_fps"]

    if duration:
        return math.ceil(duration)
    if nb_frames and orig_fps:
        return math.ceil(nb_frames / orig_fps)
    raise ValueError("Cannot determine video length from metadata.")


def run_uvq15(model, video_path: str, meta: dict, fps: int, device: str, ffmpeg_path: str) -> dict:
    """Run UVQ 1.5 inference and return result dict."""
    fps_to_use = fps
    if fps_to_use == -1:
        if meta["orig_fps"] is None:
            raise ValueError("Cannot determine original FPS; cannot use fps=-1.")
        fps_to_use = meta["orig_fps"]

    video_length = compute_video_length(meta)
    transpose = meta["dimensions"] is not None and meta["dimensions"][0] < meta["dimensions"][1]

    results = model.infer(
        video_filename=video_path,
        video_length=video_length,
        transpose=transpose,
        fps=fps_to_use,
        orig_fps=meta["orig_fps"],
        ffmpeg_path=ffmpeg_path,
        device=device,
    )

    per_frame = results.get("per_frame_scores", [])
    frame_indices = results.get("frame_indices", [])

    return {
        "model_version": "1.5",
        "overall_score": float(results["uvq1p5_score"]),
        "score_label": "uvq1p5_score",
        "per_frame_scores": [float(s) for s in per_frame],
        "frame_indices": list(frame_indices),
        "fps_sampled": fps_to_use,
        "transpose_applied": transpose,
        "video_length_seconds": video_length,
    }


def run_uvq10(model, video_path: str, meta: dict) -> dict:
    """Run UVQ 1.0 inference and return result dict."""
    video_length = compute_video_length(meta)
    transpose = meta["dimensions"] is not None and meta["dimensions"][0] < meta["dimensions"][1]

    raw = model.infer(
        video_filename=video_path,
        video_length=video_length,
        transpose=transpose,
    )
    scores = {k: float(v) for k, v in raw.items()}

    return {
        "model_version": "1.0",
        "overall_score": scores.get("compression_content_distortion"),
        "score_label": "compression_content_distortion",
        "component_scores": {
            "compression": scores.get("compression"),
            "content": scores.get("content"),
            "distortion": scores.get("distortion"),
            "compression_content": scores.get("compression_content"),
            "compression_distortion": scores.get("compression_distortion"),
            "content_distortion": scores.get("content_distortion"),
            "compression_content_distortion": scores.get("compression_content_distortion"),
        },
        "fps_sampled": 5,
        "transpose_applied": transpose,
        "video_length_seconds": video_length,
    }


def build_report(video_path: str, meta: dict, inference_result: dict) -> dict:
    """Assemble the final UVQ report dict."""
    dims = meta["dimensions"]
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "video": {
            "path": os.path.abspath(video_path),
            "filename": os.path.basename(video_path),
            "duration_seconds": meta["duration"],
            "frame_rate": meta["orig_fps"],
            "total_frames": meta["nb_frames"],
            "width": dims[0] if dims else None,
            "height": dims[1] if dims else None,
        },
        "uvq_assessment": inference_result,
    }


def write_report(report: dict, output_path: str) -> None:
    """Write the JSON report to disk."""
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Assess video quality using Google UVQ and write a JSON report."
    )
    parser.add_argument("video", help="Path to the input video file.")
    parser.add_argument(
        "--output",
        default="uvq_report.json",
        help="Path for the output JSON report (default: uvq_report.json).",
    )
    parser.add_argument(
        "--model_version",
        choices=["1.0", "1.5"],
        default="1.5",
        help="UVQ model version (default: 1.5).",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Inference device (default: cpu).",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=1,
        help="Frame sampling rate for UVQ 1.5 (default: 1). Use -1 for all frames. Ignored for UVQ 1.0.",
    )
    parser.add_argument(
        "--uvq_path",
        default=None,
        help="Path to the cloned UVQ repository. Auto-detected if not specified.",
    )
    parser.add_argument(
        "--ffmpeg_path",
        default="ffmpeg",
        help="Path to ffmpeg executable (default: ffmpeg).",
    )
    parser.add_argument(
        "--ffprobe_path",
        default="ffprobe",
        help="Path to ffprobe executable (default: ffprobe).",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"Error: video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    uvq_repo = find_uvq_repo(args.uvq_path)
    print(f"Using UVQ repository: {uvq_repo}")

    if uvq_repo not in sys.path:
        sys.path.insert(0, uvq_repo)

    try:
        from utils import probe
    except ImportError as e:
        print(f"Error importing UVQ utils: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Probing video: {args.video}")
    meta = probe_video(args.video, probe, args.ffprobe_path)
    print(
        f"  Duration: {meta['duration']:.2f}s | FPS: {meta['orig_fps']} | "
        f"Frames: {meta['nb_frames']} | Dimensions: {meta['dimensions']}"
    )

    print(f"Loading UVQ {args.model_version} model...")
    try:
        import torch
        if args.device == "cuda" and not torch.cuda.is_available():
            print("Warning: CUDA requested but not available; falling back to CPU.")
            args.device = "cpu"

        if args.model_version == "1.5":
            from uvq1p5_pytorch.utils import uvq1p5
            model = uvq1p5.UVQ1p5()
            if args.device == "cuda":
                model.cuda()
            print(f"Running UVQ 1.5 inference (fps={args.fps}, device={args.device})...")
            inference_result = run_uvq15(model, args.video, meta, args.fps, args.device, args.ffmpeg_path)
        else:
            from uvq_pytorch.utils import uvq1p0
            model = uvq1p0.UVQ1p0()
            if args.device == "cuda":
                model.cuda()
            print("Running UVQ 1.0 inference (fixed 5fps sampling)...")
            inference_result = run_uvq10(model, args.video, meta)

    except ImportError as e:
        print(f"Error loading UVQ model: {e}", file=sys.stderr)
        print("Ensure dependencies are installed: pip install torch torchvision tqdm numpy pandas", file=sys.stderr)
        sys.exit(1)

    report = build_report(args.video, meta, inference_result)

    score = inference_result["overall_score"]
    print(f"\nUVQ {args.model_version} score: {score:.4f}")

    if args.model_version == "1.5" and inference_result.get("per_frame_scores"):
        frames = inference_result["per_frame_scores"]
        print(f"Per-frame range: {min(frames):.4f} – {max(frames):.4f} ({len(frames)} frames sampled)")

    write_report(report, args.output)
    print(f"\nReport saved to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
