"""Train V3 after Stage 3, keeping the mesh and appearance weights frozen."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image
import torch

from diff_gaussian_rasterization_depth_alpha import GaussianRasterizationSettings, GaussianRasterizer
from opacity_controller_v3_common import K_BINS, SplineOpacityController, save_v3
from opacity_training_cameras import TrainingCameras
from scene import AvatarGaussianModel, AvatarNet
from scene.cameras import Camera
from utils.defaults import DEFAULTS
from utils.graphics_utils import focal2fov
from utils.io_utils import read_obj


class TrainingData:
    def __init__(self, subject, sequence, cameras, render_scale, camera_names=None):
        self.data = Path(DEFAULTS.data_root) / subject / sequence
        self.stage2 = Path(DEFAULTS.output_root) / subject / DEFAULTS.stage2 / sequence
        self.camera_source = TrainingCameras(self.data, self.stage2,
            Path(DEFAULTS.output_root) / subject / 'stage1', cameras, render_scale, camera_names)
        self.names = self.camera_source.names
        self.frames, self.cameras = {}, {}

    def camera(self, name):
        if name not in self.cameras:
            params = self.camera_source.parameters(name)
            width, height = params.pop('width'), params.pop('height')
            self.cameras[name] = Camera(
                **params, FoVx=focal2fov(params['fx'], width), FoVy=focal2fov(params['fy'], height),
                colmap_id=None, image_name=name, image=torch.zeros(3, height, width),
                gt_alpha_mask=torch.zeros(1, height, width), data_device="cuda",
            )
        return self.cameras[name]

    def frame_paths(self, frame):
        name = f"frame_{frame:05d}"
        return (self.stage2 / "meshes" / f"{name}.obj",
                self.stage2 / "texture/ambient" / f"{name}.png",
                self.stage2 / "texture/normal" / f"{name}.png")

    def validate(self, frames):
        for frame in frames:
            for path in self.frame_paths(frame):
                if not path.is_file():
                    raise FileNotFoundError(path)

    def frame(self, frame):
        if frame not in self.frames:
            mesh, ambient, normal = self.frame_paths(frame)
            vertices = torch.as_tensor(read_obj(mesh)["vertices"], dtype=torch.float32)
            with Image.open(ambient) as image:
                ao = torch.from_numpy(np.asarray(image.convert("L"), dtype=np.float32) / 255).unsqueeze(0)
            with Image.open(normal) as image:
                normals = torch.from_numpy(np.asarray(image.convert("RGB"), dtype=np.float32) / 255).permute(2, 0, 1)
            self.frames[frame] = vertices, ao, normals
        return self.frames[frame]


@torch.no_grad()
def render_state(gaussians, avatar, data, frame, camera_name):
    vertices, ambient, normal = data.frame(frame)
    gaussians.mesh.v = vertices.cuda()
    gaussians.update_face_coor()
    _, visible = avatar(ambient.cuda(), normal.cuda(), data.camera(camera_name))
    return tuple(value.detach() for value in
                 (gaussians.get_final_xyz, gaussians.get_scaling, gaussians.get_rotation, visible))


def render_alpha(camera, state, opacity):
    xyz, scales, rotations, visible = state
    xyz = xyz[visible]
    settings = GaussianRasterizationSettings(
        image_height=int(camera.image_height), image_width=int(camera.image_width),
        tanfovx=math.tan(camera.FoVx / 2), tanfovy=math.tan(camera.FoVy / 2),
        bg=torch.zeros(3, device=opacity.device), scale_modifier=1.0,
        viewmatrix=camera.world_view_transform, projmatrix=camera.full_proj_transform,
        sh_degree=0, campos=camera.camera_center, prefiltered=False, debug=False,
    )
    _, _, _, alpha = GaussianRasterizer(raster_settings=settings)(
        means3D=xyz, means2D=torch.zeros_like(xyz, requires_grad=opacity.requires_grad),
        shs=None, colors_precomp=torch.ones_like(xyz), opacities=opacity[visible],
        scales=scales[visible], rotations=rotations[visible], cov3D_precomp=None,
    )
    return alpha


def foreground_l1(prediction, target, original):
    mask = original > 1e-3
    if not mask.any():
        raise ValueError("Alpha render has no foreground")
    weights = mask.float() + .25 * original
    return (weights * (prediction - target).abs()).sum() / weights.sum().clamp_min(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--sequence", default="Sequence1")
    parser.add_argument("--output", type=Path, help="New directory; existing directories are never overwritten.")
    parser.add_argument("--steps", type=int, default=5000)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=31359)
    parser.add_argument("--render-scale", type=float, default=.5)
    parser.add_argument("--camera-limit", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--cameras", nargs="+", help="Explicit calibrated camera names, overriding camera-limit.")
    parser.add_argument("--train-frames", type=int, nargs="+", default=list(range(30)))
    parser.add_argument("--validation-frames", type=int, nargs="+", default=list(range(30, 40)))
    args = parser.parse_args(argv)
    if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) for value in (args.subject, args.sequence)):
        parser.error("Invalid subject or sequence")
    if args.steps < 1 or not math.isfinite(args.lr) or args.lr <= 0 or not 0 < args.render_scale <= 1:
        parser.error("Invalid steps, learning rate or render scale")
    if min(args.train_frames + args.validation_frames) < 0 or set(args.train_frames) & set(args.validation_frames):
        parser.error("Training and validation frames must be non-negative and disjoint")
    if not torch.cuda.is_available():
        raise RuntimeError("V3 training requires CUDA")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    output_root = Path(DEFAULTS.output_root) / args.subject
    output = args.output or output_root / "opacity_controller_v3"
    if output.exists():
        raise FileExistsError(f"Choose a new --output directory: {output}")
    data = TrainingData(args.subject, args.sequence, args.camera_limit, args.render_scale, args.cameras)
    data.validate(args.train_frames + args.validation_frames)
    if not any((output_root / DEFAULTS.stage2).glob("*/point_cloud/frame_*/point_cloud.ply")):
        raise FileNotFoundError("Stage 2 point_cloud/frame_*/point_cloud.ply is required to initialize GG")
    model_args = SimpleNamespace(subject=args.subject, subject_out=args.subject, sh_degree=3,
                                 texture_size=512, texture_margin=5, debug=False, eval=True)
    gaussians = AvatarGaussianModel(model_args)
    avatar = AvatarNet(model_args, gaussians).cuda()
    epoch = avatar.load_ckpt(str(output_root / DEFAULTS.stage3), load_optm=False)
    avatar.requires_grad_(False).eval()
    base, xyz = gaussians.get_opacity.detach(), gaussians.get_xyz.detach()
    center, scale = xyz.mean(0), xyz.std(0).clamp_min(1e-6)
    xyz = ((xyz - center) / scale).detach()
    controller = SplineOpacityController().cuda()
    optimizer = torch.optim.Adam(controller.parameters(), lr=args.lr)
    checkpoint_path = output_root / DEFAULTS.stage3 / "ckpt/net.pt"
    digest = hashlib.sha256()
    with checkpoint_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    config = dict(subject=args.subject, sequence=args.sequence, stage3_epoch=int(epoch),
                  stage3_sha256=digest.hexdigest(), train_frames=args.train_frames,
                  validation_frames=args.validation_frames, camera_names=data.names,
                  camera_source=data.camera_source.provenance,
                  steps=args.steps, learning_rate=args.lr, render_scale=args.render_scale,
                  seed=args.seed, bins=K_BINS, s_sampling=[.05, .95],
                  loss_weights=dict(cal=1, reg=.001))
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    start = time.perf_counter()
    with (output / "train_log.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["step", "loss_cal", "loss_reg", "requested_s"])
        for step in range(1, args.steps + 1):
            frame, camera_name = random.choice(args.train_frames), random.choice(data.names)
            state = render_state(gaussians, avatar, data, frame, camera_name)
            camera = data.camera(camera_name)
            with torch.no_grad():
                original = render_alpha(camera, state, base)
            s = random.uniform(.05, .95)
            opacity, probabilities, _ = controller(base, xyz, s)
            calibration = foreground_l1(render_alpha(camera, state, opacity), s * original, original)
            regularization = (probabilities - 1 / K_BINS).square().mean()
            loss = calibration + .001 * regularization
            if not torch.isfinite(loss):
                raise FloatingPointError(f"Non-finite loss at step {step}")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            if any(p.grad is None or not torch.isfinite(p.grad).all() for p in controller.parameters()):
                raise FloatingPointError(f"Invalid controller gradients at step {step}")
            optimizer.step()
            writer.writerow([step, float(calibration.detach()), float(regularization.detach()), s])
            if step % 100 == 0:
                handle.flush()
                print(f"step={step} calibration={float(calibration.detach()):.6f}", flush=True)
    controller.eval()
    rows = []
    with torch.no_grad():
        for index, frame in enumerate(args.validation_frames):
            name = data.names[index % len(data.names)]
            state = render_state(gaussians, avatar, data, frame, name)
            camera = data.camera(name)
            original = render_alpha(camera, state, base)
            for s in (.25, .5, .75):
                predicted = render_alpha(camera, state, controller(base, xyz, s)[0])
                rows.append(dict(frame=frame, camera=name, s=s,
                                 alpha_mae=float(foreground_l1(predicted, s * original, original))))
    (output / "validation.json").write_text(json.dumps(rows, indent=2) + "\n")
    save_v3(output / "controller.pt", controller, center, scale, args.steps, config)
    torch.cuda.synchronize()
    summary = dict(steps=args.steps, seconds=time.perf_counter() - start,
                   trainable_parameters=sum(p.numel() for p in controller.parameters()))
    (output / "training_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
