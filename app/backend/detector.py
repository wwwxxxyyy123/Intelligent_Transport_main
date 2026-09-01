"""推理后端：封装 YOLO 模型加载与预测流程。

后端只关心"输入图像路径 -> 输出原图 + 检测结果"，不涉及任何 UI 逻辑，
便于后续替换模型或在命令行中复用。标注绘制由调用方按需进行（draw_detections）。
"""
import cv2
import torch

from app.backend.flow_counter import class_color
from app.config import Config


class Detector:
    """YOLO 目标检测器。"""

    def __init__(self):
        self.config = Config()

        # 设备解析：auto 时优先使用 GPU
        device_cfg = self.config.get('model', 'device', default='auto')
        if device_cfg == 'auto':
            self.device = 0 if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device_cfg

        # 加载模型权重
        weights = self.config.get('model', 'weights')
        # 延迟导入，避免无 ultralytics 环境下 import 阶段就报错
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.names = self.model.names  # {id: name} 由权重自动给出
        # ONNX 模型由 ONNX Runtime 管理 device，传 device 会被忽略并告警
        self._is_onnx = str(weights).lower().endswith('.onnx')

        # 推理参数
        self.image_size = self.config.get('model', 'image_size', default=640)
        self.conf = self.config.get('model', 'conf_threshold', default=0.25)
        self.iou = self.config.get('model', 'iou_threshold', default=0.45)

    def predict(self, image_path):
        """对单张图像推理。

        返回:
            image      : np.ndarray  原始 BGR 图像（未绘制，由调用方按需绘制）
            detections : list[dict] 每个元素含 class_id/class_name/confidence/bbox
        """
        # ONNX 模式不传 device（由 ONNX Runtime 的 provider 决定）
        kwargs = dict(
            source=image_path,
            imgsz=self.image_size,
            conf=self.conf,
            iou=self.iou,
            save=False,
            verbose=False,
        )
        if not self._is_onnx:
            kwargs['device'] = self.device
        results = self.model.predict(**kwargs)
        result = results[0]
        image = result.orig_img.copy()   # 原始图像，不使用 result.plot()
        detections = self._parse_result(result)
        return image, detections

    @staticmethod
    def draw_detections(image, detections):
        """在图像上绘制检测结果：每个目标按类别颜色的 1px 细框 + 类别+置信度标签。

        与视频跟踪的目标框样式保持一致（细框+类别色），原地绘制返回同一图像。
        """
        for d in detections:
            x1, y1, x2, y2 = d['bbox']
            color = class_color(d['class_id'])
            cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), color, 1)
            # bbox 上方标注 "类别 置信度"
            label = f"{d['class_name']} {d['confidence']:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image,
                         (int(x1), int(y1) - th - 6),
                         (int(x1) + tw + 4, int(y1) - 2),
                         (0, 0, 0), -1)
            cv2.putText(image, label, (int(x1) + 2, int(y1) - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return image

    @staticmethod
    def _parse_result(result):
        """从结果对象提取每框信息，组装为前端友好的字典列表。"""
        detections = []
        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy()           # [N, 4]
        confs = result.boxes.conf.cpu().numpy()            # [N]
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)  # [N]
        names = result.names

        for (x1, y1, x2, y2), conf, cid in zip(boxes, confs, cls_ids):
            detections.append({
                'class_id': int(cid),
                'class_name': str(names.get(int(cid), cid)),
                'confidence': float(conf),
                'bbox': [float(v) for v in (x1, y1, x2, y2)],
            })
        return detections
