"""
场馆灯光评估 - 命令行入口
用法:
  python -m court_lighting.analyze --image path/to/photo.jpg
  python -m court_lighting.analyze --image photo.jpg --roi 100,100,400,300
"""

import argparse
import sys
from .brightness import analyze_court_lighting


def main():
    parser = argparse.ArgumentParser(description="场馆灯光评估工具")
    parser.add_argument("--image", required=True, help="场馆照片路径")
    parser.add_argument("--roi", default=None, help="感兴趣区域 x,y,w,h（可选）")
    args = parser.parse_args()

    roi = None
    if args.roi:
        parts = [int(x.strip()) for x in args.roi.split(",")]
        if len(parts) == 4:
            roi = tuple(parts)

    try:
        report = analyze_court_lighting(args.image, roi)
        print(report)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
