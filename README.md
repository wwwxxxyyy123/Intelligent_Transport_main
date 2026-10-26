# 智能交通检测系统

基于 YOLO11n 的轻量化交通目标检测桌面应用：图片 / 视频 / 摄像头输入，检测行人、机动车、非机动车，ByteTrack 跟踪后进行区域流量统计与拥堵预警，可选调用大模型生成中文路况分析。

## 功能特性

- 图片、视频、摄像头三种输入，检测 + 多目标跟踪
- 多边形区域计数：统计流入 / 流出 / 区域内在场数与平均停留时间，超阈值触发拥堵预警
- pyqtgraph 实时曲线（窗口流量 / 区域内在场数）、目标列表、FPS 统计
- 配置驱动：模型、阈值、追踪器、界面尺寸均在 `config.yaml` 中调整
- 支持 `.pt` 与 `.onnx` 推理；可接入 OpenAI 兼容接口做智能分析

## 环境与安装

| 依赖 | 版本（已验证） |
|---|---|
| Python / 系统 | 3.10.20 / Windows 11 |
| PyTorch | 2.5.0+cu124（CUDA 12.4、cuDNN 9） |
| 硬件 | NVIDIA RTX 4060 Laptop（CPU 亦可运行，速度较慢） |

```bash
conda activate ultralytics310
pip install -r requirements.txt
python main.py
```

安装完请注意三条硬约束，否则程序无法启动：

1. **不要 `pip install ultralytics`**。`ultralytics/` 是内置修改版（8.4.123，含自定义 `LEDH` 检测头等模块），pip 版会覆盖它，加载 `.pt` 时报 `KeyError: 'LEDH'`。
2. **必须在仓库根目录启动**（`python main.py`），相对权重路径与内置 `ultralytics` 都依赖工作目录。
3. 内置版本**没有 `yolo` 命令行工具**，评测与导出请用 Python API（见下文「复现」一节）。

## 配置

`config.yaml` 主要项：

| 键 | 默认值 | 说明 |
|---|---|---|
| `model.weights` | `runs/.../ghost-p2-lh-yolo11n/weights/best.onnx` | `.pt` / `.onnx` 均可 |
| `model.device` | `auto` | `auto` / `cuda` / `cpu`（ONNX 模式下不生效） |
| `model.image_size` | `640` | 推理尺寸 |
| `model.conf` / `model.iou` | `0.25` / `0.45` | 置信度 / NMS 阈值 |
| `tracking.tracker` | `bytetrack.yaml` | 可换 `botsort.yaml` |
| `traffic.congestion_threshold` | `5` | 单窗口流量超过该值即预警 |
| `llm.model` | `deepseek-ai/DeepSeek-V4.1-Flash` | 大模型名称 |

大模型密钥写在项目根目录 `.env`：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`DEFAULT_MODEL`（兼容 `AGNES_*` 变量名）。缺少密钥只影响 AI 分析，检测功能正常。

## 数据集

| 子集 | 规模 | 说明 |
|---|---|---|
| 训练 / 验证 / 测试 | 7148 / 894 / 895 张 | YOLO 格式，3 类 |
| 来源 | MRTMD（公开数据集）+ SEU_PML（监控图像） | 仅取 MRTMD 的 1080p 子集 |

类别为 `person` / `motor_vehicle` / `non_motor_vehicle`，训练集框数占比 22.4% / 56.8% / 20.8%；框面积中位数仅占全图 **0.023% ~ 0.108%**，绝大多数目标小于全图 1%——这是引入 P2 高分辨率检测分支的原因。

## 模型改进

基线为官方 YOLO11n（2.59 M / 6.50 GFLOPs），共三处改动（配置见 `ultralytics/cfg/models/11/`），最终模型为 `ghost-p2-lh-yolo11n`：

| 改动 | 目的 | 实测效果 |
|---|---|---|
| 新增 P2 检测分支（三尺度 → 四尺度） | 提升小目标召回 | mAP50-95 **+0.0298**（主要增益） |
| 下采样 Conv → `GhostConv`（7 处） | 轻量化 | −0.0047，GFLOPs −7.9% |
| 检测头 `Detect` → `LEDH`（分组卷积 + 1×1 输出） | 轻量化 | −0.0102，整模型 GFLOPs −38.8% |

`C2PSA_EMA`（EMA 注意力）已实现但**未用于最终模型**，不计入改进项。

## 实验结果

7 个模型在同一套超参下训练（150 epoch、imgsz 640、batch 32、SGD、seed 42），测试集 895 张：

| 模型 | mAP50 | mAP50-95 | Params(M) | GFLOPs | 权重(MB) |
|---|---|---|---|---|---|
| **ghost-p2-lh-yolo11n（最终）** | 0.6347 | 0.3576 | **2.05** | **5.91** | **4.39** |
| ghost-p2-yolo11n | 0.6457 | 0.3678 | 2.35 | 9.65 | 4.99 |
| p2-yolo11n | **0.6513** | **0.3725** | 2.68 | 10.48 | 5.60 |
| yolo11n（基线） | 0.6013 | 0.3427 | 2.59 | 6.50 | 5.23 |
| yolov8n / v10n / v12n | 0.599 ~ 0.603 | 0.342 | 2.57 ~ 3.01 | 7.46 ~ 8.46 | 5.28 ~ 5.97 |

- 相对基线**"更小且更准"成立**：mAP50-95 +4.35%，参数 −20.8%，权重 −16.1%。
- 算力收益几乎全部来自 `LEDH` 检测头（单看检测头 GFLOPs 约 −77%），`GhostConv` 贡献有限。
- 表中最高分是 `p2-yolo11n`；最终模型是用约 1.5 个点 mAP 换算力，属**轻量化取舍**，并非精度最优。
- **"更快"没有证据**：FPS 差异在噪声内（58.4 vs 58.3），训练反而慢约 52%。
- 逐类看 `person` 最弱（mAP50-95 约 0.17），整体指标主要被占比 57% 的机动车拉高。

## 复现

```bash
python train.py        # 训练（可在脚本内改模型配置与轮数）
```

```python
from ultralytics import YOLO

m = YOLO("runs/detect/runs/train/ghost-p2-lh-yolo11n/weights/best.pt")
r = m.val(data="data.yaml", split="test", imgsz=640)
print(r.box.map50, r.box.map, r.box.maps)   # mAP50 / mAP50-95 / 逐类
```

```bash
python yolo_export.py  # 导出 ONNX（默认 fp16，CPU 部署请改 half=False）
```

## 项目结构

```
Intelligent_Transport_main/
├── main.py              # 入口：预热模型 + 主窗口
├── config.yaml          # 运行配置
├── data.yaml            # 数据集定义
├── train.py / test.py   # 训练 / 评测脚本
├── data_split.py        # 数据划分（注意：会移动原始文件）
├── yolo_export.py       # 导出 ONNX
├── app/
│   ├── backend/         # 模型加载、检测、跟踪、流量统计、大模型客户端
│   └── frontend/        # PyQt5 界面、视频线程、图表与各面板
├── ultralytics/         # 内置修改版（含 LEDH、C2PSA_EMA 等自定义模块）
└── runs/、test_results/ # 训练产物与测试指标
```

## 许可

内置 `ultralytics/` 沿用原项目 AGPL-3.0 协议，商用请遵守；数据集 MRTMD、SEU_PML 版权归原作者。
