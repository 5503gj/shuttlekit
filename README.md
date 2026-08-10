# ShuttleKit - 羽毛球智能分析工具箱

> 羽毛球爱好者的"瑞士军刀"：球速检测、场馆灯光评估、场地配置、比赛统计、器材知识库，一站式搞定。

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Modules](https://img.shields.io/badge/Modules-6-orange)

---

## 这是什么

ShuttleKit 是一个**模块化**的羽毛球综合分析工具箱。不管你是想分析自己的击球速度、评估场馆灯光是否合格、还是查什么球拍适合新手——打开对应模块就行。

每个模块**独立可用**，不需要全部跑通。你可以只用人脸都能操作的灯光分析模块，也可以深入跑 TrackNet 球速检测。

### 为什么做这个

市面上的羽毛球 CV 项目要么只检测球（没有场地分析），要么假设俯视机位（真实场景做不到），要么写死 Windows 路径。ShuttleKit 把常见需求拆成 6 个独立模块，能用的用、不能用的看文档，降低使用门槛。

---

## 模块总览

| 模块 | 功能 | 难度 | 需要 GPU？ |
|------|------|------|-----------|
| [court_lighting](./court_lighting) | 场馆灯光亮度评估 + 是否达标的判断 | ★☆☆ | 否 |
| [court_config](./court_config) | 场地线检测 + 尺寸校验 + 配置建议 | ★★☆ | 否 |
| [shuttle_speed](./shuttle_speed) | 羽毛球球速检测（轨迹→速度） | ★★★ | 推荐 |
| [match_stats](./match_stats) | 比赛回合统计 + 数据可视化看板 | ★★☆ | 否 |
| [equipment_kb](./equipment_kb) | 球拍/球鞋/球 知识库 + 选品推荐 | ☆☆☆ | 否 |
| [tests](./tests) | 全模块测试用例 + 缺陷报告模板 | ★☆☆ | 否 |

---

## 快速开始

### 环境要求

- Python 3.9+
- 核心依赖：`opencv-python`, `numpy`, `matplotlib`（简单模块）
- 进阶依赖：`ultralytics`, `torch`（球速检测模块）

### 安装

```bash
git clone https://github.com/your-username/ShuttleKit.git
cd ShuttleKit
pip install -r requirements.txt
```

### 启动网页

```bash
python badminton_web.py
```

浏览器打开 `http://127.0.0.1:7861`，可以体验场馆图片分析、比赛数据看板和器材推荐。

### 30 秒体验：场馆灯光评估

```bash
python -m court_lighting.analyze --image data/sample_results/test_court.jpg
```

输出示例：
```
========== 场馆灯光评估报告 ==========
平均亮度: 142.3 / 255 (55.8%)
亮度均匀度: 0.82 (良好)
眩光区域: 检测到 1 处高光区
评估结论: 基本达标，建议关注右上角眩光
======================================
```

---

## 各模块说明

### 1. court_lighting - 场馆灯光评估
[详细文档](./court_lighting/README.md)

拍一张场馆照片，自动分析：
- 平均亮度（对照 BWF 照度标准 300-500 lux）
- 亮度均匀度（是否有过亮/过暗区）
- 眩光检测（避免影响球员视线）
- 是否达标的结论和建议

### 2. court_config - 场地配置
[详细文档](./court_config/README.md)

检测场地线并校验尺寸：
- 场地线提取（基于 OpenCV 边缘检测）
- 球场类型判断（单打/双打）
- 尺寸合规性校验（对照 BWF 标准）
- 球网高度估算

### 3. shuttle_speed - 球速检测
[详细文档](./shuttle_speed/README.md)

从视频检测羽毛球轨迹并计算速度：
- 球轨迹追踪（基于 TrackNet / YOLO）
- 帧间位移 → 像素速度 → 实际速度
- 最高速度 / 平均速度统计
- 速度曲线可视化

### 4. match_stats - 比赛统计
[详细文档](./match_stats/README.md)

比赛数据记录与可视化：
- 回合计数与时长
- 得分记录与比分曲线
- 击球类型分布
- 生成数据看板（PNG/HTML）

### 5. equipment_kb - 器材知识库
[详细文档](./equipment_kb/README.md)

球拍/球鞋/球 的选购知识：
- 按水平/预算推荐装备
- 参数对照表（重量、平衡点、中杆硬度）
- 新手避坑指南

### 6. tests - 测试用例
[详细文档](./tests/README.md)

每个模块的测试用例 + 缺陷报告模板，展示测试思维。

---

## 项目结构

```
ShuttleKit/
├── README.md                 # 本文件
├── requirements.txt          # 依赖清单
├── .gitignore
├── LICENSE                   # MIT
├── court_lighting/           # 灯光评估
│   ├── __init__.py
│   ├── analyze.py            # 主入口
│   ├── brightness.py         # 亮度计算核心
│   └── README.md
├── court_config/             # 场地配置
│   ├── __init__.py
│   ├── detect.py             # 线检测
│   ├── validate.py           # 尺寸校验
│   └── README.md
├── shuttle_speed/            # 球速检测
│   ├── __init__.py
│   ├── track.py              # 轨迹追踪
│   ├── speed_calc.py         # 速度计算
│   └── README.md
├── match_stats/              # 比赛统计
│   ├── __init__.py
│   ├── recorder.py           # 数据记录
│   ├── visualize.py          # 可视化
│   └── README.md
├── equipment_kb/             # 器材知识库
│   ├── __init__.py
│   ├── rackets.json          # 球拍数据
│   ├── recommender.py        # 推荐逻辑
│   └── README.md
├── tests/                    # 测试用例
│   ├── test_lighting.py
│   ├── test_config.py
│   ├── test_speed.py
│   ├── DEFECT_TEMPLATE.md    # 缺陷报告模板
│   └── README.md
├── docs/                     # 文档
│   ├── BWF_STANDARDS.md      # BWF 标准参考
│   ├── QUICKSTART.md         # 快速上手
│   └── FAQ.md                # 常见问题
├── data/
│   ├── templates/            # 数据模板
│   └── sample_results/       # 示例输出
└── scripts/
    └── setup_models.sh       # 模型下载脚本
```

---

## 致谢

本项目参考/整合了以下优秀开源工作：

- [Good-Badminton](https://github.com/Chen-Jason/Good-Badminton) - AI 羽毛球鹰眼系统
- [BaddieVision](https://github.com/MaxLinCode/BaddieVision) - 羽毛球视频分析工具链
- [TrackNet](https://github.com/yastrebksv/TrackNet) - 高速小球追踪模型
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) - 目标检测框架

---

## 球馆实时球速大屏（MVP）

除了原有的图像分析和比赛统计工具，本项目现在提供一个面向球馆的实时球速 MVP：每块场地创建独立会话，服务端计算当前球速、峰值、平均值并通过 WebSocket 推送到网页大屏或微信小程序。

### 启动实时大屏

```bash
pip install -r requirements.txt
python speed_api.py
```

然后打开 <http://127.0.0.1:7862>，填写球馆 ID、场地 ID，点击“创建实时会话”，再用“模拟击球”按钮查看实时效果。小程序端代码位于 `miniprogram/`，可用微信开发者工具导入。

### 给真实摄像头接入的位置

真实链路是：固定摄像头 → TrackNet / YOLO 等检测器识别球心 → 通过场地标定得到像素/米 → 向 `/ws/sessions/{session_id}` 推送 `{"type":"point","x":123,"y":456,"timestamp":1720000000.12}`。当前按钮是用于验收产品交互和接口链路的模拟数据，不代表已经完成视频识别。

当前 MVP 使用进程内存保存会话，适合本地演示和单球馆验证；面向真实球馆部署时，还需要接入数据库、账号权限、设备管理、HTTPS/WSS、异常告警和多租户隔离。

---

## License

MIT License - 详见 [LICENSE](./LICENSE)

---

## 作者

郭嘉辉 | 计算机与数据科学 | 羽毛球二级裁判员
