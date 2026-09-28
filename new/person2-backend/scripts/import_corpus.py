import argparse,asyncio,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.db import make_database
from app.models import Base
from app.corpus import read_corpus
from app.repository import import_corpus

async def run(directory):
    corpus=read_corpus(directory)
    engine,sessions=make_database(get_settings())
    try:
        async with engine.begin() as db:await db.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:fp=await import_corpus(db,corpus)
        print(f'Activated snapshot {fp}: {len(corpus["procedures"])} procedures; {len(corpus["fragments"])} fragments')
    finally:await engine.dispose()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
    asyncio.run(run(args.directory))
