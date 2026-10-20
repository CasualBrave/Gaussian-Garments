# 與原版 Gaussian Garments 的差異

[English](REALFIT3D_CHANGES.md) | [README](README.md)

更新日期：2026-10-20。範圍：此 fork 的程式修改、依賴與驗證狀態。

## 1. 比較基準與專案分工

- 官方來源：[eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments)。
- 比較基準：`ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`。
- 此 fork：維護需要放在 GG 執行程式內的改動。
- [RealFit3D 主專案](https://github.com/CasualBrave/realfit3d)：網站、API、
  流程調度、身形適配 worker、品質工具與設定；
  以 Git submodule 在 `upstream/Gaussian-Garments` 引用此 fork 的固定版本。
- ContourCraft 提供動態模擬，ActorsHQ／GS2Mesh 提供替代重建流程；
  RealFit3D 分別固定這些依賴的版本。

Submodule 記錄特定 commit。推送此 fork 不會自動更新 RealFit3D，
還必須在主專案提交新的引用。我們保留上游 README、引用與聲明；
各移入元件的來源列於下方。

## 2. 已採用的程式修改

以下實作由 fork commit `8a52dc6` 引入。

### 2.1 沿用交接版渲染入口

檔案：[render_lean.py](render_lean.py)、[render_turntable.py](render_turntable.py)。

來源：`CasualBrave/frontend_temp`，commit
`2a643b1b43a0329dce23b7c40fbc2757bcfab968`。
我們從此版本移入這兩個渲染腳本。

- `render_lean.py` 輸出最終畫面，不組合原版的診斷面板，並提供 bake 採樣數選項。
- `render_turntable.py` 對選定的一幀渲染多個角度，透過既有 preparation cache
  在不同角度間重用 mesh／bake 產物。
- 兩個入口的 `--bake-samples` 預設為 4；原版 `inference.py` 仍為 16。
  新入口僅在自己的程序替換 bake 函式，沒有修改原版全域預設。

這兩個入口支援可調整烘焙採樣數的預覽渲染。較低採樣數可能增加 AO／normal
貼圖雜訊。GPU 驗收將以相同資產、影格與相機設定，比較 4 與 16 samples
的畫質及耗時。

### 2.2 資料路徑改為可設定

檔案：[utils/defaults.py](utils/defaults.py)。

| 環境變數 | 對應 GG 設定 |
|---|---|
| `REALFIT3D_GG_DATA_ROOT` | `DEFAULTS.data_root` |
| `REALFIT3D_GG_OUTPUT_ROOT` | `DEFAULTS.output_root` |
| `REALFIT3D_GG_AUX_ROOT` | `DEFAULTS.aux_root` |

原本需要編輯程式內的路徑 placeholder，現在可由環境變數覆蓋，
讓不同機器不必修改同一份共用程式。保留原版 fallback 路徑、
輸入與輔助資料目錄的存在性檢查。
部署前需準備對應資產目錄與執行環境。

### 2.3 模擬輸入檢查

檔案：[inference.py](inference.py) 的 `Simulation`。

新增檢查會拒絕：

- 衣物名稱清單為空，或名稱不是字串、為空字串、為 `.`／`..`、包含路徑分隔符。
- 預測軌跡為空，或任一幀頂點數不等於依衣物排列讀取的 UV templates 頂點總數。
- 衣物 `pred` 與人體 `obstacle` 的幀數不同。

這些檢查在渲染前拒絕數量不相容的輸入。資產準備時還需核對衣物順序、
面索引、座標慣例與外觀 checkpoint。檢查發生在讀取 pickle 之後；
pickle 反序列化可執行程式碼，因此輸入僅接受可信來源。

## 3. 明確沒有採用的修改

- 交接版依檔名猜衣物名稱的 fallback：可能選錯外觀 checkpoint。
  RealFit3D worker 改由資料明確提供 garment names。
- 無關的 inference 計時變更與全域 bake 預設修改：
  預覽採樣設定只留在新增渲染入口。
- 實驗性的 LBS／ICP pose transfer 保留為獨立研究路徑。
- 透明度 V3 與遠端訓練修改將先進行來源比對與相容性驗證，再接入此 fork。

## 4. 各階段涵蓋範圍

| 階段 | 目前狀態 | 待確認／驗證 |
|---|---|---|
| S1 幾何重建 | 此 fork 保留原版算法；RealFit3D 另引用固定版本 ActorsHQ／GS2Mesh 及交接品質工具 | 遠端重建改動、實際採用的輸入；不是每個品質工具都已自動接入 |
| S2 registration | 原版 GG 訓練程式 | 比對遠端小組程式、啟動設定與輸出 |
| S3 外觀 | 原版 GG 訓練程式，未合併 V3 controller | 稽核並整合已找到的透明度實作與相容資產 |
| S4 動態 | 不在此 fork；RealFit3D 包裝 ContourCraft 轉換與訓練 | 實際生效設定與 GPU 行為 |
| 線上身形適配 | 交接 fitting／pin workers 位於 RealFit3D | 與既有部署使用相同真實資產比較 |
| 渲染 | 已加入上述交接入口、路徑設定與輸入檢查 | 畫質、效能及完整網站產出流程 |

## 5. 透明度 V3 接入進度

2026-10-20 唯讀檢查遠端 `iismtl5197096_actor1267_delivery_20261020` 交付時：

- 找到並閱讀 `opacity_controller_v3_common.py` 中的 `SplineOpacityController`。
- 讀到 `inference_opacity.py` 的 V3 載入與 rasterization 前 opacity 控制分支。
- 確認 Actor02 上下衣 `controller.pt` 存在並計算雜湊；
  沒有反序列化權重或執行 GPU 測試。

交付 manifest 指定 Actor02 使用 learned V3；
Actor01／06／07 使用 direct opacity。
目前交付入口每次推論只提供一個全域 opacity 值，不是上下衣各自獨立控制。

GitHub 透明度 repo 提供研究說明與 actor scripts；
遠端交付提供 V3 原始碼與 Actor02 controller 檔案。
接入前將完成程式比對與資產相容性檢查。
路徑與雜湊見 [遠端發現紀錄](https://github.com/CasualBrave/realfit3d/blob/main/docs/REMOTE_DISCOVERY_20261020.md)。

## 6. 驗證與後續維護

已完成原始碼版本檢查及主專案 CPU／瀏覽器測試。
GPU 驗收待執行，將以相同輸入比較既有流程與整合版的軌跡、
圖片／影片、耗時及峰值記憶體。

本機檢視實際差異：

```bash
git diff --stat ceb66fc36598da05b3b3391f4562cdc54d2a2ed2 HEAD
git diff ceb66fc36598da05b3b3391f4562cdc54d2a2ed2 HEAD -- inference.py utils/defaults.py
```

後續每項採用的修改，都要同步更新中英文文件，記錄來源檔案／commit 或雜湊、
目的、行為改變、採用狀態與測試。遠端既有小組資料只讀；
程式修改與 push 在本機進行，遠端實驗須另行通知，
並限定在 `/home/vtongroup/lin/` 工作目錄。
