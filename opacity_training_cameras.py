"""Read V3 training cameras without loading models or initializing CUDA."""

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise ValueError(f"Invalid camera name: {value!r}")
    return value


def _shape(value, name):
    values = np.asarray(value, dtype=float)
    if (values.shape != (2,) or not np.isfinite(values).all()
            or (values <= 0).any() or not np.equal(values, np.floor(values)).all()):
        raise ValueError(f"Camera {name}: expected positive integer [height, width]")
    return tuple(int(v) for v in values)


class TrainingCameras:
    def __init__(self, data_dir, stage2_dir, stage1_dir, limit=8, render_scale=.5, names=None):
        if not 1 <= limit <= 8 or not np.isfinite(render_scale) or not 0 < render_scale <= 1:
            raise ValueError("Camera limit must be 1-8 and render scale must be in (0, 1]")
        self.data = Path(data_dir)
        self.render_scale = render_scale
        selection_path = Path(stage2_dir) / "cameras.json"
        selection = json.loads(selection_path.read_text()) if selection_path.is_file() else None
        if selection is not None and not isinstance(selection, (dict, list)):
            raise ValueError(f"Expected a camera dictionary or rendering-camera list: {selection_path}")

        calibration_path = self.data / "cameras.json"
        if calibration_path.is_file():
            calibration = json.loads(calibration_path.read_text())
        elif isinstance(selection, dict):
            calibration_path, calibration = selection_path, selection
        else:
            calibration_path = Path(stage1_dir) / "cameras.json"
            if not calibration_path.is_file():
                raise FileNotFoundError(
                    "Full calibration with intrinsics/extrinsics is required in the input sequence "
                    f"or Stage 1; a rendering-camera list alone is insufficient: {calibration_path}")
            calibration = json.loads(calibration_path.read_text())
        if not isinstance(calibration, dict) or not calibration:
            raise ValueError(f"Expected a nonempty camera-name-keyed calibration dictionary: {calibration_path}")

        views = {}
        if isinstance(selection, list):
            for view in selection:
                if not isinstance(view, dict):
                    raise ValueError(f"Invalid rendering-camera record: {selection_path}")
                name = _name(view.get("img_name"))
                if name in views:
                    raise ValueError(f"Duplicate Stage 2 camera: {name}")
                views[name] = view
            available = sorted(views)
        elif isinstance(selection, dict):
            available = sorted(_name(name) for name in selection)
        else:
            available = sorted(_name(name) for name in calibration if (self.data / _name(name)).is_dir())
        if not available:
            raise ValueError("No selected cameras: provide Stage 2 cameras.json or calibrated image directories")
        missing = set(available) - calibration.keys()
        if missing:
            raise ValueError(f"Stage 2 cameras missing full calibration: {sorted(missing)}")

        self.params, self.shapes = {}, {}
        for name in available:
            self.params[name], self.shapes[name] = self._validate(name, calibration[name])
            if name in views:
                self._check_view(name, views[name])
        self.names = [available[i] for i in np.linspace(0, len(available) - 1,
                                                      min(limit, len(available)), dtype=int)]
        if names is not None:
            if not names or len(names) > 8 or len(set(names)) != len(names) or not set(names) <= set(available):
                raise ValueError("Camera names must be 1-8 unique calibrated Stage 2/image-directory views")
            self.names = list(names)
        self.provenance = dict(
            calibration_path=str(calibration_path),
            calibration_sha256=hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
            selection_path=str(selection_path) if selection is not None else None,
            selection_sha256=hashlib.sha256(selection_path.read_bytes()).hexdigest() if selection is not None else None,
            available_camera_count=len(available),
            image_shapes={name: list(self.shapes[name]) for name in self.names},
        )

    def _validate(self, name, params):
        if not isinstance(params, dict) or not {'intrinsics', 'extrinsics'} <= params.keys():
            raise ValueError(f"Camera {name}: missing full intrinsics/extrinsics")
        intrinsic = np.asarray(params['intrinsics'], dtype=float)
        extrinsic = np.asarray(params['extrinsics'], dtype=float)
        if (intrinsic.shape != (3, 3) or not np.isfinite(intrinsic).all()
                or intrinsic[0, 0] <= 0 or intrinsic[1, 1] <= 0
                or not np.allclose(intrinsic[2], [0, 0, 1], atol=1e-8, rtol=0)
                or not np.allclose([intrinsic[0, 1], intrinsic[1, 0]], 0, atol=1e-8, rtol=0)):
            raise ValueError(f"Camera {name}: invalid or unsupported pinhole intrinsics")
        if extrinsic.shape == (4, 4) and np.allclose(extrinsic[3], [0, 0, 0, 1], atol=1e-8, rtol=0):
            extrinsic = extrinsic[:3]
        if extrinsic.shape != (3, 4) or not np.isfinite(extrinsic).all():
            raise ValueError(f"Camera {name}: expected finite world-to-camera extrinsics")
        rotation = extrinsic[:, :3]
        if (not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-4, rtol=0)
                or not np.isclose(np.linalg.det(rotation), 1, atol=1e-4, rtol=0)):
            raise ValueError(f"Camera {name}: extrinsic rotation is not a proper rotation")
        if 'shape' in params:
            shape = _shape(params['shape'], name)
        else:
            folder = self.data / name
            images = sorted(p for p in folder.rglob('*')
                            if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg'))
            if not images:
                raise FileNotFoundError(f"Camera {name}: calibration needs shape [height, width] or an image in {folder}")
            with Image.open(images[0]) as image:
                shape = (image.height, image.width)
        return dict(params, intrinsics=intrinsic, extrinsics=extrinsic), shape

    def _check_view(self, name, view):
        required = {'width', 'height', 'fx', 'fy', 'rotation', 'position'}
        if not required <= view.keys():
            raise ValueError(f"Camera {name}: incomplete Stage 2 rendering metadata")
        params = self.params[name]
        if _shape([view['height'], view['width']], name) != self.shapes[name]:
            raise ValueError(f"Camera {name}: Stage 2 image dimensions disagree with calibration")
        focal = np.asarray([view['fx'], view['fy']], dtype=float)
        if not np.allclose(focal, [params['intrinsics'][0, 0], params['intrinsics'][1, 1]], atol=1e-3, rtol=0):
            raise ValueError(f"Camera {name}: Stage 2 focal lengths disagree with calibration")
        # GG exports camera-to-world rotation and camera center; calibration is world-to-camera.
        rotation = np.asarray(view['rotation'], dtype=float)
        position = np.asarray(view['position'], dtype=float)
        extrinsic = params['extrinsics']
        expected_rotation = extrinsic[:, :3].T
        expected_position = -expected_rotation @ extrinsic[:, 3]
        if (rotation.shape != (3, 3) or position.shape != (3,)
                or not np.allclose(rotation, expected_rotation, atol=1e-4, rtol=0)
                or not np.allclose(position, expected_position, atol=1e-4, rtol=0)):
            raise ValueError(f"Camera {name}: Stage 2 pose disagrees with calibration")

    def parameters(self, name):
        params = self.params[name]
        height, width = self.shapes[name]
        intrinsic = params['intrinsics'].copy()
        intrinsic[:2] *= self.render_scale
        extrinsic = params['extrinsics']
        return dict(R=extrinsic[:, :3].T.copy(), T=extrinsic[:, 3].copy(),
                    fx=intrinsic[0, 0], fy=intrinsic[1, 1], cx=intrinsic[0, 2], cy=intrinsic[1, 2],
                    width=max(1, round(width * self.render_scale)),
                    height=max(1, round(height * self.render_scale)), uid=params.get('ids', name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True, help='Input subject/sequence directory; may be absent for metadata-only input.')
    parser.add_argument('--stage1-dir', type=Path, required=True)
    parser.add_argument('--stage2-dir', type=Path, required=True, help='Registered sequence directory.')
    parser.add_argument('--camera-limit', type=int, choices=range(1, 9), default=8)
    parser.add_argument('--render-scale', type=float, default=.5)
    parser.add_argument('--cameras', nargs='+')
    args = parser.parse_args()
    cameras = TrainingCameras(args.data_dir, args.stage2_dir, args.stage1_dir,
                              args.camera_limit, args.render_scale, args.cameras)
    print(json.dumps(dict(camera_names=cameras.names, **cameras.provenance), indent=2))


if __name__ == '__main__':
    main()
