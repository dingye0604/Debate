"""Inspect an explicitly downloaded ZIP without bypassing visitor authentication."""
import argparse
import json
import zipfile
from pathlib import Path

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("archive",type=Path)
    args=parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        assert len(archive.namelist())==7
        assert "00-备赛总档案.md" in archive.namelist()
        sources=json.loads(archive.read("来源记录.json"))
        assert isinstance(sources,list)
        for name in archive.namelist():
            archive.read(name).decode("utf-8-sig")
        print(json.dumps({"files":7,"sources":len(sources),"utf8_valid":True}))
