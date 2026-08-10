# 测试模块

本目录包含 ShuttleKit 各模块的测试用例和缺陷报告模板。

## 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行单个模块测试
pytest tests/test_lighting.py -v
pytest tests/test_match_stats.py -v
pytest tests/test_speed.py -v
pytest tests/test_config.py -v

# 生成测试报告
pytest tests/ -v --html=report.html
```

## 测试覆盖

| 测试文件 | 模块 | 用例数 | 覆盖范围 |
|---------|------|--------|---------|
| test_lighting.py | court_lighting | 12 | 亮度计算、眩光检测、均匀度、ROI、异常处理 |
| test_config.py | court_config | 10 | 线检测、角点、尺寸校验、球网高度 |
| test_speed.py | shuttle_speed | 8 | 速度计算、标定、对角线、边界条件 |
| test_match_stats.py | match_stats | 8 | 得分记录、击球分布、导出、空比赛 |

## 测试用例设计原则

1. **正常场景**：验证功能在标准输入下正确工作
2. **边界场景**：空输入、单点、极值
3. **异常场景**：文件不存在、依赖缺失
4. **输出验证**：报告格式、导出文件完整性

## 缺陷报告模板

发现问题时，复制 [DEFECT_TEMPLATE.md](./DEFECT_TEMPLATE.md) 填写并提交。
