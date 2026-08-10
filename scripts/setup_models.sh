#!/bin/bash
# ShuttleKit 模型下载脚本
# 用法: bash scripts/setup_models.sh

set -e

MODELS_DIR="shuttle_speed/models"
mkdir -p "$MODELS_DIR"

echo "=========================================="
echo "  ShuttleKit 模型下载脚本"
echo "=========================================="

# 1. YOLO 通用模型（可选，用于球检测）
echo ""
echo "[1/2] 下载 YOLOv8n 模型（通用检测，约 6MB）..."
if [ -f "$MODELS_DIR/yolov8n.pt" ]; then
    echo "  已存在，跳过"
else
    # 首次运行 ultralytics 会自动下载，这里不手动下载
    echo "  首次运行 python -m shuttle_speed.track 时自动下载"
    echo "  或手动访问: https://github.com/ultralytics/assets/releases"
fi

# 2. TrackNet 羽毛球专用模型（推荐）
echo ""
echo "[2/2] TrackNet 羽毛球专用模型..."
echo "  TrackNet 需要从以下仓库获取权重:"
echo "  - https://github.com/yastrebksv/TrackNet"
echo "  - https://gitlab.nol.cs.nycu.edu.tw/open-source/TrackNet"
echo "  下载后放到: $MODELS_DIR/tracknet.pth"
echo ""
echo "  注意: TrackNet 需要 GPU + PyTorch 环境"

echo ""
echo "=========================================="
echo "  下载完成"
echo "  简单模块（灯光/场地/统计/器材）无需模型即可使用"
echo "=========================================="
