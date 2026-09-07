"""Explicit loopback-only browser QA service. All model/search outputs are fixtures."""
import asyncio
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from config import Settings, AppError
from workflow import STEPS
import uvicorn

class FixtureProvider:
    async def probe(self,cfg):
        if not cfg.key.startswith("qa-") or cfg.base != "https://provider.example/v1":
            raise AppError("测试环境仅接受明确的 QA 配置。")
        await asyncio.sleep(.05)

class FixtureModel:
    async def generate(self,s):
        await asyncio.sleep(.15)
        step=STEPS[s["index"]]
        answered=s["nodes"].get(step.key,{}).get("answered")
        message=("你的回答已整理。请核对下方草稿，再决定是否进入下一步。" if answered else
                 "这是浏览器验收夹具，不是真实模型输出。\n\n请先说明：\n1. 你如何界定“自由”？\n2. 你想比较哪些具体生活情境？\n3. 对方最有力的反驳是什么？")
        section="## 核心讨论\n\n这是**浏览器验收夹具**，仅用于检查界面和文档交互。\n\n| 概念 | 待确认判断 |\n| --- | --- |\n| 自由 | 选择的能力与现实机会 |\n| 技术 | 应区分工具和使用制度 |\n\n### 仍需检验\n\n- 定义是否一致\n- 因果链条是否充分\n"
        return {"message":message,"section":section,"ready":bool(answered) or not step.answer,
                "queries":["概念与定义","正方证据","反方视角"] if step.plan else []},{"input_tokens":1,"output_tokens":1}

class FixtureSearch:
    async def run(self,queries):
        return [{"query":q,"count":1} for q in queries],[{"title":"QA 来源（非真实证据）","url":"https://example.com","snippet":"仅供浏览器验收","text":"","query":queries[0],"status":"测试夹具"}]

if __name__=="__main__":
    settings=Settings(data=Path("test-artifacts")/("browser-"+uuid.uuid4().hex),origin="http://127.0.0.1:8767")
    uvicorn.run(create_app(settings,FixtureProvider(),lambda owner:FixtureModel(),FixtureSearch),
                host="127.0.0.1",port=8767,access_log=False,log_level="warning",proxy_headers=False)
