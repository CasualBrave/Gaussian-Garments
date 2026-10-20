"""GPU regression on trusted local assets; all generated files stay in --output."""

import argparse
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys

import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory", type=Path, required=True, help="Trusted trajectory pickle")
    parser.add_argument("--output", type=Path, required=True, help="New test directory")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with args.trajectory.open("rb") as handle:
        trajectory = pickle.load(handle)
    trajectory["pred"] = trajectory["pred"][:1]
    trajectory["obstacle"] = trajectory["obstacle"][:1]
    with (output / "frame.pkl").open("wb") as handle:
        pickle.dump(trajectory, handle)
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", XDG_CACHE_HOME=str(output / "cache"),
               MPLCONFIGDIR=str(output / "cache/matplotlib"), CUDA_CACHE_PATH=str(output / "cache/cuda"),
               TRITON_CACHE_DIR=str(output / "cache/triton"), TMPDIR=str(output / "tmp"))
    (output / "tmp").mkdir()
    results = {}
    cases = [("original", "original", 1), ("original-repeat", "original", 1),
             ("v3-one", "v3", 1), ("v3-half", "v3", .5),
             ("v3-zero", "v3", 0), ("lean-half", "v3", .5)]
    for label, mode, scale in cases:
        lean = label.startswith("lean")
        script = "render_lean.py" if lean else "render_turntable.py"
        command = [sys.executable, str(root / script), "--traj_path", str(output / "frame.pkl"),
                   "--output_path", str(output / label), "--opacity-mode", mode, "--opacity-scale", str(scale)]
        if not lean:
            command += ["--frame_idx", "0", "--n-angles", "1"]
        with (output / f"{label}.log").open("w") as log:
            subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        image_path = output / label / ("renders/0000.png" if lean else "angle_000.png")
        with Image.open(image_path) as image:
            results[label] = np.array(image)
        print(f"{label}: {image_path}", flush=True)
    original = results["original"]
    def difference(a, b):
        delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
        return dict(max_channel_error=int(delta.max()), mean_channel_error=float(delta.mean()),
                    changed_pixels=int(np.any(delta != 0, axis=-1).sum()))

    baseline = difference(original, results["original-repeat"])
    endpoint = difference(original, results["v3-one"])
    entries = difference(results["lean-half"], results["v3-half"])
    # Independent GPU rasterizations may round a few channels differently.
    def equivalent(error):
        return error["max_channel_error"] <= 1 and error["changed_pixels"] / (original.shape[0] * original.shape[1]) <= .0001

    report = dict(
        shape=list(original.shape),
        original_nonblank=bool(original.std() > 1),
        v3_one_matches_original=bool(np.array_equal(original, results["v3-one"])),
        half_changed_pixels=int(np.any(original != results["v3-half"], axis=-1).sum()),
        zero_changed_pixels=int(np.any(original != results["v3-zero"], axis=-1).sum()),
        lean_matches_turntable=bool(np.array_equal(results["lean-half"], results["v3-half"])),
        repeated_original_difference=baseline, endpoint_difference=endpoint, entry_difference=entries,
        tolerance=dict(max_channel_error=1, max_changed_pixel_fraction=.0001),
        passed=all(equivalent(error) for error in (baseline, endpoint, entries)),
    )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not (report["original_nonblank"] and report["passed"]
            and report["half_changed_pixels"] > 0 and report["zero_changed_pixels"] > 0
            ):
        raise RuntimeError("Opacity render regression failed; inspect report.json")


if __name__ == "__main__":
    main()
