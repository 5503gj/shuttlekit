# ShuttleKit在线训练实验室部署

公开入口：https://5503gj.github.io/shuttlekit/ 。访客不需要安装Python、不需要Key或账号。

浏览器Worker运行原有会话、速度计算、训练教练、装备推荐与候选点检测算法。支持模拟、轨迹JSON导入/导出、回放、训练清单、报告与视频分析。

## 能力与数据边界

在线版会话仅存在本页面，不提供云端实时多设备同步。视频通过浏览器解码最多60秒/50MiB、720p/10Hz/600帧采样，输入原视频比例后同步缩放；不适合专业高速测速。

原有Python服务不被替换。浏览器版与服务版的存储和连接方式不同，不能把页面会话当作企业持久化、云端同步或身份认证。

## 构建与验证

运行 `python scripts/build_online.py`，再运行 `npm run test:online`。构建目录dist仅包含公开资源，不包含.git、.env或服务端密钥。dist和运行时缓存忽略提交。

工作流 `.github/workflows/test.yml` 在原测试通过后构建、执行在线浏览器回归；仅main推送发布，部署依赖测试成功。浏览器测试以子目录路径提供资源，实际调用工具和导出，验证响应式并检查没有本地API或上传请求。

## Python/WebAssembly运行时

使用[Pyodide官方Worker模式](https://pyodide.org/en/0.28.3/usage/webworker.html)及[包目录](https://pyodide.org/en/0.28.3/usage/packages-in-pyodide.html)，锁定0.28.3。构建时获取运行时与wheel并校验锁文件及包SHA256，随后全部发布在本站，不在访客运行时依赖外部CDN。许可证随runtime/LICENSE提供，各wheel保留自身许可证。

Python算法源码由构建脚本从原模块打包进python-source.zip，避免另写一套近似算法。浏览器版OpenCV等依赖版本由Pyodide锁定，与服务版的像素输出不承诺逐位完全相同。
