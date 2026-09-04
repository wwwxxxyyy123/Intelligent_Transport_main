import os
from ultralytics import YOLO
import torch
import warnings

warnings.filterwarnings('ignore')

# --- 1. 基础配置 ---
DATA_YAML = 'data.yaml'
MODEL_NAME = './ultralytics/cfg/models/11/ghost-p2-lh-yolo11n.yaml'
EPOCHS = 150
IMAGE_SIZE = 640
BATCH_SIZE = 32

DEVICE = 0 if torch.cuda.is_available() else 'cpu'

# --- 3. 训练模型 ---
def main():
    # 加载预训练模型
    model = YOLO(MODEL_NAME).load('yolo11n.pt')
    
    # 开始训练
    results = model.train(
        # === 数据和模型基础参数 ===
        data=DATA_YAML,          # 数据集配置文件
        epochs=EPOCHS,           # 训练轮数
        imgsz=IMAGE_SIZE,        # 输入图像大小
        batch=BATCH_SIZE,        # 批量大小
        device=DEVICE,           # 训练设备
        workers=8,               # 数据加载线程数
        
        # === 优化器与学习率 ===
        optimizer='SGD',         # SGD优化器
        lr0=0.01,                # 初始学习率
        lrf=0.01,                # 最终学习率因子 (lr0 * lrf)
        momentum=0.937,          # SGD动量
        weight_decay=0.0005,     # 权重衰减系数
        warmup_epochs=3,         # 预热轮数
        warmup_momentum=0.8,     # 预热阶段动量
        warmup_bias_lr=0.1,      # 预热阶段偏置学习率
        
        # 数据增强
        # 颜色与空间增强
        hsv_h=0.015,             # 色调增强
        hsv_s=0.7,               # 饱和度增强
        hsv_v=0.4,               # 明度增强
        degrees=5.0,             # 随机旋转角度
        translate=0.2,           # 随机平移
        scale=0.5,               # 随机缩放
        
        # 高级增强 (Mosaic, MixUp, Copy-Paste)
        mosaic=1.0,              # Mosaic马赛克增强
        mixup=0.1,               # MixUp混合增强
        copy_paste=0.3,          # Copy-Paste复制粘贴增强
        
        # === 训练控制 ===
        patience=30,             # 早停轮数
        save=True,               # 保存训练检查点
        save_period=-1,          # 只保存最后一轮权重last.pt，以及最优权重best.pt。
        seed=42,                 # 随机种子以确保可复现性
        single_cls=False,        # 多类别检测
        cos_lr=True,             # 使用余弦退火调度器

        # === 其他 ===
        project='runs/train',    # 结果保存项目名
        name='ghost-p2-lh-yolo11n',           # 本次实验名称
        exist_ok=True,           # 允许覆盖同名实验
        pretrained=True,         # 使用预训练权重
        resume=False,            # 从检查点恢复训练
        amp=True,                # 使用混合精度训练
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

if __name__ == '__main__':
    main()