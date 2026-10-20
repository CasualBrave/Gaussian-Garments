# Differences from Upstream Gaussian Garments

[Traditional Chinese](REALFIT3D_CHANGES.zh-TW.md) | [README](README.md)

Updated: 2026-10-20. Scope: this fork's code changes, dependencies, and validation status.

## 1. Baseline and Repository Roles

- Official source: [eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments).
- Comparison baseline: `ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`.
- This fork: changes that must live inside the GG runtime.
- [RealFit3D](https://github.com/CasualBrave/realfit3d): website, API, workflow
  orchestration, fitting workers, quality tools, and configuration.
  It pins this fork at `upstream/Gaussian-Garments` using a Git submodule.
- ContourCraft provides dynamics; ActorsHQ/GS2Mesh provides the alternative
  reconstruction pipeline. RealFit3D pins these dependencies separately.

A submodule records a specific commit. Pushing this fork does not automatically
update RealFit3D; the parent repository must also commit its updated reference.
We retain the upstream README, references, and notices. The source of each
imported component is listed below.

## 2. Adopted Code Changes

The implementation changes below were introduced in fork commit `8a52dc6`.

### 2.1 Handoff Rendering Entries

Files: [render_lean.py](render_lean.py), [render_turntable.py](render_turntable.py).

Source: `CasualBrave/frontend_temp`, commit
`2a643b1b43a0329dce23b7c40fbc2757bcfab968`.
We imported both scripts from this revision.

- `render_lean.py` renders the final panel without the original diagnostic panel
  composition and exposes a bake sample-count option.
- `render_turntable.py` renders multiple angles of one selected frame, reusing
  prepared mesh/bake outputs across angles through the existing preparation cache.
- Both entries default `--bake-samples` to 4; original `inference.py` baking
  remains at 16. The entries replace the bake function in their own process;
  they do not change the global upstream default in source.

These entries support preview rendering with configurable bake sampling.
Lower sample counts can introduce noise in the baked AO/normal maps.
GPU acceptance will compare image quality and elapsed time at 4 and 16 samples
using the same assets, frames, and camera settings.

### 2.2 Configurable Data Roots

File: [utils/defaults.py](utils/defaults.py).

| Environment variable | GG setting |
|---|---|
| `REALFIT3D_GG_DATA_ROOT` | `DEFAULTS.data_root` |
| `REALFIT3D_GG_OUTPUT_ROOT` | `DEFAULTS.output_root` |
| `REALFIT3D_GG_AUX_ROOT` | `DEFAULTS.aux_root` |

Previously these paths were source-code placeholders. They now accept environment
overrides so separate deployments do not need to edit shared code. Original
fallback placeholders and input/auxiliary-directory existence checks remain.
Deployment requires existing asset directories and configured runtime environments.

### 2.3 Simulation Input Guards

File: [inference.py](inference.py), `Simulation`.

The added checks reject:

- Empty garment-name lists or names that are non-strings, empty, `.`/`..`,
  or contain path separators.
- Empty predicted trajectories, or frames whose vertex count differs from the
  sum of the UV-template vertex counts in the provided garment order.
- Different numbers of garment (`pred`) and body (`obstacle`) frames.

These checks reject incompatible counts before rendering. Asset preparation must
also verify garment order, face indices, coordinate conventions, and appearance
checkpoint selection. The checks run after pickle loading; use trusted input
files because pickle deserialization can execute code.

## 3. Changes Deliberately Not Adopted

- Filename-based garment-name guessing from the handoff: it can select the wrong
  appearance checkpoint. RealFit3D workers write explicit garment names.
- Unrelated inference timing changes and changes to the global bake default:
  preview bake settings remain scoped to the new rendering entries.
- Experimental LBS/ICP pose transfer remains a separate research path.
- Opacity V3 and remote training modifications are scheduled for source
  comparison and compatibility validation before integration.

## 4. Stage Coverage

| Area | Current fork / integration state | Remaining work |
|---|---|---|
| S1 geometry | Original GG algorithm unchanged. RealFit3D separately pins ActorsHQ/GS2Mesh and includes handoff quality tools. | Audit remote reconstruction changes and actual selected inputs; quality tools are not all automatically wired into reconstruction. |
| S2 registration | Original GG training code. | Compare team server-side source, launch settings, and outputs against the baseline. |
| S3 appearance | Original GG training code; no V3 controller integrated. | Audit and integrate the discovered opacity implementation and compatible assets. |
| S4 dynamics | Outside this fork; RealFit3D wraps ContourCraft conversion/training. | Verify effective settings and real GPU behavior. |
| Online fitting | Handoff fitting/pin workers live in RealFit3D. | Compare real-asset behavior with the deployed handoff. |
| Rendering | New handoff entries, configurable paths, and input guards above. | Validate output quality, performance, and the complete website result path. |

## 5. Opacity V3 Integration

On 2026-10-20, read-only inspection of the remote
`iismtl5197096_actor1267_delivery_20261020` package found:

- `opacity_controller_v3_common.py`, including the actual
  `SplineOpacityController` implementation, which was read.
- V3 loading and pre-raster opacity-control branches in `inference_opacity.py`.
- Actor02 upper/lower `controller.pt` files, whose existence and hashes were
  checked. They were not deserialized or tested on a GPU.

The delivery manifest assigns learned V3 to Actor02 and direct opacity scaling
to Actor01, Actor06, and Actor07. It exposes one global opacity
value per invocation, not independent upper/lower controls.

The GitHub transparency repository provides research notes and actor scripts;
the remote delivery provides the V3 source and Actor02 controller files.
Source review and asset compatibility checks precede integration. Paths and hashes are in
the [remote discovery record](https://github.com/CasualBrave/realfit3d/blob/main/docs/REMOTE_DISCOVERY_20261020.md).

## 6. Validation and Future Updates

Source checkout/version checks and parent-project CPU/browser tests have passed.
GPU acceptance is pending. It will compare trajectories, rendered images/video,
runtime, and peak memory against the existing workflow using the same inputs.

To inspect code differences locally:

```bash
git diff --stat ceb66fc36598da05b3b3391f4562cdc54d2a2ed2 HEAD
git diff ceb66fc36598da05b3b3391f4562cdc54d2a2ed2 HEAD -- inference.py utils/defaults.py
```

For every later adopted change, update both language versions with source
path/commit or hash, purpose, behavior changes, adoption status, and tests.
Remote team directories remain read-only. Implementation changes and pushes
are made locally; any remote experiments require a separately announced
workspace under `/home/vtongroup/lin/`.
