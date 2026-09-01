"""视频目标跟踪后端：基于 YOLO + ByteTrack/BoT-SORT 的多目标跟踪。

后端以生成器形式逐帧产出结果，不依赖任何 UI 框架，前端可按需消费：

    tracker = VideoTracker()
    for fr in tracker.track_video('traffic.mp4'):
        show(fr.annotated)       # 显示带 track_id 的标注帧
        update_table(fr.tracks)  # 更新该帧目标列表
    # 可在中途 break 提前终止，无需等整段视频跑完
"""
from collections import namedtuple

import cv2
import torch

from app.config import Config

# 单帧跟踪结果：用命名元组，轻量且字段自描述
FrameResult = namedtuple('FrameResult', [
    'frame_idx',     # 当前帧序号（从 0 起）
    'frame',         # 原始 BGR 图像 np.ndarray（未绘制，由调用方按需绘制）
    'tracks',        # 该帧目标列表 list[dict]，含 track_id/class_name/confidence/bbox
    'total_frames',  # 视频总帧数（未知则为 -1）
    'fps',           # 视频帧率
])


class VideoTracker:
    """视频多目标跟踪器。

    使用 ultralytics 内置 ByteTrack（默认）或 BoT-SORT 完成跨帧 ID 关联，
    persist=True 让同一目标在不同帧保持同一 track_id。
    """

    def __init__(self):
        self.config = Config()

        # 设备解析：auto 时优先使用 GPU
        device_cfg = self.config.get('model', 'device', default='auto')
        self.device = (0 if torch.cuda.is_available() else 'cpu') if device_cfg == 'auto' else device_cfg

        # 加载模型权重（延迟导入 ultralytics，与 Detector 保持一致）
        from ultralytics import YOLO
        weights = self.config.get('model', 'weights')
        self.model = YOLO(weights)
        self.names = self.model.names
        # ONNX 模型由 ONNX Runtime 管理 device，传 device 会被忽略并告警
        self._is_onnx = str(weights).lower().endswith('.onnx')

        # 推理参数
        self.image_size = self.config.get('model', 'image_size', default=640)
        self.conf = self.config.get('model', 'conf_threshold', default=0.25)
        self.iou = self.config.get('model', 'iou_threshold', default=0.45)
        # 跟踪器配置文件（ultralytics 自带 bytetrack.yaml / botsort.yaml）
        self.tracker_cfg = self.config.get('tracking', 'tracker', default='bytetrack.yaml')

    def track_video(self, source, save_path=None):
        """逐帧跟踪视频，生成器 yield FrameResult。

        参数:
            source    : 视频文件路径 / 摄像头索引(int) / RTSP 流，交给 cv2.VideoCapture
            save_path : 若提供，把带跟踪框的帧写入该 mp4 文件
        生成器模式便于前端实时显示与中断，不一次性载入全部帧。
        """
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频源: {source}")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 按需创建视频写出器（mp4v 编码）
        writer = None
        if save_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(save_path, fourcc, fps, (w, h))

        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                # track：persist=True 维持跨帧 track id；ONNX 模式不传 device
                kwargs = dict(
                    source=frame,
                    imgsz=self.image_size,
                    conf=self.conf,
                    iou=self.iou,
                    persist=True,
                    tracker=self.tracker_cfg,
                    verbose=False,
                )
                if not self._is_onnx:
                    kwargs['device'] = self.device
                results = self.model.track(**kwargs)
                result = results[0]
                tracks = self._parse_tracks(result)
                if writer is not None:
                    writer.write(frame)   # 仅保存原始帧（如需保存标注，由调用方另行写入）
                yield FrameResult(frame_idx, frame, tracks, total, fps)
                frame_idx += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()

    @staticmethod
    def _parse_tracks(result):
        """从跟踪结果对象提取每目标信息，组装为前端友好的字典列表。

        与 Detector._parse_result 的区别：额外提取 track_id（仅 track 模式存在）。
        """
        tracks = []
        if result.boxes is None or len(result.boxes) == 0:
            return tracks

        boxes = result.boxes.xyxy.cpu().numpy()           # [N, 4]
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)  # [N]
        confs = result.boxes.conf.cpu().numpy() if result.boxes.conf is not None else None
        # track id 在 track 模式存在；predict 模式下为 None
        ids = result.boxes.id.cpu().numpy().astype(int) if result.boxes.id is not None else None
        names = result.names

        for i, (x1, y1, x2, y2) in enumerate(boxes):
            tracks.append({
                'track_id': int(ids[i]) if ids is not None else -1,
                'class_id': int(cls_ids[i]),
                'class_name': str(names.get(int(cls_ids[i]), cls_ids[i])),
                'confidence': float(confs[i]) if confs is not None else 1.0,
                'bbox': [float(v) for v in (x1, y1, x2, y2)],
            })
        return tracks
