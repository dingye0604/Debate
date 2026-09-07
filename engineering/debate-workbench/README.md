# 辩序 · AI 备赛工作台

在网页输入辩题与持方，由 AI 教练按 skill 分阶段提问、讨论、检索和整理，最后下载五份阶段文档、合并总稿及来源记录。每位访客自行连接模型，没有开发者 API 作为默认连接。

## 本机使用

现有项目可双击根目录「启动备赛.cmd」。源码压缩包解压后，先在应用目录准备独立环境：

```powershell
conda env create --prefix .runtime --file environment.yml
.runtime/python.exe run.py
```

已有环境不要重复创建。Windows 也可使用包内 start.cmd。默认打开 http://127.0.0.1:8766，运行期间保留服务进程。本机不需要额外租服务器，但模型 API 和资料检索需要联网。

1. 打开「连接你的模型」，选择 OpenAI 兼容或 Anthropic 兼容协议。
2. 填写服务商提供的 HTTPS Base URL、真实模型 ID 与 API Key。不要将 Markdown 链接或 Claude Code 的模型别名后缀直接当作接口地址或模型 ID。
3. 点击「测试连接」或「连接模型」。两者都会发送一次小规模请求；连接成功后密钥输入框清空。
4. 输入完整辩题、持方，按需填写赛制及日期，开始备赛。
5. 回答教练问题，核对草稿并确认。搜索方案确认后才执行检索；每个步骤均可继续修改。
6. 下载 ZIP 或 Markdown；未完成时导出会标明草稿与待生成状态。

Base URL 可包含服务商的网关路径。末尾已含 /v1 时不重复添加；OpenAI 兼容调用 /chat/completions，Anthropic 兼容调用 /messages。仅支持公网域名、HTTPS 和 443 端口，不支持浏览器直连、本机模型 HTTP 接口或任意自定义请求头。模型需要能按提示输出 JSON；连接测试成功不代表所有模型都能稳定执行完整备赛流程。

## 访客与隐私

- 通过 HttpOnly Cookie 识别访客。档案、列表、操作、下载和运行任务均按访客隔离。
- 每个 API Key 只在当前后端进程内存中暂存两小时；到期或断开会暂停任务，重启后需重新连接。
- 应用不读取开发者 Claude Code 配置或模型环境变量，不把密钥写入磁盘、日志、浏览器持久存储或下载文件。
- 后端负责转发模型请求，因此后端会接触使用者提交的密钥。远端使用应信任站点维护者；模型服务商会收到备赛上下文。
- 档案保存在运行服务的电脑或服务器；Cookie 保留 30 天。清除 Cookie、更换浏览器或设备后，此版本没有账号找回功能，请及时下载。
- 新档案位于 data/workspaces/。旧版 data/sessions/ 保持原样，不会分配给新访客。
- 暂停请求不能撤销服务商已经发生的 API 计费。

## 流程与文件

五阶段：辩题分析 → 资料整合 → 立论架构 → 论据手册 → 攻防模拟。共 16 个确认节点。来源区分搜索摘要与已获取正文；获取正文不等于内容已获权威认证。重做阶段会保存旧版本并将后续章节标记为需更新。

ZIP 含五份阶段 Markdown、一份合并总稿和来源记录 JSON。暂不直接导出 Word/PDF。

## 远端分享

见 HOSTING.md。当前实现适合单进程、小规模访客分享；必须部署一个可运行 Python 的后端，不能只上传到静态网页托管。密钥保管和任务调度使用进程内存，不支持多 worker、多个副本或无状态函数自动扩缩容。本轮没有公开部署。

## 开发与验证

- app.py：同源 API、访客认证、限流与下载。
- visitors.py：临时连接与访客工作空间。
- provider.py / network.py：模型协议、HTTPS 公网地址校验及 DNS 地址固定。
- engine.py / workflow.py / skill/：备赛流程与确认约束。
- static/：原生网页、玻璃材质、深浅主题和安全 Markdown 渲染。
- data/、backups/、test-artifacts/、output/：私人数据或本地产物，不应分发。

```powershell
.runtime/python.exe -m unittest discover -s tests -v
node tests/markdown.test.mjs
.runtime/python.exe package_source.py
```

测试使用明确的模型与搜索替身；不会自动调用个人 API。实际浏览器检查方法、结果和限制见 VERIFICATION.md。requirements-lock.txt 记录当前 Windows 环境的完整安装版本；environment.yml 与 requirements.txt 为通常的安装入口。

## 设计与协议参考

界面以 CSS 近似 Liquid Glass 的通透层次，玻璃用于导航与控件，长文区域保留实色底，并支持减少动效与透明度降级。不是 Apple 原生组件。

- [Apple Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
- [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)
- Marked 的许可保留在 static/vendor/marked-LICENSE.md。
