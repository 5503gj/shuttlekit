# 照片曝光分析

`analyze_court_lighting(path, roi=None)`输出灰度均值、图像均匀度和高亮区域。
这些值不能换算lux或证明场馆照度/BWF合规。报告明确标为未测量；ROI越界会拒绝。
实际照度需要校准照度计、适用版本及测量网格，参见../docs/BWF_STANDARDS.md。
