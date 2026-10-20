# RealFit3D Changes to Gaussian Garments

[Traditional Chinese](REALFIT3D_CHANGES.zh-TW.md) | [README](README.md)

## Role in the Try-On Pipeline

ContourCraft produces a sequence of body and garment meshes. GG combines those
moving meshes with a trained garment appearance model to render images.
RealFit3D assembles the images into the website's turntable preview and video.

```text
Body and garment trajectories + UV templates + Stage 3 appearance checkpoints
    -> GG rendering
    -> turntable PNGs or animation frames
    -> RealFit3D preview and video
```

We maintain this fork against
[eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments),
baseline `ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`.
RealFit3D pins it as the `upstream/Gaussian-Garments` submodule.
The changes described below concern rendering entries, configuration, and input
validation. The original S1 reconstruction, S2 registration, and S3 training
algorithms are unchanged in this revision.

## Rendering a Simulated Garment

For each frame, GG takes the simulated garment vertices and the body's position.
It places the garment Gaussians on the deformed mesh and prepares two UV maps
with Blender: an ambient occlusion (AO) map describing how surrounding surfaces
occlude the garment, and a normal map describing surface directions. The trained
AvatarNet uses these maps and the camera to update the garment's appearance.
GG then evaluates visibility, rasterizes the Gaussians, and composites the garment
with the body to produce the final image.

```text
Frame meshes -> UV AO/normal maps -> AvatarNet appearance update
             -> visibility and Gaussian rasterization -> composited image
```

This rendering stage uses an existing Stage 3 checkpoint; it does not retrain
the appearance model for each frame.

### Final-Image Rendering

[render_lean.py](render_lean.py) uses the same mesh preparation and appearance
model as `inference.py`, but renders only the final composited image.
The original entry also renders raw/style comparison panels and combines them
into a diagnostic image. Removing those extra panels reduces rendering and image
assembly work while retaining the image used by the website.

Run from this repository with the GG Python environment and configured data roots:

```bash
python render_lean.py \
  --traj_path /path/to/trajectory.pkl \
  --output_path /path/to/new-render-directory \
  --bake-samples 4
```

The output is a sequence of frame images. RealFit3D's preview worker assembles
these frames into an MP4.

### Turntable Rendering

[render_turntable.py](render_turntable.py) selects one simulated frame and moves
the camera around it. The mesh and UV AO/normal maps stay the same across angles,
so their cached files are reused. The appearance network, visibility calculation,
and rasterization are evaluated for each camera because the visible surface and
view-dependent appearance change with the angle.

```bash
python render_turntable.py \
  --traj_path /path/to/trajectory.pkl \
  --output_path /path/to/new-turntable-directory \
  --frame_idx 4 --n-angles 12 --bake-samples 4
```

The resulting PNGs let the website show several views of the outfit before the
full animation is ready.

### Bake Sampling

Blender baking converts the current 3D surface information into the UV maps used
by AvatarNet. `--bake-samples` sets the Cycles sampling budget for this step.
The new entries default to 4, compared with 16 in the original `inference.py`.
A lower setting reduces the bake sampling budget and can increase AO-map noise.
Both entries retain the existing 512 x 512 map dimensions expected by the model.
Changing this option does not change the simulation or retrain the checkpoint.

## Selecting Data and Models

We added environment-variable overrides to [utils/defaults.py](utils/defaults.py)
so RealFit3D can select the input data, trained garment assets, and auxiliary
models for each deployment without editing GG source files.

| Variable | Contents |
|---|---|
| `REALFIT3D_GG_DATA_ROOT` | GG input data |
| `REALFIT3D_GG_OUTPUT_ROOT` | Reconstructed garment assets and trained appearance checkpoints |
| `REALFIT3D_GG_AUX_ROOT` | Auxiliary models and data |

The renderer loads each named garment's `stage1/template_uv.obj`,
`stage1/cameras.json`, and `stage3/ckpt/net.pt` from the asset root.
Rendered media goes to the command's `--output_path`.

## Checking the Trajectory

The trajectory stores multiple garments in a single vertex sequence.
Its `garment_names` order tells `Simulation` which UV template and appearance
model belong to each portion of that sequence. Before rendering, our checks
require valid names, a nonempty predicted sequence, the expected total vertex
count in every frame, and matching body/garment frame counts.
An incompatible input stops with an error before rendering.

Names are supplied explicitly by the simulation worker rather than inferred
from the trajectory filename. Asset preparation also needs matching face/UV
indices and coordinate conventions. Use trusted pickle files: deserialization
occurs before these checks.

## Opacity Control

The team's separate opacity runtime applies control before Gaussian
rasterization. In `direct` mode it multiplies each Gaussian's base opacity by
one requested scale. In V3, a small network takes the base opacity and normalized
canonical position and produces eight positive, normalized weights. These define
a monotonic piecewise-linear function of the requested scale; its output changes
the Gaussian opacity before the same rasterization step.

The delivered runtime assigns learned V3 to Actor02 and direct scaling to
Actor01, Actor06, and Actor07. V3 source and Actor02 controller files are located;
they are not yet included in this fork. Training-source review and integration
are tracked in the maintainer notes.

## Version and Validation

The rendering entries, path overrides, and input checks were introduced in
`8a52dc6`. Source-version checks and RealFit3D's CPU/browser tests have passed.
End-to-end GPU rendering validation is pending.

For development and version updates, see
[RealFit3D's development guide](https://github.com/CasualBrave/realfit3d/blob/main/docs/DEVELOPMENT.md).
