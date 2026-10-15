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
  The reported V3 opacity implementation and remote training diffs have not
  been delivered. Original upstream files and notices retain their provenance.

This revision has static/CPU integration checks, not GPU output parity testing.
