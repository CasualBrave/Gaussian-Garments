"""Shared opacity configuration for sequence and turntable rendering."""

import math
from pathlib import Path

import torch

from opacity_controller_v3_common import load_v3

MODES = ("original", "direct", "optical_depth", "v3")


def add_opacity_arguments(parser):
    parser.add_argument("--opacity-mode", "--opacity_mode", choices=MODES, default="original")
    parser.add_argument("--opacity-scale", "--opacity_scale", type=float, default=1.0,
                        help="0 hides garments; 1 preserves the original Gaussian opacity.")
    parser.add_argument("--v3-controller", "--v3_controller", action="append", default=[],
                        metavar="GARMENT=PATH", help="Repeat once per garment for V3.")


class GarmentOpacity:
    def __init__(self, args, garment_names, model_root, device="cuda"):
        self.mode = getattr(args, "opacity_mode", "original")
        self.scale = float(getattr(args, "opacity_scale", 1.0))
        if self.mode not in MODES or not math.isfinite(self.scale) or not 0 <= self.scale <= 1:
            raise ValueError("Opacity mode or scale is invalid")
        if self.mode == "original" and self.scale != 1:
            raise ValueError("Select direct, optical_depth or v3 to change opacity")
        paths = {}
        for entry in getattr(args, "v3_controller", []) or []:
            name, separator, path = entry.partition("=")
            if not separator or not path or name not in garment_names or name in paths:
                raise ValueError(f"Invalid or duplicate V3 mapping: {entry}")
            paths[name] = Path(path).expanduser()
        if paths and self.mode != "v3":
            raise ValueError("V3 controller mappings require --opacity-mode v3")
        self.controllers = []
        if self.mode == "v3":
            for name in garment_names:
                path = paths.get(name)
                if path is None:
                    candidates = [Path(model_root) / name / folder / "controller.pt" for folder in
                                  ("opacity_controller_v3", "opacity_controller_v3_valid_cameras")]
                    existing = [p for p in candidates if p.is_file()]
                    if len(existing) != 1:
                        raise ValueError(f"Specify --v3-controller {name}=PATH; found {len(existing)} candidates")
                    path = existing[0]
                self.controllers.append(load_v3(path, device=device, subject=name))

    def apply(self, garments):
        result = []
        for index, garment in enumerate(garments):
            base = garment.get_opacity
            # Exact endpoints preserve the existing renderer, including alpha=1.
            if self.scale == 1:
                alpha = base
            elif self.scale == 0:
                alpha = torch.zeros_like(base)
            elif self.mode == "direct":
                alpha = base * self.scale
            elif self.mode == "optical_depth":
                alpha = -torch.expm1(self.scale * torch.log1p(-base.clamp(0, 1 - 1e-7)))
            elif self.mode == "v3":
                controller, checkpoint = self.controllers[index]
                xyz = (garment.get_xyz - checkpoint["canonical_center"]) / checkpoint["canonical_scale"]
                alpha = controller(base, xyz, self.scale)[0]
            else:
                alpha = base
            result.append(alpha)
        return torch.cat(result)
