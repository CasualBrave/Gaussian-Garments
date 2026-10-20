# RealFit3D 對 Gaussian Garments 的修改

[English](REALFIT3D_CHANGES.md) | [README](README.md)

## 在試衣流程中的位置

ContourCraft 先算出人體與衣物逐幀移動的 mesh；GG 將這些形狀與訓練好的
衣物外觀模型結合，渲染成圖片。RealFit3D 再把圖片組成網站上的多角度預覽與影片。

```text
人體與衣物軌跡 + UV 模板 + Stage 3 外觀 checkpoint
    → GG 渲染
    → 多角度 PNG 或動畫影格
    → RealFit3D 網頁預覽與影片
```

此 fork 以 [eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments)
的 `ceb66fc36598da05b3b3391f4562cdc54d2a2ed2` 為基準，
由 RealFit3D 透過 `upstream/Gaussian-Garments` submodule 固定版本。
以下修改集中在渲染入口、路徑設定與輸入檢查；
此版本的 S1 重建、S2 registration、S3 訓練算法維持原版。

## 模擬結果如何變成衣物圖片

每一幀先讀入模擬算出的衣物頂點與人體位置。GG 讓附著於衣物表面的
Gaussians 隨 mesh 變形，再用 Blender 將當前幾何資訊轉成兩張 UV 貼圖：
AO 貼圖描述衣物受到周圍表面遮蔽的程度，normal 貼圖記錄衣物表面的朝向。
訓練好的 AvatarNet 讀取這兩張貼圖和相機資訊，更新衣物外觀。
最後計算哪些 Gaussians 可見，將它們光柵化成像素，再與人體影像合成。

```text
當前幀的 mesh → UV 遮蔽／法線貼圖 → AvatarNet 更新外觀
             → 可見性計算與 Gaussian 光柵化 → 人體與衣物合成圖
```

這個階段使用已訓練好的 Stage 3 checkpoint，每幀只進行推論。

### 只輸出最終畫面

[render_lean.py](render_lean.py) 保留 `inference.py` 的幾何處理與外觀模型，
只渲染網站需要的最終合成圖。原版入口還會另外渲染 raw／style 比較畫面，
並拼成診斷圖片；我們省去這些額外畫面及拼接工作，輸出動畫需要的逐幀圖片。

在此 repo 目錄內，使用 GG 的 Python 環境並設定好資料路徑後執行：

```bash
python render_lean.py \
  --traj_path /path/to/trajectory.pkl \
  --output_path /path/to/new-render-directory \
  --bake-samples 4
```

輸出是一系列影格圖片，接著由 RealFit3D 的預覽 worker 組成 MP4。

### 同一幀產生多角度預覽

[render_turntable.py](render_turntable.py) 選定模擬中的一幀，
固定衣物姿勢，再讓相機繞著人體拍攝。不同角度共用同一份 mesh 與 UV 貼圖，
因此可重用已產生的幾何與烘焙檔案；相機改變後，仍會重新計算外觀、
可見性及光柵化，得到各角度的圖片。

```bash
python render_turntable.py \
  --traj_path /path/to/trajectory.pkl \
  --output_path /path/to/new-turntable-directory \
  --frame_idx 4 --n-angles 12 --bake-samples 4
```

這組 PNG 供網站顯示穿搭的多角度預覽，完整動作影片則在後續產生。

### 烘焙採樣數的用途

Blender 的烘焙步驟把當前 3D 表面的資訊存成 UV 貼圖，供 AvatarNet 使用。
`--bake-samples` 控制這個步驟使用的 Cycles 採樣數。
新增入口預設為 4，原版 `inference.py` 為 16；降低設定會減少烘焙採樣量，
也可能增加 AO 貼圖的雜訊。貼圖維持模型使用的 512 × 512 大小。
這個參數只調整渲染準備工作，不會改變衣物模擬或重新訓練模型。

## 如何指定資料與模型

我們在 [utils/defaults.py](utils/defaults.py) 加入環境變數設定，
讓 RealFit3D 依部署位置指定輸入、衣物資產與輔助模型，不必逐台修改 GG 程式。

| 變數 | 對應內容 |
|---|---|
| `REALFIT3D_GG_DATA_ROOT` | GG 輸入資料 |
| `REALFIT3D_GG_OUTPUT_ROOT` | 重建後的衣物資產與訓練好的外觀 checkpoint |
| `REALFIT3D_GG_AUX_ROOT` | 輔助模型與資料 |

Renderer 依衣物名稱讀取資產目錄中的 `stage1/template_uv.obj`、
`stage1/cameras.json` 與 `stage3/ckpt/net.pt`；
新渲染的圖片則寫入指令指定的 `--output_path`。

## 如何確認模擬軌跡能交給 GG

多件衣物的頂點會放在同一份軌跡裡，`garment_names` 的排列順序決定每段頂點
對應哪件衣物的 UV 模板與外觀模型。`Simulation` 在渲染前檢查名稱是否合法、
預測序列是否為空、每幀頂點總數是否符合模板，以及人體與衣物幀數是否一致。
輸入不相容時，程式會先回報錯誤。

衣物名稱由模擬 worker 明確寫入，取代依軌跡檔名猜測的方式。
資產準備時仍需對齊面／UV 索引與座標慣例。
由於 pickle 會先反序列化再進行上述檢查，檔案須來自可信來源。

## 透明度控制

小組的另一套透明度執行程式是在 Gaussian 光柵化前調整 opacity。
`direct` 模式直接將每顆 Gaussian 的原始 opacity 乘上控制值。
V3 則把原始 opacity 與正規化後的初始位置送入小型神經網路，
產生八個正值且總和為一的權重。這些權重組成隨控制值單調變化的分段線性函數，
再用函數輸出調整每顆 Gaussian 的 opacity，交給原有光柵化步驟產生畫面。

訓練時先固定 Stage 3 模型，渲染原始 alpha 圖 A1，再抽取控制值 s，
將 s × A1 當作目標。Controller 調整每顆 Gaussian 的 opacity，
可微分光柵器用它們產生新 alpha 圖；程式比較新圖與目標的前景誤差，
只更新 controller。訓練完成的 controller 會與 Stage 3 checkpoint 一起用於推論。

目前交付設定中，Actor02 使用 learned V3，Actor01／06／07 使用 direct。
我們已定位 V3 程式與 Actor02 controller 權重；此 fork 尚未包含它們。
接入工作另記於維護紀錄。

## 版本與測試

渲染入口、路徑設定與輸入檢查由 `8a52dc6` 引入。
已完成來源版本檢查及 RealFit3D CPU／瀏覽器測試；
完整 GPU 渲染驗收待執行。

版本更新方式見 [RealFit3D 開發流程](https://github.com/CasualBrave/realfit3d/blob/main/docs/DEVELOPMENT.md)。
