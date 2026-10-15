"""Startup index creation: each spec on its own, so one conflict never stops the others; option mismatches are reported, never repaired."""
from pymongo.errors import OperationFailure

CONFLICT_CODES = (85, 86)  # IndexOptionsConflict, IndexKeySpecsConflict


def _key(keys):
    return [(keys, 1)] if isinstance(keys, str) else [tuple(k) for k in keys]


async def ensure(coll, keys, **opts):
    """None when created/verified; a mismatch description (str) when an index on the same keys exists with other options. Other errors raise, tagged with the collection."""
    try:
        await coll.create_index(keys, **opts)
        return None
    except OperationFailure as e:
        if e.code not in CONFLICT_CODES:
            raise RuntimeError(f"{coll.name} {_key(keys)}: {e}") from e
        want = _key(keys)
        info = await coll.index_information()
        have = next(({"name": n, **{k: v for k, v in spec.items() if k not in ("v", "ns", "key")}}
                     for n, spec in info.items() if [tuple(k) for k in spec["key"]] == want), None)
        name = (have or {}).pop("name", None) or "?"
        return f"{coll.name}.{name} keys={want} requested={opts or {}} existing={have} (existing index kept, nothing changed)"
    except Exception as e:
        raise RuntimeError(f"{coll.name} {_key(keys)}: {e}") from e


def summarize(results):
    mismatches = [r for r in results if isinstance(r, str)]
    failed = [r for r in results if isinstance(r, BaseException)]
    return len(results) - len(mismatches) - len(failed), mismatches, failed
