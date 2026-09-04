"""推理后端：单张图像预测与检测框绘制。"""
import cv2

from app.backend.flow_counter import class_color
from app.backend.model import YOLOModel


class Detector(YOLOModel):
    """YOLO 单图目标检测器。"""

    def predict(self, image_path):
        """推理单张图像，返回 (原始 BGR 图像, 检测结果列表)。"""
        result = self.model.predict(source=image_path, **self._infer_kwargs())[0]
        return result.orig_img.copy(), self._parse_result(result)

    @staticmethod
    def draw_detections(image, detections):
        """绘制检测框与置信度标签（框色打底 + 白字），原地绘制。"""
        for d in detections:
            x1, y1, x2, y2 = (int(v) for v in d['bbox'])
            color = class_color(d['class_id'])
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)
            label = f"{d['confidence']:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image, (x1, y1 - th - 6), (x1 + tw + 4, y1 - 2), color, -1)
            cv2.putText(image, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return image

    @staticmethod
    def _parse_result(result):
        """从结果对象提取每框信息，组装为字典列表。"""
        detections = []
        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)
        names = result.names

        for (x1, y1, x2, y2), conf, cid in zip(boxes, confs, cls_ids):
            detections.append({
                'class_id': int(cid),
                'class_name': str(names.get(int(cid), cid)),
                'confidence': float(conf),
                'bbox': [float(v) for v in (x1, y1, x2, y2)],
            })
        return detections
