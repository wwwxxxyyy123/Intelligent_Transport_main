from ultralytics import YOLO

model = YOLO("runs/detect/runs/train/ghost-p2-lh-yolo11n/weights/best.pt")

# 导出并接收返回的路径
onnx_path = model.export(format="onnx", half=True)

print(f"ONNX 保存至: {onnx_path}")