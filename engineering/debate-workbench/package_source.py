"""Build a clean, allowlisted source ZIP. Private directories are never traversed."""
import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FILES=[
    "app.py","config.py","documents.py","engine.py","model.py","network.py","provider.py",
    "run.py","search.py","store.py","visitors.py","workflow.py","package_source.py",
    "README.md","HOSTING.md","VERIFICATION.md","requirements.txt","requirements-lock.txt",
    "environment.yml","start.cmd",
    "skill/SKILL.md","skill/WEB-RULES.md",
    "static/index.html","static/style.css","static/app.js","static/markdown.mjs","static/favicon.svg",
    "static/vendor/marked.mjs","static/vendor/marked-LICENSE.md",
    "tests/test_api.py","tests/test_boundaries.py","tests/test_model.py","tests/test_network.py",
    "tests/test_workflow.py","tests/markdown.test.mjs","tests/browser_fixture.py","tests/browser_checks.js",
    "tests/live_probe.py","tests/model_diagnostic.py","tests/verify_live_export.py"
]
def main():
    manifest={}
    contents={}
    forbidden=[re.compile(r"sk-[A-Za-z0-9_.-]{24,}"),
               re.compile(r"ws-[a-z0-9]+[.]cn-beijing[.]maas[.]aliyuncs[.]com"),
               re.compile(r"[A-Z]:[/\\]+Users[/\\]",re.I)]
    for name in FILES:
        path=ROOT/name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError("Unsafe source path: "+name)
        raw=path.read_bytes()
        text=raw.decode("utf-8-sig")
        if any(pattern.search(text) for pattern in forbidden):
            raise RuntimeError("Potential private value in "+name+"; package not created.")
        contents[name]=raw
        manifest[name]=hashlib.sha256(raw).hexdigest()
    target=ROOT/"release"
    target.mkdir(exist_ok=True)
    archive=target/("debate-workbench-source-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".zip")
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED) as z:
        for name,raw in contents.items():
            z.writestr("debate-workbench/"+name,raw)
        z.writestr("debate-workbench/SOURCE-MANIFEST.json",json.dumps(manifest,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(FILES)+1
        for name,digest in manifest.items():
            assert hashlib.sha256(z.read("debate-workbench/"+name)).hexdigest()==digest
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".sha256").write_text(checksum+"  "+archive.name+"\n",encoding="ascii")
    print(json.dumps({"archive":str(archive),"files":len(FILES)+1,"bytes":archive.stat().st_size,"sha256":checksum}))

if __name__=="__main__":
    main()
