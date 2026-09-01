# 智能交通检测系统

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)

基于 **YOLO11 + ByteTrack + PyQt5** 的桌面端智能交通检测系统，支持视频/图像目标检测与多目标跟踪、区域流量统计、拥堵预警、实时曲线绘制，并集成大语言模型（LLM）对交通状况进行智能分析。

## 功能特性

- **目标检测**：YOLO11（GhostNet-P2 改进版）ONNX 推理，自动适配 GPU / CPU，支持行人、机动车、非机动车三类目标
- **多目标跟踪**：内置 ByteTrack（可切换 BoT-SORT），跨帧维持目标 ID
- **区域流量统计**：自定义检测区域，统计单位时间内进入区域的目标数量，区域内目标列表展示停留时间
- **拥堵预警**：拥堵阈值可配置（左侧面板实时调节），区域内目标数超过阈值时区域自动变红
- **实时曲线**：基于 pyqtgraph 的高性能流量统计曲线，图表时间间隔与配置文件一致
- **FPS 显示**：视频区域左上角叠加实时帧率，采用 EMA 指数平滑
- **AI 智能分析**：视频结束后自动调用 LLM（OpenAI SDK 兼容接口）对统计数据进行 Markdown 格式分析，不阻塞 UI
- **明亮的中文界面**：左侧按钮/图例/阈值控制，中间视频或图像展示，下方目标信息，右上曲线区，右下统计区

## 界面布局

```
┌──────────┬────────────────────────┬─────────────┐
│ 按钮图例  │                        │  曲线绘制区  │
│ 拥堵阈值  │   视频 / 图像显示区      ├─────────────┤
│ 控制区   │   （左上角显示 FPS）      │  统计信息区  │
├──────────┴────────────────────────┴─────────────┤
│              目标信息（ID / 类别 / 置信度）          │
└──────────────────────────────────────────────────┘
```

## 环境要求

- Windows 10/11（建议，Linux/macOS 理论可用）
- Python 3.9+
- （可选）NVIDIA GPU + CUDA：用于推理与训练加速

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/<your-username>/Intelligent-Transport.git
cd Intelligent-Transport
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
```

> **GPU 加速（可选）**：
> - PyTorch CUDA 版：`pip install torch --index-url https://download.pytorch.org/whl/cu121`
> - ONNX Runtime GPU 版：`pip uninstall onnxruntime && pip install onnxruntime-gpu`

### 3. 配置密钥

复制 `.env.example` 为 `.env`，填入你的 LLM API 密钥：

```env
AGNES_API_KEY=your_api_key_here
AGNES_BASE_URL=your_base_url_here
```

> `.env` 已被 `.gitignore` 排除，请勿将密钥提交到仓库。

### 4. 下载模型权重

模型权重不随仓库分发，请从 [Releases](../../releases) 下载 `best.onnx`，放到配置文件指定的路径（默认）：

```
runs/detect/runs/train/ghost-p2-lh-yolo11n/weights/best.onnx
```

或修改 `config.yaml` 中 `model.weights` 指向你自己的模型文件。

### 5. 运行

```bash
python main.py
```

## 配置说明

所有可调参数集中在 [config.yaml](./config.yaml)：

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `model.weights` | ONNX 模型路径 | `runs/detect/.../best.onnx` |
| `model.image_size` | 推理图像尺寸 | `640` |
| `model.device` | 设备：`auto` / `cpu` / `0` | `auto` |
| `model.conf_threshold` | 置信度阈值 | `0.25` |
| `model.iou_threshold` | NMS IoU 阈值 | `0.45` |
| `tracking.tracker` | 跟踪器：`bytetrack.yaml` / `botsort.yaml` | `bytetrack.yaml` |
| `traffic.flow_window_seconds` | 流量统计窗口时长（秒） | `1.0` |
| `traffic.congestion_threshold` | 拥堵阈值（区域目标数超过则变红） | `5` |
| `llm.model` | LLM 模型名称 | `agnes-2.0-flash` |
| `llm.analysis_interval` | 自动分析间隔（秒） | `10.0` |
| `llm.max_frames_for_analysis` | 参与分析的最大统计帧数 | `300` |
| `llm.enable_auto_analysis` | 是否自动触发 AI 分析 | `true` |
| `display.width` | 前端显示缩放宽度 | `1280` |

## 模型训练与导出

如需使用自己的数据集重新训练：

```bash
# 1. 划分数据集
python data_split.py

# 2. 训练（含自定义 Ghost-P2 改进结构，详见 ultralytics/cfg/models/11/ghost-p2-lh-yolo11n.yaml）
python train.py

# 3. 将 best.pt 导出为 ONNX
python yolo_export.py
```

> 项目内置了修改版 [ultralytics](./ultralytics/)（含自定义模块 `C2PSA_EMA`、`LEDH` 等），运行时会优先使用内置版本，请勿删除该目录。

## 项目结构

```
Intelligent-Transport/
├── main.py                  # 程序入口（DPI/主题/模型预加载）
├── config.yaml              # 全局配置文件
├── requirements.txt         # 依赖清单
├── .env.example             # 环境变量模板
├── app/
│   ├── config.py            # 配置加载
│   ├── backend/             # 推理与统计后端
│   │   ├── detector.py      # YOLO 检测器封装
│   │   ├── tracker.py       # 多目标跟踪封装
│   │   ├── flow_counter.py  # 区域流量统计 / 拥堵判断 / FPS 叠加
│   │   └── llm_client.py    # LLM 客户端（OpenAI SDK）
│   └── frontend/            # PyQt5 界面
│       ├── main_window.py   # 主窗口
│       ├── button_panel.py  # 左侧控制面板（图例/阈值）
│       ├── image_viewer.py  # 视频/图像显示区
│       ├── chart_panel.py   # pyqtgraph 实时曲线
│       ├── stats_panel.py   # 右下统计信息
│       ├── llm_panel.py     # AI 分析面板（Markdown 渲染）
│       └── video_worker.py  # 视频工作线程
├── ultralytics/             # 内置修改版 ultralytics（含自定义模型结构）
├── train.py                 # 训练脚本
├── yolo_export.py           # ONNX 导出脚本
└── data_split.py            # 数据集划分脚本
```

## 许可证

本项目基于 [GNU Affero General Public License v3.0（AGPL-3.0）](./LICENSE) 开源。

- 你可以自由使用、修改和分发本项目，但分发或通过网络提供服务时必须以相同许可证开源修改后的完整源代码
- 项目内置的 [ultralytics](./ultralytics/) 目录基于 Ultralytics 项目（AGPL-3.0 许可证），并包含本项目的自定义修改
