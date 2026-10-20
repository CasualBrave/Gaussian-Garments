# RealFit3D Integration

Baseline: eth-ait/Gaussian-Garments at
`ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`.

- `render_lean.py` and `render_turntable.py` are copied from
  CasualBrave/frontend_temp, commit `2a643b1b43a0329dce23b7c40fbc2757bcfab968`.
  They preserve the handoff rendering behavior, including reduced bake samples.
  This is not a new claim of equal visual quality or measured speedup.
- `utils/defaults.py` accepts REALFIT3D_GG_DATA_ROOT,
  REALFIT3D_GG_OUTPUT_ROOT and REALFIT3D_GG_AUX_ROOT. Existing fallback values
  remain unchanged. No machine-specific paths are committed.
- `Simulation` rejects unnamed garments, mismatched UV vertex counts and
  mismatched body/garment frame counts before rendering. The handoff's
  filename-based garment-name guessing is deliberately not adopted because
  it can select the wrong checkpoint. RealFit3D simulation workers write names.
- The handoff's unrelated inference timing changes and global bake default
  changes are not copied. Lean/turntable rendering overrides bake_texture itself.
- No S2/S3 algorithm, rasterizer or opacity controller is changed here.
  The V3 implementation and Actor02 controller files were located in a remote
  delivery on 2026-10-20, but are not integrated here. Remote training diffs
  still need an audit. Original upstream files and notices retain their provenance.

This revision has static/CPU integration checks, not GPU output parity testing.

## Stage Coverage and Evidence Boundaries

| Area | Current integration | Still to verify |
|---|---|---|
| S1 reconstruction | This fork's original S1 is unchanged. RealFit3D separately pins the ActorsHQ/GS2Mesh alternative and includes handoff quality tools. | Remote reconstruction scripts and which reviewed outputs were used; quality tools are not all automatically wired into reconstruction. |
| S2 registration | Original GG training code. | Team server-side changes, launch commands, and checkpoints have not been audited. |
| S3 appearance | Original GG training code; no team opacity V3 controller integrated. | V3 core code, inference branches, and Actor02 upper/lower controller files were found in the remote delivery on 2026-10-20. Checkpoint deserialization, compatibility, integration, and GPU testing are pending. |
| S4 dynamics | Outside this fork: RealFit3D wraps pinned ContourCraft conversion/training. | Team server-side training changes and their effective configurations. |
| Online fitting | Handoff fitting/pin workers live in RealFit3D, not this fork. | Real-asset GPU behavior and comparison with the deployed handoff. |
| Rendering | Handoff lean/turntable entries, path configuration, and trajectory guards above. | GPU image parity, quality/performance tradeoffs, and complete website output. |

After a read-only server audit, record each adopted change here with its source
path, baseline commit/diff, purpose, and validation status. A server filename
alone is not evidence that the change is implemented or integrated.

## Remote V3 Discovery: 2026-10-20

A read-only inspection of the `iismtl5197096_actor1267_delivery_20261020`
delivery found and read `opacity_controller_v3_common.py` (including
`SplineOpacityController`) and the V3 integration branches in `inference_opacity.py`.
Actor02 upper/lower `controller.pt` files exist and were hashed, not loaded.
The delivery's runtime manifest assigns learned V3 to Actor02 only; Actor01,
Actor06, and Actor07 use direct opacity scaling. This is not yet a validation
of their generated output or a completed integration into this fork.
Detailed paths and hashes are recorded in RealFit3D's
[remote discovery note](https://github.com/CasualBrave/realfit3d/blob/main/docs/REMOTE_DISCOVERY_20261020.md).
