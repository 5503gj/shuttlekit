# 如何把 ShuttleKit 上传到 GitHub

## 前提
- 你需要有一个 GitHub 账号（去 github.com 注册，免费）
- 仓库已在本地 git init + commit 完成

## 步骤

### Step 1: 在 GitHub 网站创建空仓库

1. 登录 https://github.com
2. 点右上角 **+** → **New repository**
3. 填写：
   - Repository name: `ShuttleKit`
   - Description: `羽毛球智能分析工具箱：球速检测、场馆灯光、场地配置、比赛统计、器材推荐`
   - 选 **Public**（公开，让面试官能看）
   - **不要**勾选 "Add a README file"（本地已经有了）
   - **不要**勾选 "Add .gitignore"（本地已经有了）
   - License 选 "MIT License"（本地已有，可跳过）
4. 点 **Create repository**

### Step 2: 把本地代码推送到 GitHub

GitHub 会给你一段命令，你只需要运行这两行（把 `你的用户名` 换成你的 GitHub 用户名）：

```bash
cd "C:/Users/郭嘉辉/WorkBuddy/2026-08-10-19-10-43/badminton-toolkit"

git remote add origin https://github.com/你的用户名/ShuttleKit.git
git push -u origin main
```

系统会弹出 GitHub 登录窗口，登录后自动推送。

### Step 3: 验证

打开 `https://github.com/你的用户名/ShuttleKit`，你应该能看到所有代码和 README。

### Step 4: 把 GitHub 链接写进简历

在简历的"项目经历"或"个人作品"区写：
> **ShuttleKit - 羽毛球智能分析工具箱** | GitHub: github.com/你的用户名/ShuttleKit
> - 独立设计并开发羽毛球综合分析工具箱，包含 6 个模块
> - 使用 Python + OpenCV 实现场馆灯光评估、场地线检测、球速计算
> - 实现比赛数据记录与可视化看板（比分曲线/击球分布/HTML 看板）
> - 编写 39 个测试用例，覆盖正常/边界/异常场景
> - 技术栈：Python, OpenCV, NumPy, Matplotlib, pytest

---

## 如果遇到问题

### Q: push 时报错 "rejected - non-fast-forward"
说明远程有内容。运行：
```bash
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Q: 中文文件名显示为乱码
```bash
git config core.quotepath false
```

### Q: 想修改仓库为 Private
GitHub → 仓库 → Settings → 最底部 Danger Zone → Change visibility

### Q: 想删除仓库重来
GitHub → 仓库 → Settings → 最底部 Danger Zone → Delete this repository
