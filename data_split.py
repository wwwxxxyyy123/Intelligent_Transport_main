import os
import json
import shutil
from tqdm import tqdm
from sklearn.model_selection import train_test_split

MRTMD_IMAGE_DIR = "./MRTMD-main/images/1080p"
MRTMD_LABEL_DIR = "./MRTMD-main/labels/1080p"

SEU_IMAGE_DIR = "./SEU_PML/train/images_mosaic"
SEU_LABEL_DIR = "./SEU_PML/train/labels"

OUTPUT_ROOT = "./DataSet"

TRAIN_RATIO = 0.8

SPLIT_RECORD_FILE = "split_records.json"

def get_pairs(img_dir, label_dir):
    """返回 (图片绝对路径, 标签绝对路径) 的列表"""
    pairs = []
    for fname in os.listdir(img_dir):
        if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        base = os.path.splitext(fname)[0]
        label_fname = base + '.txt'
        img_path = os.path.join(img_dir, fname)
        label_path = os.path.join(label_dir, label_fname)
        if os.path.exists(label_path):
            pairs.append((img_path, label_path))
        else:
            print(f"警告: {fname} 无对应标签，跳过")
    return pairs

def split(pairs, train_ratio, random_state=42):
    """返回 train, val, test 三个列表"""
    train, temp = train_test_split(pairs, test_size=(1 - train_ratio), random_state=random_state)

    val, test = train_test_split(temp, test_size=0.5, random_state=random_state)
    return train, val, test

def move_dataset_pairs(pairs_list, output_root, subset_name, prefix, dataset_name):
    """将 pairs_list 中的图片和标签移动到 output_root 下的 subset_name 目录中"""
    # 创建目标目录
    img_dst_dir = os.path.join(output_root, subset_name, "images")
    label_dst_dir = os.path.join(output_root, subset_name, "labels")
    os.makedirs(img_dst_dir, exist_ok=True)
    os.makedirs(label_dst_dir, exist_ok=True)

    moved_names = []
    for img_path, label_path in tqdm(pairs_list, desc=f"{dataset_name}->{subset_name}"):
        base_img = os.path.basename(img_path)
        new_img = f"{prefix}_{base_img}"
        base_label = os.path.basename(label_path)
        new_label = f"{prefix}_{base_label}"

        # 移动图片和标签
        dst_img = os.path.join(img_dst_dir, new_img)
        dst_label = os.path.join(label_dst_dir, new_label)
        shutil.move(img_path, dst_img)
        shutil.move(label_path, dst_label)

        moved_names.append(new_img)  # 只记录图片名，标签名可推断

    return moved_names


if __name__ == "__main__":
    # 读取图片和标签对
    mrtmd_pairs = get_pairs(MRTMD_IMAGE_DIR, MRTMD_LABEL_DIR)
    seu_pairs = get_pairs(SEU_IMAGE_DIR, SEU_LABEL_DIR)

    print(f"MRTMD 有效图片: {len(mrtmd_pairs)}")
    print(f"SEU_PML 有效图片: {len(seu_pairs)}")

    # 划分数据集
    mrtmd_train, mrtmd_val, mrtmd_test = split(mrtmd_pairs, TRAIN_RATIO)
    seu_train, seu_val, seu_test = split(seu_pairs, TRAIN_RATIO)

    # 记录划分信息
    split_info = {
        "random_seed": 42,
        "train_ratio": TRAIN_RATIO,
        "datasets": {
            "MRTMD": {
                "total": len(mrtmd_pairs),
                "train": {"count": len(mrtmd_train), "files": []},
                "val":   {"count": len(mrtmd_val),   "files": []},
                "test":  {"count": len(mrtmd_test),  "files": []}
            },
            "SEU": {
                "total": len(seu_pairs),
                "train": {"count": len(seu_train), "files": []},
                "val":   {"count": len(seu_val),   "files": []},
                "test":  {"count": len(seu_test),  "files": []}
            }
        }
    }

    # MRTMD
    split_info["datasets"]["MRTMD"]["train"]["files"] = move_dataset_pairs(mrtmd_train, OUTPUT_ROOT, "train", "MRTMD", "MRTMD")
    split_info["datasets"]["MRTMD"]["val"]["files"]   = move_dataset_pairs(mrtmd_val, OUTPUT_ROOT, "val", "MRTMD", "MRTMD")
    split_info["datasets"]["MRTMD"]["test"]["files"]  = move_dataset_pairs(mrtmd_test, OUTPUT_ROOT, "test", "MRTMD", "MRTMD")

    # SEU
    split_info["datasets"]["SEU"]["train"]["files"] = move_dataset_pairs(seu_train, OUTPUT_ROOT, "train", "SEU", "SEU")
    split_info["datasets"]["SEU"]["val"]["files"]   = move_dataset_pairs(seu_val, OUTPUT_ROOT, "val", "SEU", "SEU")
    split_info["datasets"]["SEU"]["test"]["files"]  = move_dataset_pairs(seu_test, OUTPUT_ROOT, "test", "SEU", "SEU")

    with open(SPLIT_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(split_info, f, indent=4, ensure_ascii=False)

    print(f"\n✅ 全部完成！")
    print(f"   - 数据已移动至: {OUTPUT_ROOT}")
    print(f"   - 划分记录已保存: {SPLIT_RECORD_FILE}")
    print(f"   - 总图片数: {len(mrtmd_pairs) + len(seu_pairs)}")