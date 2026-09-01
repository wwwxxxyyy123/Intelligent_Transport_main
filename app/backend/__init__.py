"""推理后端包：封装模型加载与预测/跟踪/流量计数逻辑，与 UI 解耦。"""
from .detector import Detector                 # 单图推理
from .tracker import VideoTracker, FrameResult  # 视频跟踪
from .flow_counter import FlowCounter           # 区域流量计数

__all__ = ["Detector", "VideoTracker", "FrameResult", "FlowCounter"]
