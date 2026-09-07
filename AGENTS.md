# 辩论备赛工作台

- 默认中文；保留根目录原始资料及用户 skill，不移动或删除。
- 应用位于 engineering/debate-workbench/，使用 FastAPI 与原生网页；独立 Conda 环境 .runtime/。
- 本轮已批准 SHARING-PLAN.md：访客独立配置模型与工作空间，Liquid Glass 风格改版。默认仍仅绑定 127.0.0.1，公开部署另行批准。
- 禁止读取开发者 Claude Code 配置或个人模型环境变量。API 密钥仅在访客内存保管并设置有效期，不写磁盘、日志、浏览器持久存储或导出。
- 新数据在 data/workspaces/ 内按访客隔离；保留 data/sessions/ 旧档案，不向新访客提供。backups/ 保存改造前本地源码快照，不纳入分发包。
- 所有会话读取、操作、任务与下载必须检查访客归属。远端模式须 HTTPS、同源校验及公网目标限制。
- skill/ 为备赛流程依据，阶段确认由后端强制执行。
- 验证：.runtime/python.exe -m unittest discover -s tests -v；node tests/markdown.test.mjs；浏览器检查桌面/移动、主题、设置、问答及下载。模拟接口测试和真实 API 调用分别报告。
- 不自动提交、推送、公开发布、修改用户密钥配置或删除文件。分发包使用明确白名单，排除 data/、backups/、缓存、运行环境及测试产物。
