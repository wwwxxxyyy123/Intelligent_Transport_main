import os
import time
import glob
import warnings
from pathlib import Path

import yaml
import torch
import pandas as pd
from ultralytics import YOLO
from ultralytics.utils.torch_utils import get_num_params, get_flops

warnings.filterwarnings('ignore')

# ====== 基础配置 ======
SVAE_DIR = os.path.abspath('./test_results')                     # 所有结果保存根目录
MODEL_PATH = "./runs/detect/runs/train/yolo11s/weights/best.pt"   # 训练好的模型权重
DATA_YAML = 'data.yaml'                                          # 数据集配置文件
TEST_NAME = "yolo11s"                                            # 实验名称（写入 CSV 标识）
IMAGE_SIZE = 640                                                 # 推理 / 评估图像尺寸
DEVICE = 0 if torch.cuda.is_available() else 'cpu'               # 推理设备

# ====== 输出路径（统一保存在 SVAE_DIR/TEST_NAME 下）======
OUT_DIR = os.path.join(SVAE_DIR, TEST_NAME)                          # 本次实验输出根目录
TEST_DIR = os.path.join(OUT_DIR, 'test')                              # test 评估结果目录
PRED_DIR = os.path.join(OUT_DIR, 'predictions')                      # 预测结果图片目录
CSV_PATH = os.path.join(OUT_DIR, 'metrics_summary.csv')              # 指标汇总 CSV


def parse_data_yaml(yaml_path):
    """解析 data.yaml，返回测试集图像目录绝对路径与 {id: name} 字典。"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    base_dir = Path(yaml_path).resolve().parent
    test_dir = (base_dir / cfg['path'] / cfg['test']).resolve() # 测试集图像目录
    return str(test_dir), cfg.get('names', {})


def list_images(image_dir):
    """列出目录下所有图像文件（已排序）。"""
    exts = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.webp')
    files = []
    for e in exts:
        files.extend(glob.glob(os.path.join(image_dir, e)))
    return sorted(files)


def compute_params_flops(model, imgsz=IMAGE_SIZE):
    """计算模型参数量(M) 与 GFLOPs。"""
    n_params = get_num_params(model.model)                            # 参数量
    n_gflops = get_flops(model.model, imgsz=imgsz)                    # GFLOPs
    return n_params / 1e6, n_gflops


def measure_fps(model, image_dir, imgsz=IMAGE_SIZE, device=DEVICE, warmup=10):
    """在完整测试集上进行推理以测量 FPS（不含保存图片的开销）。"""
    files = list_images(image_dir)
    num = len(files)
    if num == 0:
        return 0.0, 0.0, 0

    # 预热：先推理若干张，避免首次启动 / CUDA 初始化耗时影响
    for f in files[:min(warmup, num)]:
        model.predict(f, imgsz=imgsz, device=device, save=False, verbose=False)
    if device != 'cpu' and torch.cuda.is_available():
        torch.cuda.synchronize()

    # 正式计时
    t0 = time.time()
    for f in files:
        model.predict(f, imgsz=imgsz, device=device, save=False, verbose=False)
    if device != 'cpu' and torch.cuda.is_available():
        torch.cuda.synchronize()
    total = time.time() - t0

    fps = num / total if total > 0 else 0.0
    return fps, total, num


def save_predictions(model, image_dir, save_dir, imgsz=IMAGE_SIZE, device=DEVICE):
    """对测试集推理并保存带预测框 + 类别名称的图片到 save_dir/predictions。"""
    model.predict(
        source=image_dir,
        imgsz=imgsz,
        device=device,
        save=True,
        save_txt=False,
        project=save_dir,
        name='predictions',
        exist_ok=True,
        verbose=False,
    )


def metrics_to_csv(metrics, fps, total_time, num_imgs, params_m, gflops, names, csv_path):
    """整理整体 / 每类指标并写入 CSV 文件。"""
    box = metrics.box
    mp, mr = float(box.mp), float(box.mr)
    map50, map95 = float(box.map50), float(box.map)
    f1 = 2 * mp * mr / (mp + mr + 1e-9)

    rows = [
        ('TestName', TEST_NAME),
        ('NumImages', num_imgs),
        ('Params(M)', round(params_m, 3)),
        ('GFLOPs', round(gflops, 2)),
        ('FPS', round(fps, 2)),
        ('TotalInferenceTime(s)', round(total_time, 2)),
        ('Precision', round(mp, 4)),
        ('Recall', round(mr, 4)),
        ('mAP50', round(map50, 4)),
        ('mAP50-95', round(map95, 4)),
        ('F1', round(f1, 4)),
    ]

    # 按类别 ID 排序，逐类输出指标
    for cid in sorted(names.keys()):
        name = names[cid]
        p_i = float(box.p[cid])
        r_i = float(box.r[cid])
        f1_i = 2 * p_i * r_i / (p_i + r_i + 1e-9)
        rows.extend([
            (f'{name}_Precision', round(p_i, 4)),
            (f'{name}_Recall', round(r_i, 4)),
            (f'{name}_F1', round(f1_i, 4)),
            (f'{name}_mAP50', round(float(box.ap50[cid]), 4)),
            (f'{name}_mAP50-95', round(float(box.ap[cid]), 4)),
        ])

    df = pd.DataFrame(rows, columns=['Metric', 'Value'])
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')


def print_summary(metrics, fps, total_time, num_imgs, params_m, gflops, names):
    """在控制台打印关键指标便于查看。"""
    box = metrics.box
    print('\n' + '=' * 60)
    print(f'  [Experiment] {TEST_NAME}')
    print('=' * 60)
    print(f'  NumImages         : {num_imgs}')
    print(f'  Params(M)         : {params_m:.3f}')
    print(f'  GFLOPs            : {gflops:.2f}')
    print(f'  FPS               : {fps:.2f}  (total {total_time:.2f}s)')
    print('-' * 60)
    print(f'  Precision         : {box.mp:.4f}')
    print(f'  Recall            : {box.mr:.4f}')
    print(f'  mAP50             : {box.map50:.4f}')
    print(f'  mAP50-95          : {box.map:.4f}')
    f1 = 2 * float(box.mp) * float(box.mr) / (float(box.mp) + float(box.mr) + 1e-9)
    print(f'  F1                : {f1:.4f}')
    print('-' * 60)
    for cid in sorted(names.keys()):
        n = names[cid]
        print(f'  [{n}] P={float(box.p[cid]):.4f}  R={float(box.r[cid]):.4f}  '
              f'mAP50={float(box.ap50[cid]):.4f}  mAP50-95={float(box.ap[cid]):.4f}')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    # 创建输出目录
    os.makedirs(OUT_DIR, exist_ok=True)

    # 解析 yaml 获取测试集路径与类别（根据当前目录下的 data.yaml）
    test_dir, names = parse_data_yaml(DATA_YAML)
    print(f'[Info] 测试集路径: {test_dir}')
    print(f'[Info] 类别映射  : {names}')

    # 加载训练好的模型
    model = YOLO(MODEL_PATH)
    print(f'[Info] 模型加载完成: {MODEL_PATH}')

    # 计算模型参数量与 FLOPs
    params_m, gflops = compute_params_flops(model)
    print(f'[Info] Params: {params_m:.3f} M | GFLOPs: {gflops:.2f}')

    # 在测试集上评估，得到 mAP / P / R 等指标
    metrics = model.val(
        data=DATA_YAML,
        split='test',                            # 使用 test 划分
        imgsz=IMAGE_SIZE,
        device=DEVICE,
        project=OUT_DIR,
        name='test',
        exist_ok=True,
    )

    # 在完整测试集上测量 FPS（不保存图片，纯推理耗时）
    fps, total_time, num_imgs = measure_fps(model, test_dir)
    print(f'[Info] 测试图像数: {num_imgs} | 总耗时: {total_time:.2f}s | FPS: {fps:.2f}')

    # 保存带预测框 + 类别名称的图片到 PRED_DIR
    save_predictions(model, test_dir, OUT_DIR)
    print(f'[Info] 预测图片已保存至: {PRED_DIR}')

    # 输出指标并写入 CSV
    print_summary(metrics, fps, total_time, num_imgs, params_m, gflops, names)
    metrics_to_csv(metrics, fps, total_time, num_imgs, params_m, gflops, names, CSV_PATH)
    print(f'[Done] 指标汇总已保存至: {CSV_PATH}')
