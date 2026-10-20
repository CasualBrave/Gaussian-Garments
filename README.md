# Gaussian garments: Reconstructing simulation-ready clothing with photorealistic appearance from multi-view video

## 與原版的差異 / Differences from Upstream

### 中文

這是 RealFit3D 維護的 GG 整合 fork，不是原作者的官方版本。
比較基準為 [eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments)
的 `ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`。
**這個 fork 目前只包含下列渲染與整合修改，不是組員所有實驗的完整集合。**

| 範圍 | 已合併的差異 | 來源與限制 |
|---|---|---|
| `render_lean.py`、`render_turntable.py` | 新增精簡渲染與轉盤渲染入口，採用較低的 bake 採樣設定 | 沿用組員 frontend_temp 交付程式，不是本次新發明的算法；未驗證等畫質或實際加速幅度 |
| `utils/defaults.py` | 支援 `REALFIT3D_GG_DATA_ROOT`、`REALFIT3D_GG_OUTPUT_ROOT`、`REALFIT3D_GG_AUX_ROOT` 環境變數 | 避免在共用程式寫死每台機器的資料路徑；保留原本 fallback |
| `inference.py` 的 `Simulation` | 拒絕缺少衣物名稱、UV 頂點數不符、人體與衣物幀數不符的輸入 | 基本相容性檢查，不等於完整幾何或 checkpoint 語意驗證 |
| Stage 1 / 2 / 3 訓練核心 | **未修改原版算法** | 組員伺服器上的相關實驗修改仍待逐項比對，不宣稱已全部整合 |
| 透明度 V3 | **尚未合併** | 2026-10-20 已在遠端交付找到 controller 程式與 Actor02 上下衣權重，但尚未遷入此 fork 或執行 GPU 驗收 |
| Stage 4、網站、身形適配與品質工具 | 不放在此 GG fork | 由 [RealFit3D 主專案](https://github.com/CasualBrave/realfit3d)整合 ContourCraft、ActorsHQ 與本組 worker |

**最新查核做了什麼：**只讀取遠端程式、交付設定與計算少量檔案雜湊，
再於本機更新文件並推送。沒有改動遠端小組資料、沒有下載並整合透明度程式，
也沒有載入模型或跑 GPU。交付設定只有 Actor02 標為 learned V3；
Actor01 / 06 / 07 使用 direct opacity，不可混稱 V3。

原始碼版本一致性與 CPU／網頁整合檢查已完成，但不代表 GPU 試衣流程已通過。
詳細來源、尚未採用的改動及證據範圍見 [修改紀錄](REALFIT3D_CHANGES.md)；
遠端發現見 [唯讀查核紀錄](https://github.com/CasualBrave/realfit3d/blob/main/docs/REMOTE_DISCOVERY_20261020.md)。

### English

This is the RealFit3D integration fork, not the original authors' official release.
The upstream baseline is `eth-ait/Gaussian-Garments` at
`ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`.
**This fork contains the integration changes below, not every team experiment.**

| Area | Adopted change | Provenance and limits |
|---|---|---|
| `render_lean.py`, `render_turntable.py` | Added lean and turntable rendering entries with reduced bake sampling | Reused from the frontend_temp handoff; not a newly invented algorithm or a verified equal-quality speedup |
| `utils/defaults.py` | Added `REALFIT3D_GG_DATA_ROOT`, `REALFIT3D_GG_OUTPUT_ROOT`, `REALFIT3D_GG_AUX_ROOT` environment overrides | Avoids machine-specific source edits; original fallback values remain |
| `Simulation` in `inference.py` | Rejects missing garment names, mismatched UV vertex counts, and unequal body/garment frame counts | Basic compatibility checks, not full geometry or checkpoint validation |
| Stage 1 / 2 / 3 training core | **Original algorithms unchanged** | Team server-side experiment changes still need individual comparison; they are not all integrated |
| Opacity V3 | **Not integrated** | Remote controller code and Actor02 upper/lower weights were located on 2026-10-20; migration and GPU validation are pending |
| Stage 4, website, fitting, quality tools | Outside this GG fork | Orchestrated by [RealFit3D](https://github.com/CasualBrave/realfit3d) with ContourCraft, ActorsHQ, and team workers |

**Latest inspection:** read remote source/configuration and hashed a few files,
then updated and pushed documentation from the local machine. It did not modify
remote team data, download and integrate opacity code, load models, or run GPU
experiments. The delivery configuration labels only Actor02 as learned V3;
Actor01 / 06 / 07 use direct opacity instead.

Source-version and CPU/web integration checks do not establish GPU end-to-end
correctness. See [REALFIT3D_CHANGES.md](REALFIT3D_CHANGES.md) for source commits,
omitted changes, and validation boundaries, and the
[read-only discovery record](https://github.com/CasualBrave/realfit3d/blob/main/docs/REMOTE_DISCOVERY_20261020.md)
for the remote evidence.

## 原版使用文件 / Original Upstream Documentation

The original upstream usage documentation follows.

### <img align=center src=./static/icons/project.png width='32'/> [Project](https://ribosome-rbx.github.io/Gaussian-Garments/) &ensp; <img align=center src=./static/icons/paper.png width='24'/> [Paper](https://arxiv.org/abs/2409.08189) &ensp;  

This is a repository for the paper [**"Gaussian garments: Reconstructing simulation-ready clothing with photorealistic appearance from multi-view video"**](https://ribosome-rbx.github.io/Gaussian-Garments/) (3DV2025).

This repository contains the implementation of the three stages described in the paper:
1. Geometry reconstruction (`s1_initiallisation.py`)
2. Garment registration (`s2_registration.py`)
3. Appearance reconstruction (`s3_appearance.py`)

This Readme file describes steps to 
* [Install the environment](#installation) 
* [Prepare input data for garment reconstruction](#data-preparation)
* [Create new Gaussian garments](#creating-new-gaussian-garments), and
* [Render the sequences of garment motions](#inference)

Unfortunately, we can not share the full data used in the paper. Hence, we have prepared the code for running Gaussian Garments algorithm on [ActorsHQ](https://actors-hq.com/) dataset. Notably, we found that the first stage used in the paper does not produce satysfying results on ActorsHQ, so we have prepared an alternative solution in the repository [ActorsHQ-for-Gaussian-Garments](https://github.com/hlimach/ActorsHQ-for-Gaussian-Garments).

**Follow instructions in [ActorsHQ-for-Gaussian-Garments](https://github.com/hlimach/ActorsHQ-for-Gaussian-Garments) to convert data from ActorsHQ into our format and reconstruct the garment mesh.** Then, you can continue from the stage 2 in this repository.

## Installation
To install the environment with all the required libraries, use the `setup.sh` script:
```bash
bash setup.sh
```
In case you encounter errors while running this script, we recommend running the lines from the script manually one by one to isolate the issue.

After the installation, you can activate the environment with
```bash
conda activate gaugar
```

## Data Preparation
This repository assumes three key data locations:
* Input folder
* Output folder
* Auxilliary data folder

Refer to [DataPreparation.md](DataPreparation.md) for the instructions on how to set up these folders.

Then, your first step is to set paths to these three locations in `utils/defaults.py`:
```python
DEFAULTS['data_root'] = '/path/to/input/folder'
DEFAULTS['output_root'] = '/path/to/output/folder'
DEFAULTS['aux_root'] = '/path/to/auxilliary/data/folder'
```



## Creating new Gaussian garments
To reconstruct a new Gaussian garment from multi-view videos, you'll need to run three stages: (1) initialize the geomentry from a single frame, (2) register this geometry to all multi-view videos, and (3) train an appearance model to reconstruct the garment's appearance. Here we'll describe each of these steps.

Before running the reconstruction, make sure you have followed instructions in [DataPreparation.md](DataPreparation.md) and your input and auxilliary folders hava the same structure as described there.

All three steps share the same argument names:
* `-s/--subject`: name of the subject in the input folder (`DEFAULTS.data_root/*subject_id*`)
* `-so/--subject_out`: name of the directory in the output folder where the results will be stored (`DEFAULTS.output_root/*subject_out_id*`). If not set, the same name as in `--subject` is used
* `-q/--sequence`: name of the sequence to use. There may be more than one sequence for one subject. (`DEFAULTS.data_root/*subject_id*/*sequence_id*`)
* `-tf/--template_frame`: the number of the template frame in the sequence. By default `-tf 0` is used.

### Step 1: Geometry initialization
*Note: if you want to run Gaussian Garments for ActorsHQ or another dataset for which the 1st stage described in the paper produces unsatisfying results, refer to [ActorsHQ-for-Gaussian-Garments](https://github.com/hlimach/ActorsHQ-for-Gaussian-Garments) repository. After reconstructing the geometry with that repo, procede directly with Step 2.*

Assuming you have correct structure of the input folder, to reconstruct the garment geometry from a template frame, run:
```bash
python s1_initialisation.py -s *subject_id* -q *sequence_id* -tf *template_frame_id*
```
For the template frame, use the one where the whole surface of the garment is fully visible and where the pose is similar to the first frame of each sequence.

This script will generate the folder `DEFAULTS.output_root/*subject_id*/stage1`, where the reconstructed template will be stored in `template.obj`.

The final action in this step is to create a UV unwrapping for the template mesh. **This have to be done manually.** You can use Blender and follow [this YouTube guide](https://www.youtube.com/watch?v=LqJGD6yjlDE). **Save the .obj file of the mesh with the UV unwrapping to `DEFAULTS.output_root/*subject_id*/stage1/template_uv.obj`**

### Step 2: Garment registration
Once you have a garment template with uv unwrapping, you can register it to the multi-view videos. This process has two substeps.

First, we need to initialize the appearance of the garment. You can do this with this script:

*(Note that in the paper appearance initialization is described as a part of stage 1)*
```bash
python s2_registration.py -s *subject_id* -q *sequence_id*  -tf *template_frame_id*
```
You'll need to use the same sequence and template frame as in Step 1.

This will optimize the initial appearance and geometry for a single frame and save them into `DEFAULTS.output_root/*subject_id*/stage2/Template/`

Then, register this template to all sequences of this subject:
```bash
python s2_registration.py -s *subject_id* -q *sequence_id* 
python s2_registration.py -s *subject_id* -q *sequence_id2*
... 
```
This will produce registered meshes for each frame and save them into `DEFAULTS.output_root/*subject_id*/stage2/*sequence_id*/meshes/`. To check if it is running correctly, see the renders in `DEFAULTS.output_root/*subject_id*/stage2/*sequence_id*/renders/`.

Registering geometry to one frame takes a few minutes.


### Step 3: 
Finally, optimize the albedo texture and the appearance model using all registered sequences:
```bash
python s3_appearance.py -s *subject_id* 
```
This will store the training checkpoint into `DEFAULTS.output_root/*subject_id*/stage3/ckpt/`

### Step 4 and creating trajectories:
In step 4, we optimize the behavior of the garment by finetuning a ContourCraft graph neural network.

To perform this step, please refer to the [ContourCraft](https://github.com/Dolorousrtur/ContourCraft/) repository and specifically to [this notebook](https://github.com/Dolorousrtur/ContourCraft/blob/main/GaussianGarments.ipynb). This notebook also shows how to simulate the garments with ContourCraft in order to create trajectory files needed to run the inference step of Gaussian Garments.

Note that you will need to follow the [installation instructions for ContourCraft](https://github.com/Dolorousrtur/ContourCraft/blob/main/INSTALL.md) before running the finetuning process.


### Inference
To render a dynamic sequence of Gaussian garment geometries, use `inference.py` script:
```bash
python inference.py --traj_path *trajectory_file*.pkl --output_path *directory_to_store_renders*
``` 

Here, `trajectory_file` is a path to a `.pkl` file containing trajectories of the garments and the body meshes. They follow the structure of the trajectory files produced by [ContourCraft](https://github.com/dolorousrtur/ContourCraft) and contain a dictionary with the following elements:

* `pred`: 3D positions of garment vertices in each frame, np.array of shape [N, V, 3], where N is the number of frames and V is the number of the garment vertices.
* `cloth_faces`: faces of the garment meshes, np.array of shape [F, 3]
* `obstacle`: 3D positions of body vertices in each frame, np.array of shape [N, B, 3], where N is the number of frames and B is the number of the body vertices.
* `obstacle_faces`: faces of the body mesh, np.array of shape [Fb, 3]
* `garment_names`: a list of subject names for the garments used in the trajectory. The subject names should correspond to the folders in your `DEFAULTS.output_root` directory. 

A trajectory file may contain a trajectory for a multi-garment outfit comprised of several garments. In this case, 

* `pred` is a concatenation of vertex positions for all garments, 
* `cloth_faces` is the concatenation of their faces with properly renumerated vertex ids, and 
* `garment_names` is the list of subject names in the same order as the garments are concatenated in.

The script `inference.py` will check the  `garment_names` list and load the corresponding checkpoints stored in your `DEFAULTS.output_root` directory. 

See the link to examples of the trajectory files below.

#### Render sequences from the supplementary video
You can download the trajectory files used in the supplementary video [here](https://drive.google.com/file/d/1VoCmCfL-YmWL4BsgcdN8gxcEt3djJp-v/view?usp=drive_link).

To render them, you will need to download checkpoints of the Gaussian Garments used in the paper [here](https://drive.google.com/file/d/1EnmIQQ3BIN9nqykhEAOv18R5mH1eq5fx/view?usp=sharing). Unpack them to your `DEFAULTS.output_root` so that its structure is:

```
DEFAULTS.output_root/
├── 00122_outer/
├── 00134_upper/
└── ...
```

Then, you will be able to render the trajectories with the command above.
