# 與原版 Gaussian Garments 的差異

[English](REALFIT3D_CHANGES.md) | [README](README.md)

查核日期：2026-10-20。本文件只描述已提交到此 fork 的改動，
不是小組全部實驗與研究成果的總表。

## 1. 比較基準與專案分工

- 官方來源：[eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments)。
- 比較基準：`ceb66fc36598da05b3b3391f4562cdc54d2a2ed2`。
- 此 fork：維護需要放在 GG 執行程式內的改動。
- [RealFit3D 主專案](https://github.com/CasualBrave/realfit3d)：網站、API、
  流程調度、身形適配 worker、品質工具與設定；
  以 Git submodule 在 `upstream/Gaussian-Garments` 引用此 fork 的固定版本。
- ContourCraft、ActorsHQ／GS2Mesh 是另外的依賴，不是我們新增到 GG 核心的算法。

Submodule 記錄特定 commit。推送此 fork 不會自動更新 RealFit3D，
還必須在主專案提交新的引用。保留上游署名與聲明；
程式放在哪個資料夾不代表算法是誰發明的，也不會改變第三方授權。

## 2. 已採用的程式修改

以下實作由 fork commit `8a52dc6` 引入；其後的文件提交沒有新增透明度功能。

### 2.1 沿用交接版渲染入口

檔案：[render_lean.py](render_lean.py)、[render_turntable.py](render_turntable.py)。

來源：`CasualBrave/frontend_temp`，commit
`2a643b1b43a0329dce23b7c40fbc2757bcfab968`。
這些是沿用組員交接的程式，不是整合時新發明的算法。

- `render_lean.py` 輸出最終畫面，不組合原版的診斷面板，並提供 bake 採樣數選項。
- `render_turntable.py` 對選定的一幀渲染多個角度，透過既有 preparation cache
  在不同角度間重用 mesh／bake 產物。
- 兩個入口的 `--bake-samples` 預設為 4；原版 `inference.py` 仍為 16。
  新入口僅在自己的程序替換 bake 函式，沒有修改原版全域預設。

目的：提供交接版預覽渲染行為的固定入口。降低採樣是畫質與速度的取捨，
不能直接宣稱等畫質加速。交接程式註解中的歷史效能數字不是本次整合的新測量；
GPU 畫質與耗時比較仍待完成。

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
此修改不會下載資料、安裝環境或驗證模型內容。

### 2.3 模擬輸入檢查

檔案：[inference.py](inference.py) 的 `Simulation`。

新增檢查會拒絕：

- 衣物名稱清單為空，或名稱不是字串、為空字串、為 `.`／`..`、包含路徑分隔符。
- 預測軌跡為空，或任一幀頂點數不等於依衣物排列讀取的 UV templates 頂點總數。
- 衣物 `pred` 與人體 `obstacle` 的幀數不同。

目的：提早擋下部分不相容資產，避免產生誤導畫面或在後續才發生索引錯誤。
資料產生端仍須提供正確衣物順序；頂點數相同不代表拓撲、座標或 checkpoint
語意相容。這些檢查發生在讀取 pickle 之後，不能讓不可信 pickle 變得安全。

## 3. 明確沒有採用的修改

- 交接版依檔名猜衣物名稱的 fallback：可能選錯外觀 checkpoint。
  RealFit3D worker 改由資料明確提供 garment names。
- 無關的 inference 計時變更與全域 bake 預設修改：
  預覽採樣設定只留在新增渲染入口。
- 實驗性的 LBS／ICP pose transfer 沒有默默成為 RealFit3D 預設流程。
- 透明度 V3 與遠端訓練修改尚未整包搬進此 fork，
  必須先比較原始碼與確認相容性。

## 4. 各階段涵蓋範圍

| 階段 | 目前狀態 | 待確認／驗證 |
|---|---|---|
| S1 幾何重建 | 此 fork 保留原版算法；RealFit3D 另引用固定版本 ActorsHQ／GS2Mesh 及交接品質工具 | 遠端重建改動、實際採用的輸入；不是每個品質工具都已自動接入 |
| S2 registration | 原版 GG 訓練程式 | 比對遠端小組程式、啟動設定與輸出 |
| S3 外觀 | 原版 GG 訓練程式，未合併 V3 controller | 稽核並整合已找到的透明度實作與相容資產 |
| S4 動態 | 不在此 fork；RealFit3D 包裝 ContourCraft 轉換與訓練 | 實際生效設定與 GPU 行為 |
| 線上身形適配 | 交接 fitting／pin workers 位於 RealFit3D | 與既有部署使用相同真實資產比較 |
| 渲染 | 已加入上述交接入口、路徑設定與輸入檢查 | 畫質、效能及完整網站產出流程 |

## 5. 透明度 V3：已找到，不等於已整合

2026-10-20 唯讀檢查遠端 `iismtl5197096_actor1267_delivery_20261020` 交付時：

- 找到並閱讀 `opacity_controller_v3_common.py` 中的 `SplineOpacityController`。
- 讀到 `inference_opacity.py` 的 V3 載入與 rasterization 前 opacity 控制分支。
- 確認 Actor02 上下衣 `controller.pt` 存在並計算雜湊；
  沒有反序列化權重或執行 GPU 測試。

交付 manifest 只有 Actor02 標為 learned V3；
Actor01／06／07 使用 direct opacity，不是 learned V3。
目前交付入口每次推論只提供一個全域 opacity 值，不是上下衣各自獨立控制。

先前 GitHub 透明度交付 repo 缺少核心檔案，這項限制不能概括套用到新找到的
伺服器交付包。找到檔案不代表已整合或通過驗收。
路徑、雜湊與查核範圍見 [遠端發現紀錄](https://github.com/CasualBrave/realfit3d/blob/main/docs/REMOTE_DISCOVERY_20261020.md)。

## 6. 驗證與後續維護

已完成原始碼版本檢查及主專案 CPU／瀏覽器測試；
未跑完真實模型的 GPU 試衣或重新訓練。
目前不宣稱此 fork 與交接版輸出完全一致、已量測加速，
或已完整重現組員的 S1–S4。

本機檢視實際差異：

```bash
git diff --stat ceb66fc36598da05b3b3391f4562cdc54d2a2ed2 HEAD
git diff ceb66fc36598da05b3b3391f4562cdc54d2a2ed2 HEAD -- inference.py utils/defaults.py
```

後續每項採用的修改，都要同步更新中英文文件，記錄來源檔案／commit 或雜湊、
目的、行為改變、採用狀態與測試。遠端既有小組資料只讀；
程式修改與 push 在本機進行，遠端實驗須另行通知，
並限定在 `/home/vtongroup/lin/` 工作目錄。
