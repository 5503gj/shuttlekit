# ShuttleKit 微信小程序端

这是球馆实时球速 MVP 的小程序端骨架，和 `speed_api.py` 共用同一套会话与 WebSocket 接口。

## 本地体验

1. 在项目根目录启动服务：`python speed_api.py`
2. 使用微信开发者工具导入本目录。
3. 开发工具中勾选“不校验合法域名”，将 `app.js` 的 `apiBaseUrl` 和 `wsBaseUrl` 保持为本机地址。
4. 点击“连接场地”，再点击“模拟击球”。

页面下方的“装备推荐”会调用 `/api/equipment/recommend`，按装备类型、水平、预算和打法返回带来源的推荐结果。

真机或上线时，需要将地址替换为备案域名，并使用 HTTPS / WSS；还需要在微信公众平台配置 request 合法域名和 socket 合法域名。
