"""Validate an explicitly supplied saved JSON response without echoing its contents."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import parse_reply
from config import AppError

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("response_file",type=Path)
    args=parser.parse_args()
    try:
        parse_reply(args.response_file.read_text(encoding="utf-8"))
        print("REPLY_VALID")
    except AppError:
        print("REPLY_INVALID")
        raise SystemExit(1)
