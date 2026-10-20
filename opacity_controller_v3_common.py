"""Eight-bin monotonic opacity controller, compatible with the V3 checkpoints."""

from pathlib import Path

import torch
from torch import nn

K_BINS = 8
SPLINE_EPS = 1e-6


class SplineOpacityController(nn.Module):
    def __init__(self, bins=K_BINS, eps=SPLINE_EPS):
        super().__init__()
        self.bins, self.eps = bins, eps
        self.net = nn.Sequential(
            nn.Linear(4, 32), nn.SiLU(), nn.Linear(32, 32), nn.SiLU(), nn.Linear(32, bins)
        )
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def bin_probabilities(self, base_alpha, canonical_xyz_norm):
        logits = self.net(torch.cat((base_alpha, canonical_xyz_norm), dim=-1))
        weights = torch.nn.functional.softplus(logits) + self.eps
        return weights / weights.sum(dim=-1, keepdim=True)

    def exponent(self, probabilities, s):
        s = torch.as_tensor(s, device=probabilities.device, dtype=probabilities.dtype)
        if s.numel() != 1:
            raise ValueError("V3 expects a scalar requested opacity")
        s = s.reshape(())
        u = s * self.bins
        k = torch.floor(u).long().clamp(0, self.bins - 1)
        frac = u - k.to(u.dtype)
        cumulative = probabilities.cumsum(dim=-1) - probabilities
        index = k.reshape(1, 1).expand(probabilities.shape[0], 1)
        m = cumulative.gather(1, index) + frac * probabilities.gather(1, index)
        m = torch.where(s <= 0, torch.zeros_like(m), m)
        return torch.where(s >= 1, torch.ones_like(m), m)

    def forward(self, base_alpha, canonical_xyz_norm, s):
        probabilities = self.bin_probabilities(base_alpha, canonical_xyz_norm)
        m = self.exponent(probabilities, s)
        safe = base_alpha.clamp(1e-6, 1 - 1e-6)
        controlled = -torch.expm1(m * torch.log1p(-safe))
        s = torch.as_tensor(s, device=base_alpha.device, dtype=base_alpha.dtype)
        controlled = torch.where(s <= 0, torch.zeros_like(controlled), controlled)
        controlled = torch.where(s >= 1, base_alpha, controlled)
        return controlled.clamp(0, 1), probabilities, m


def save_v3(path, controller, center, scale, step, config):
    torch.save(dict(controller=controller.state_dict(), canonical_center=center.detach().cpu(),
                    canonical_scale=scale.detach().cpu(), step=step, config=config), path)


def load_v3(path, device="cuda", subject=None):
    checkpoint = torch.load(Path(path), map_location=device, weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("V3 checkpoint must be a dictionary")
    config = checkpoint.get("config", {})
    if not isinstance(config, dict):
        raise ValueError("V3 config must be a dictionary")
    if subject and config.get("subject") not in (None, subject):
        raise ValueError(f"V3 checkpoint belongs to {config.get('subject')}, not {subject}")
    for key in ("canonical_center", "canonical_scale"):
        value = checkpoint.get(key)
        if not isinstance(value, torch.Tensor) or value.shape != (3,) or not torch.isfinite(value).all():
            raise ValueError(f"V3 requires a finite three-vector: {key}")
    if not (checkpoint["canonical_scale"] > 0).all():
        raise ValueError("V3 canonical_scale must be positive")
    controller = SplineOpacityController().to(device)
    controller.load_state_dict(checkpoint["controller"], strict=True)
    if not all(torch.isfinite(p).all() for p in controller.parameters()):
        raise ValueError("V3 controller contains non-finite weights")
    controller.requires_grad_(False).eval()
    return controller, checkpoint
