"""Snapshot / restore the five cc_* collections around manual UI runs so the founder's data stays intact.
Usage: cd /app/backend && set -a && . ./.env && set +a && python tests/cc_snapshot.py save|restore [/tmp/cc_snapshot.bson]"""
import asyncio
import os
import sys

import bson
from motor.motor_asyncio import AsyncIOMotorClient

COLLS = ["cc_blueprint", "cc_priorities", "cc_roadmap", "cc_ideas", "cc_notes"]


async def main(cmd: str, path: str):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if cmd == "save":
        snap = {c: await db[c].find({}).to_list(5000) for c in COLLS}
        open(path, "wb").write(bson.encode(snap))
        print({c: len(v) for c, v in snap.items()})
    elif cmd == "restore":
        snap = bson.decode(open(path, "rb").read())
        for c in COLLS:
            await db[c].delete_many({})
            if snap[c]:
                await db[c].insert_many(snap[c])
        print("restored", {c: len(v) for c, v in snap.items()})
    else:
        raise SystemExit("save|restore")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/tmp/cc_snapshot.bson"))
