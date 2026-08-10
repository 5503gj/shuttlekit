"""ShuttleKit 的轻量网页入口。

运行：
    python badminton_web.py

网页默认监听 http://127.0.0.1:7861。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import gradio as gr

from court_config import CourtDetector
from court_lighting import analyze_court_lighting
from equipment_kb.recommender import EquipmentRecommender, PlayerProfile
from match_stats.recorder import MatchRecorder
from match_stats.visualize import StatsVisualizer


STYLE = """
body { background: #f5f7fb; }
.shuttle-shell { max-width: 1180px; margin: 0 auto; }
.hero { padding: 28px 8px 8px; }
.hero h1 { font-size: 34px; letter-spacing: -0.04em; }
.hero p { color: #667085; font-size: 16px; }
.panel { border: 1px solid #e6eaf0; border-radius: 18px; }
"""


def _empty_message() -> str:
    return "请先上传一张 JPG 或 PNG 图片。"


def analyze_lighting(image_path: str | None) -> str:
    if not image_path:
        return _empty_message()
    try:
        report = analyze_court_lighting(image_path)
        suggestions = "\n".join(f"- {item}" for item in report.suggestions) or "- 暂无额外建议"
        return (
            f"### 灯光评估\n"
            f"- 平均亮度：**{report.mean_brightness:.1f} / 255**（{report.brightness_pct:.1f}%）\n"
            f"- 亮度均匀度：**{report.uniformity:.2f}**\n"
            f"- 眩光区域：**{report.glare_regions}** 处\n"
            f"- 结论：**{report.conclusion}**\n\n"
            f"**改进建议**\n{suggestions}"
        )
    except Exception as exc:
        return f"处理失败：{exc}"


def detect_court(image_path: str | None):
    if not image_path:
        return None, _empty_message()
    try:
        output_dir = Path(tempfile.mkdtemp(prefix="shuttlekit-court-"))
        output_path = output_dir / "court_detection.jpg"
        result = CourtDetector().detect(image_path, str(output_path))
        report = (
            f"### 场地检测\n"
            f"- 检测线段：**{result.line_count}**\n"
            f"- 角点数量：**{len(result.corners)}**\n"
            f"- 场地判断：**{result.court_type}**\n"
            f"- 边界线：**{'有' if result.has_boundary else '无'}**\n"
            f"- 发球线：**{'有' if result.has_service_line else '无'}**\n"
            f"- 中线：**{'有' if result.has_center_line else '无'}**"
        )
        return str(output_path), report
    except Exception as exc:
        return None, f"处理失败：{exc}"


def build_match_report(player_a: str, player_b: str, rows: str):
    try:
        recorder = MatchRecorder(player_a or "A", player_b or "B")
        for line_number, raw_line in enumerate((rows or "").splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 4:
                raise ValueError(f"第 {line_number} 行需要：发球方,得分方,击球类型,时长")
            server, winner, shot_type, duration = parts
            recorder.add_point(server, winner, shot_type, float(duration))

        if not recorder.data.points:
            raise ValueError("至少输入一条回合记录")

        output_dir = Path(tempfile.mkdtemp(prefix="shuttlekit-match-"))
        StatsVisualizer().generate_dashboard(recorder.data, str(output_dir))
        report = (
            f"### 比赛摘要\n"
            f"- 对阵：**{recorder.data.player_a} vs {recorder.data.player_b}**\n"
            f"- 最终比分：**{recorder.data.final_score()}**\n"
            f"- 总回合：**{recorder.data.total_rallies()}**\n"
            f"- 平均回合时长：**{recorder.data.avg_rally_duration():.1f} 秒**\n\n"
            f"击球分布：{recorder.data.shot_distribution()}"
        )
        return (
            report,
            str(output_dir / "score_curve.png"),
            str(output_dir / "shot_distribution.png"),
            str(output_dir / "rally_duration.png"),
        )
    except Exception as exc:
        return f"处理失败：{exc}", None, None, None


def recommend_equipment(level: str, budget: float, play_style: str, gender: str) -> str:
    try:
        profile = PlayerProfile(level, int(budget), play_style, gender)
        return EquipmentRecommender().format_recommendation(profile)
    except Exception as exc:
        return f"推荐失败：{exc}"


with gr.Blocks(css=STYLE, title="ShuttleKit 羽毛球工具箱") as demo:
    with gr.Column(elem_classes="shuttle-shell"):
        gr.Markdown(
            "# ShuttleKit\n"
            "把场馆、比赛和器材信息放在一个轻量工具箱里。\n\n"
            "> 当前版本优先演示稳定的图片分析、比赛统计和器材推荐；所有处理均在本机完成。",
            elem_classes="hero",
        )

        with gr.Tab("场馆图片分析"):
            with gr.Row():
                with gr.Column(elem_classes="panel"):
                    court_image = gr.Image(
                        type="filepath",
                        sources=["upload", "webcam"],
                        label="上传场馆照片",
                    )
                    with gr.Row():
                        lighting_button = gr.Button("评估灯光", variant="primary")
                        court_button = gr.Button("检测场地线")
                with gr.Column(elem_classes="panel"):
                    lighting_output = gr.Markdown("灯光报告会显示在这里。")
                    court_output = gr.Markdown("场地检测报告会显示在这里。")
            court_annotated = gr.Image(label="场地标注结果", type="filepath")
            lighting_button.click(analyze_lighting, court_image, lighting_output)
            court_button.click(detect_court, court_image, [court_annotated, court_output])

        with gr.Tab("比赛数据看板"):
            gr.Markdown("每行格式：`发球方,得分方,击球类型,回合时长`，例如 `A,A,杀球,8.2`。")
            with gr.Row():
                player_a = gr.Textbox(value="选手 A", label="选手 A")
                player_b = gr.Textbox(value="选手 B", label="选手 B")
            match_rows = gr.Textbox(
                value="A,A,杀球,8.2\nB,B,网前小球,6.4\nA,A,高远球,10.1",
                lines=7,
                label="回合记录",
            )
            match_button = gr.Button("生成比赛看板", variant="primary")
            match_report = gr.Markdown()
            with gr.Row():
                score_chart = gr.Image(label="比分曲线")
                shot_chart = gr.Image(label="击球分布")
                duration_chart = gr.Image(label="回合时长")
            match_button.click(
                build_match_report,
                [player_a, player_b, match_rows],
                [match_report, score_chart, shot_chart, duration_chart],
            )

        with gr.Tab("器材推荐"):
            with gr.Row():
                level = gr.Dropdown(["入门", "初级", "中级", "高级"], value="初级", label="水平")
                budget = gr.Number(value=500, minimum=100, label="预算（元）")
                play_style = gr.Dropdown(["进攻", "防守", "全能", "前场快攻"], value="全能", label="打法")
                gender = gr.Dropdown(["男", "女"], value="男", label="性别")
            equipment_button = gr.Button("生成推荐", variant="primary")
            equipment_output = gr.Textbox(lines=18, label="推荐结果")
            equipment_button.click(
                recommend_equipment,
                [level, budget, play_style, gender],
                equipment_output,
            )


if __name__ == "__main__":
    demo.launch(
        server_name=os.getenv("HOST", "127.0.0.1"),
        server_port=int(os.getenv("PORT", "7861")),
        show_error=True,
    )
