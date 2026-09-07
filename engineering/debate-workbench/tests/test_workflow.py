import asyncio
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from config import AppError
from engine import Engine
from store import Store
from documents import documents, zip_bytes
from model import parse_reply
from workflow import STEPS

class FakeModel:
    async def generate(self, s):
        step = STEPS[s["index"]]
        return {"message": "请说明你的判断。", "section": "讨论结果 [S1]" if s["sources"] else "讨论草稿",
                "ready": True, "queries": ["学理", "案例", "对方"] if step.plan else []}, {"input_tokens": 1, "output_tokens": 1}

class FakeSearch:
    async def run(self, queries):
        return [{"query": q, "count": 1} for q in queries], [
            {"title": "测试用来源（非真实证据）", "url": "https://example.com/evidence",
             "snippet": "离线测试", "text": "", "status": "测试夹具", "query": queries[0]}]

class FailingModel:
    async def generate(self, s):
        raise AppError("测试超时")

class SlowModel:
    async def generate(self, s):
        await asyncio.sleep(60)

class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Keep test outputs distinct; no user data or original files are removed.
        self.root = Path("test-artifacts") / ("unit-" + __import__("uuid").uuid4().hex)
        self.store = Store(self.root)
        self.engine = Engine(self.store, FakeModel(), FakeSearch())
        self.s = self.store.create("技术发展让生活更好 / 更不好", "正方", "", "")

    async def settle(self):
        tasks = list(self.engine.tasks.values())
        if tasks:
            await asyncio.gather(*tasks)
        return self.store.get(self.s["id"])

    async def test_all_five_phases_and_gates_and_zip(self):
        self.engine.start(self.s)
        s = await self.settle()
        for index, step in enumerate(STEPS):
            self.assertEqual(s["index"], index)
            self.assertFalse(s["nodes"][step.key].get("confirmed", False))
            if step.answer:
                with self.assertRaises(AppError):
                    self.engine.action(s["id"], "confirm", s["revision"])
                self.engine.action(s["id"], "reply", s["revision"], "我的理由是具体判断。")
                s = await self.settle()
            old_revision = s["revision"]
            self.engine.action(s["id"], "confirm", s["revision"])
            with self.assertRaises(AppError):
                self.engine.action(s["id"], "confirm", old_revision)
            s = await self.settle()
        self.assertEqual(s["status"], "complete")
        self.assertEqual([d["state"] for d in documents(s)], ["已确认"] * 5)
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes(s)))
        self.assertEqual(len(archive.namelist()), 7)
        self.assertIn("论据", archive.read("04-论据手册.md").decode("utf-8"))
        self.assertNotIn("token", archive.read("来源记录.json").decode("utf-8"))
        self.assertEqual(self.store.get(s["id"])["index"], len(STEPS))

    async def test_plan_draft_exposes_user_confirmation_even_when_model_waits(self):
        class WaitingModel(FakeModel):
            async def generate(self, s):
                result, usage = await super().generate(s)
                result['ready'] = False
                return result, usage
        self.engine.model = WaitingModel()
        s = self.s
        s['index'] = 1
        self.store.save(s)
        self.engine.start(s)
        s = await self.settle()
        self.assertTrue(s['nodes']['research_plan']['ready'])
        self.assertFalse(s['nodes']['research_plan']['confirmed'])
        self.assertEqual(s['sources'], [])

    async def test_failure_retry_and_recovery(self):
        self.engine.model = FailingModel()
        self.engine.start(self.s)
        s = await self.settle()
        self.assertEqual(s["status"], "error")
        self.assertEqual(s["index"], 0)
        self.engine.model = FakeModel()
        self.engine.action(s["id"], "retry", s["revision"])
        s = await self.settle()
        self.assertEqual(s["status"], "waiting")
        s["status"] = "running"
        self.store.save(s)
        self.store.recover()
        self.assertEqual(self.store.get(s["id"])["status"], "error")

    async def test_pause_discards_late_results(self):
        self.engine.model = SlowModel()
        self.engine.start(self.s)
        await asyncio.sleep(0)
        s = self.store.get(self.s["id"])
        self.engine.action(s["id"], "pause", s["revision"])
        await self.settle()
        self.assertEqual(self.store.get(s["id"])["status"], "paused")
        self.assertFalse(self.store.get(s["id"])["history"])

    async def test_rework_invalidates_downstream_and_requires_new_answer(self):
        s = self.s
        s["index"] = 5
        for step in STEPS[:6]:
            s["nodes"][step.key] = {"section": "旧内容", "confirmed": True, "ready": True, "answered": True,
                                   "turns": [{"role": "user", "content": "旧答案"}]}
        self.store.save(s)
        self.engine.action(s["id"], "rework", s["revision"], target=3)
        s = await self.settle()
        self.assertFalse(s["nodes"]["definitions"]["ready"])
        self.assertTrue(s["nodes"]["arguments"]["stale"])
        self.assertEqual(documents(s)[2]["state"], "需更新")
        self.engine.action(s["id"], "reply", s["revision"], "新的定义")
        s = await self.settle()
        self.engine.action(s["id"], "confirm", s["revision"])
        s = await self.settle()
        self.assertFalse(s["nodes"]["arguments"]["ready"])
        self.assertFalse(s["nodes"]["arguments"]["answered"])
        self.assertTrue(list((self.store.folder(s["id"]) / "versions").glob("*.json")))

    async def test_search_failure_cannot_advance(self):
        class EmptySearch:
            async def run(self, queries):
                return [], []
        self.engine.search = EmptySearch()
        s = self.s
        s["index"] = 2
        s["nodes"]["research_plan"] = {"confirmed": True, "queries": ["test"]}
        self.store.save(s)
        self.engine.start(s)
        s = await self.settle()
        self.assertEqual(s["status"], "error")
        self.assertEqual(s["sources"], [])
        with self.assertRaises(AppError):
            self.engine.action(s["id"], "confirm", s["revision"])

    def test_bad_json_and_traversal(self):
        with self.assertRaises(AppError):
            parse_reply('{"ready":true}')
        with self.assertRaises(AppError):
            self.store.get("../outside")
        parsed = parse_reply('{"message":"问题","section":"草稿","ready":false,"queries":[]}')
        self.assertFalse(parsed["ready"])

if __name__ == "__main__":
    unittest.main()
