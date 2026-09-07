"""Optional real search probe; model credentials must be entered in the web settings."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from search import Search

async def main():
    runs, sources = await Search(local=True).run(["UNESCO generative artificial intelligence education guidance"])
    print({"queries":len(runs),"sources":len(sources),"bodies":sum(bool(s["text"]) for s in sources)})
    print("Model connection: use the web settings test button with your own API.")

if __name__ == "__main__":
    asyncio.run(main())
