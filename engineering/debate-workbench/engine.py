import asyncio
import copy
from config import AppError
from documents import documents
from store import now
from workflow import STEPS, PHASES, step_info

class Engine:
    def __init__(self, store, model, search):
        self.store, self.model, self.search = store, model, search
        self.tasks = {}

    def view(self, s):
        data = copy.deepcopy(s)
        data["step"] = step_info(s["index"])
        data["steps"] = [step_info(i) for i in range(len(STEPS))]
        data["phases"] = PHASES
        data["documents"] = documents(s)
        for source in data["sources"]:
            source.pop("text", None)
        return data

    def start(self, s):
        self._launch(s)
        return self.view(s)

    def action(self, sid, action, revision, text="", target=None):
        # No await between read, version validation and save: one event-loop worker.
        s = self.store.get(sid)
        if revision != s["revision"]:
            raise AppError("页面进度已更新，请刷新后再操作。")
        if s["status"] == "running" and action != "pause":
            raise AppError("当前正在生成，请等待或先暂停。")
        if action == "pause":
            if s["status"] != "running":
                raise AppError("当前没有运行中的任务。")
            task = self.tasks.get(sid)
            if task:
                task.cancel()
            s["revision"] += 1
            s["status"] = "paused"
            s["error"] = ""
            self.store.save(s)
            return self.view(s)
        if action == "rework":
            if target is None or target < 0 or target >= len(STEPS) or target > s["index"]:
                raise AppError("只能重新讨论当前或之前的节点。")
            if STEPS[target].key not in s["nodes"]:
                raise AppError("该节点尚未开始。")
            self.store.archive(s)
            for step in STEPS[target:]:
                node = s["nodes"].get(step.key)
                if node:
                    node.update(stale=True, confirmed=False, ready=False)
            step = STEPS[target]
            s["nodes"][step.key] = {"turns": [], "answered": False, "section": "", "ready": False}
            s["index"] = target
            s["pending"] = {"kind": "generate"}
            self._launch(s)
            return self.view(s)
        if s["index"] >= len(STEPS):
            raise AppError("本场备赛已完成，可以下载或重新讨论已有节点。")
        step = STEPS[s["index"]]
        node = s["nodes"].setdefault(step.key, {"turns": [], "answered": False, "section": "", "ready": False})
        if action == "confirm":
            if s["status"] != "waiting" or not node.get("ready") or (step.answer and not node.get("answered")):
                raise AppError("请先完成本节点问答与文档生成，再确认继续。")
            node["confirmed"] = True
            s["history"].append({"role": "event", "text": "已确认：" + step.title, "step": step.key, "time": now()})
            s["index"] += 1
            if s["index"] == len(STEPS):
                s.update(status="complete", pending=None, revision=s["revision"] + 1)
                self.store.save(s)
                return self.view(s)
            next_step = STEPS[s["index"]]
            if s["nodes"].get(next_step.key, {}).get("stale"):
                s["nodes"][next_step.key] = {"turns": [], "answered": False, "section": "", "ready": False}
            s["pending"] = {"kind": "generate"}
        elif action == "reply":
            if not text.strip():
                raise AppError("请填写你的回答或修改意见。")
            node["turns"].append({"role": "user", "content": text.strip()})
            node["answered"] = True
            node["ready"] = False
            s["history"].append({"role": "user", "text": text.strip(), "step": step.key, "time": now()})
            s["pending"] = {"kind": "generate"}
        elif action == "retry":
            if s["status"] not in ("error", "paused", "idle"):
                raise AppError("只有失败或暂停的步骤需要重试。")
            s["pending"] = s.get("pending") or {"kind": "generate"}
        elif action == "search":
            if not step.search:
                raise AppError("请在资料整合或针对性论据阶段补充搜索。")
            query = text.strip()
            if not query or len(query) > 120:
                raise AppError("请输入不超过120字的补充搜索词。")
            s["pending"] = {"kind": "search", "queries": [query]}
            s["history"].append({"role": "event", "text": "补充搜索：" + query, "step": step.key, "time": now()})
        else:
            raise AppError("不支持的操作。")
        self._launch(s)
        return self.view(s)

    def _launch(self, s):
        s.update(status="running", error="", revision=s["revision"] + 1)
        s["pending"] = s.get("pending") or {"kind": "generate"}
        self.store.save(s)
        task = asyncio.create_task(self.run(s["id"], s["revision"]))
        self.tasks[s["id"]] = task
        def finished(t):
            if self.tasks.get(s["id"]) is t:
                self.tasks.pop(s["id"], None)
        task.add_done_callback(finished)

    def _current(self, sid, revision):
        s = self.store.get(sid)
        if s["revision"] != revision or s["status"] != "running":
            raise asyncio.CancelledError()
        return s

    async def run(self, sid, revision):
        try:
            s = self._current(sid, revision)
            step = STEPS[s["index"]]
            node = s["nodes"].setdefault(step.key, {"turns": [], "answered": False, "section": "", "ready": False})
            if step.search and (not node.get("searched") or s["pending"]["kind"] == "search"):
                queries = s["pending"].get("queries")
                if not queries:
                    previous = STEPS[s["index"] - 1]
                    plan = s["nodes"].get(previous.key, {})
                    if not plan.get("confirmed"):
                        raise AppError("搜索方案尚未确认。")
                    queries = plan.get("queries", [])
                if not queries:
                    raise AppError("缺少检索词，请返回搜索方案节点补充。")
                runs, sources = await self.search.run(queries)
                s = self._current(sid, revision)
                node = s["nodes"].setdefault(step.key, node)
                for source in sources:
                    source["id"] = f"S{len(s['sources']) + 1}"
                    source["step"] = step.key
                    s["sources"].append(source)
                s["search_runs"].extend([{**run, "step": step.key, "time": now()} for run in runs])
                if not sources:
                    self.store.save(s)
                    raise AppError("本轮联网检索没有获得结果，可能是搜索服务或网络限制。流程已暂停；请重试，或输入更具体的词补搜。不会以模型记忆伪装检索结果。")
                node["searched"] = True
                s["pending"] = {"kind": "generate"}
                self.store.save(s)
            # Refresh so retrieved sources and pending answers are included.
            s = self._current(sid, revision)
            result, usage = await self.model.generate(s)
            s = self._current(sid, revision)
            node = s["nodes"].setdefault(step.key, {"turns": [], "answered": False})
            self.store.archive(s)
            node.update(result)
            node.update(stale=False, confirmed=False)
            if not step.answer:
                node["ready"] = bool(node.get("section", "").strip())
            elif not node.get("answered"):
                node["ready"] = False
            node["turns"].append({"role": "assistant", "content": result["message"]})
            s["history"].append({"role": "assistant", "text": result["message"], "step": step.key, "time": now()})
            for key in ("input_tokens", "output_tokens"):
                s["usage"][key] += usage.get(key, 0)
            s.update(status="waiting", pending=None, revision=revision + 1)
            self.store.save(s)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            s = self.store.get(sid)
            if s["revision"] == revision and s["status"] == "running":
                s.update(status="error", error=str(exc) if isinstance(exc, AppError) else "本步骤处理失败，之前的文档已保留。请重试。", revision=revision + 1)
                self.store.save(s)
