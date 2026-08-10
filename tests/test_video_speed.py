import cv2
import numpy as np

from shuttle_speed.video_speed import VideoSpeedAnalyzer


def _make_demo_video(path):
    width, height, fps = 640, 480, 30
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame_index in range(8):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.rectangle(frame, (60, 60), (580, 420), (255, 255, 255), 3)
        for y in (120, 180, 300, 360, 390, 405):
            cv2.line(frame, (60, y), (580, y), (255, 255, 255), 2)
        for x in (180, 260, 380, 460):
            cv2.line(frame, (x, 60), (x, 420), (255, 255, 255), 2)
        cv2.circle(frame, (90 + frame_index * 70, 240), 5, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()


def test_video_analyzer_estimates_court_and_speed(tmp_path):
    video_path = tmp_path / "demo.mp4"
    _make_demo_video(video_path)

    report = VideoSpeedAnalyzer().analyze(str(video_path), video_name="demo.mp4")

    assert report.total_frames == 8
    assert report.detected_frames >= 4
    assert report.court.length_m == 13.4
    assert report.court.width_m in (5.18, 6.1)
    assert report.peak_speed_kmh > 0
    assert report.shot_type in {"疑似杀球", "快速平抽", "高远球/快球", "慢速击球"}


def test_video_analyzer_classifies_smash_threshold():
    analyzer = VideoSpeedAnalyzer(smash_threshold_kmh=260)
    shot_type, confidence = analyzer._classify_shot(300, 0.8, 0.8)
    assert shot_type == "疑似杀球"
    assert confidence > 0.6
