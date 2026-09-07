# 分享版验收记录

日期：2026-09-07。Windows 本机，Python 3.12 项目环境，原生前端。

## 已通过

- Python unittest：24 项全部通过。包括五阶段 16 节点确认门槛、重做失效、暂停丢弃迟到结果、失败重试、资料检索失败不推进，以及分享版访客隔离与连接边界。
- 两套模型协议使用模拟响应验证：Anthropic messages、OpenAI Chat Completions。覆盖认证头、URL 组合、正文提取、用量归一、错误响应脱敏、缺少配置不读取个人环境变量。
- 访客测试覆盖独立列表、读取/操作/ZIP/单文档越权拒绝、凭据不落盘、过期、断开、重启后档案保留而连接失效。
- 远端边界通过 TestClient 模拟验证：HTTPS、可信 Host/Origin、CSRF、Secure/HttpOnly Cookie、超大请求、输入校验不回显密钥。
- 网络边界验证：私网、字面 IP、混合 DNS 结果、非标准端口拒绝；Fake-IP 仅本机允许；实际连接使用已校验 IP 并保留原始 TLS 域名。
- Markdown 测试通过：嵌套列表、表格、来源链接和危险 HTML 内容处理。
- 不含凭据的真实 HTTPS 页面请求成功（HTTP 200）。
- 小规模真实检索：1 条查询，4 个来源，1 个获取正文。结果代表本次网络条件，不保证每次相同。

## 实际浏览器

使用 Playwright CLI，1440×1000 桌面与 390×844 手机尺寸，检查首页浅色/深色、设置弹窗、问答工作区、文档表格及移动端布局，无横向溢出。

在独立的 loopback QA 服务运行 tests/browser_fixture.py，使用明确标记的模型和来源夹具，完成：

1. 未连接时从开始备赛进入模型设置。
2. 填写自定义协议、地址、模型 ID 与测试密钥，测试、连接，成功后清空密钥输入框。
3. 创建备赛，初次问题不能跳过，回答后出现确认按钮。
4. 确认进入搜索计划，展示三条查询；再次确认后生成来源。
5. 下载 ZIP，刷新后恢复档案与临时连接。
6. 第二个独立浏览器上下文没有前者连接或档案，读取/修改/下载前者档案均被拒绝；可连接自己的独立测试模型。
7. 断开连接后保留档案；浏览器 localStorage/sessionStorage 没有测试密钥；无 JavaScript 未捕获异常。

浏览器下载的 ZIP 核对通过：五份阶段文档、一份总稿及来源记录，共 7 个有效 UTF-8 文件。本次只运行到资料阶段，导出正确标记为未完成草稿；完整 16 节点与最终导出由离线流程测试覆盖。

截图与下载在 output/playwright/，仅供本地验收，不纳入源码分发。

## 限制

本轮没有读取或使用开发者的个人 API，因此新适配层尚未通过使用者真实付费模型的完整五阶段调用。网页的连接按钮会用使用者自行填写的 API 进行实际测试。

没有公开部署；模拟 HTTPS 测试不等于真实域名、证书、代理或服务器部署验收。托管侧要求见 HOSTING.md。

Starlette TestClient 对现有 httpx 依赖发出弃用提醒，未影响本轮测试结果。没有为此安装新全局依赖。

## 复现

```powershell
.runtime/python.exe -m unittest discover -s tests -v
node tests/markdown.test.mjs
.runtime/python.exe tests/live_probe.py
.runtime/python.exe tests/verify_live_export.py output/playwright/sharing-qa-export.zip
```

浏览器夹具仅绑定 127.0.0.1:8767，绝不作为生产入口。tests/browser_checks.js 由 Playwright CLI 的 run-code --filename 执行，需要新访客浏览器上下文；其中均为假密钥与非真实模型输出。
