"""YOLO 模型加载公共基类：统一设备解析、权重加载与推理参数。"""
import torch

from app.config import Config


class YOLOModel:
    """封装 ultralytics YOLO 加载细节，供 Detector / VideoTracker 复用。"""

    def __init__(self):
        self.config = Config()

        # 设备解析：auto 时优先使用 GPU；ONNX 由 ONNX Runtime 决定设备
        device_cfg = self.config.get('model', 'device', default='auto')
        self.device = (0 if torch.cuda.is_available() else 'cpu') \
            if device_cfg == 'auto' else device_cfg

        weights = self.config.get('model', 'weights')
        from ultralytics import YOLO  # 延迟导入，避免无 ultralytics 环境下 import 即报错
        self.model = YOLO(weights)
        self.names = self.model.names
        self._is_onnx = str(weights).lower().endswith('.onnx')

        self.image_size = self.config.get('model', 'image_size', default=640)
        self.conf = self.config.get('model', 'conf_threshold', default=0.25)
        self.iou = self.config.get('model', 'iou_threshold', default=0.45)

    def _infer_kwargs(self, **extra):
        """构造推理参数（ONNX 模式不传 device，避免告警）。"""
        kwargs = dict(imgsz=self.image_size, conf=self.conf, iou=self.iou,
                      save=False, verbose=False, **extra)
        if not self._is_onnx:
            kwargs['device'] = self.device
        return kwargs
