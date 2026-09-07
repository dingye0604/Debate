import io
import json
import zipfile
from workflow import STEPS, PHASES, FILES

def documents(session):
    result = []
    for phase, name in enumerate(FILES):
        entries = [(step, session["nodes"].get(step.key, {})) for step in STEPS if step.phase == phase]
        present = [(step, node) for step, node in entries if node.get("section")]
        stale = any(node.get("stale") for _, node in present)
        confirmed = bool(present) and all(node.get("confirmed") and not node.get("stale") for _, node in entries)
        state = "需更新" if stale else "已确认" if confirmed else "草稿" if present else "待生成"
        text = f"# {PHASES[phase]}\n\n辩题：{session['topic']}\n\n持方：{session['side']} · 赛制：{session['format'] or '未指定'}\n\n状态：{state}\n\n"
        if stale:
            text += "> 上游内容已修改，以下旧章节尚未重新确认，不应用作最终定稿。\n\n"
        for step, node in present:
            text += f"## {step.title}\n\n{node['section']}\n\n"
        if not present:
            text += "本阶段尚未生成。\n"
        cited = [s for s in session["sources"] if f"[{s['id']}]" in text]
        if cited:
            text += "## 来源记录\n\n"
            for s in cited:
                text += f"- [{s['id']}] {s['title']} — {s['url']}\n  - {s['status']}\n"
        result.append({"name": name, "phase": phase, "state": state, "content": text, "available": bool(present)})
    return result

def merged(session):
    head = f"# 备赛总档案\n\n{session['topic']}\n\n"
    head += "状态：" + ("全部流程已确认" if session["index"] == len(STEPS) else "备赛进行中，包含草稿或待生成章节") + "\n\n"
    return head + "\n\n---\n\n".join(d["content"] for d in documents(session))

def zip_bytes(session):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for doc in documents(session):
            archive.writestr(doc["name"], doc["content"])
        archive.writestr("00-备赛总档案.md", merged(session))
        source_rows = [{k: s.get(k, "") for k in ("id", "title", "url", "status", "query")} for s in session["sources"]]
        archive.writestr("来源记录.json", json.dumps(source_rows, ensure_ascii=False, indent=2))
    return data.getvalue()
