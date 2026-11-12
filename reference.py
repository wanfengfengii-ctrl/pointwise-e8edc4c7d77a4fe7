"""Immutable full-rebuild specification. Integer weights count replicated evidence."""
from collections import defaultdict

class Conflict(ValueError):
    pass

def accept(records, batch):
    if not isinstance(batch, list):
        raise ValueError("BATCH")
    seen = set()
    for e in batch:
        if not isinstance(e, dict) or set(e) != {"id", "rev", "lab", "device", "units", "start", "end"}:
            raise ValueError("FIELDS")
        if any(not isinstance(e[k], str) or not e[k] for k in ("id", "lab", "device")):
            raise ValueError("NAME")
        if type(e["rev"]) is not int or e["rev"] < 1:
            raise ValueError("REV")
        if type(e["units"]) is not int or e["units"] < 0:
            raise ValueError("UNITS")
        if (type(e["start"]) is not int or type(e["end"]) is not int
                or e["start"] >= e["end"]):
            raise ValueError("INTERVAL")
        if e["id"] in seen:
            raise ValueError("DUPLICATE_ID")
        seen.add(e["id"])
        old = records.get(e["id"])
        if old is None or e["rev"] > old["rev"]:
            records[e["id"]] = dict(e)
        elif e["rev"] == old["rev"] and e != old:
            raise Conflict("REVISION_CONFLICT")

def instantaneous(records):
    rows = defaultdict(dict)
    for e in records.values():
        if e["units"]:
            row = rows[e["lab"]]
            row[e["device"]] = row.get(e["device"], 0) + e["units"]
    labs = sorted(rows)
    counts = {a: 0 for a in labs}
    total = 0
    for i, a in enumerate(labs):
        for c in labs[i + 1:]:
            left, right = rows[a], rows[c]
            if len(left) > len(right):
                left, right = right, left
            s = q = 0
            for device, x in left.items():
                z = x * right.get(device, 0)
                s += z
                q += z * z
            cycles = (s * s - q) // 2
            total += cycles
            counts[a] += cycles
            counts[c] += cycles
    return {"total": total, "labs": counts}

def materialize(records):
    active = [e for e in records.values() if e["units"]]
    points = sorted({e[k] for e in active for k in ("start", "end")})
    result = {"total": 0, "labs": {e["lab"]: 0 for e in active}}
    for lo, hi in zip(points, points[1:]):
        live = {e["id"]: e for e in active if e["start"] <= lo < e["end"]}
        part = instantaneous(live)
        result["total"] += part["total"] * (hi - lo)
        for lab, value in part["labs"].items():
            result["labs"][lab] += value * (hi - lo)
    result["labs"] = dict(sorted(result["labs"].items()))
    return result

class Engine:
    def __init__(self, records=()):
        self.records = {}
        accept(self.records, list(records))
        self.result = materialize(self.records)

    def read(self):
        return {"total": self.result["total"], "labs": dict(self.result["labs"])}

    def apply(self, batch):
        staged = {k: dict(v) for k, v in self.records.items()}
        accept(staged, batch)
        result = materialize(staged)
        old = self.result
        delta = {k: result["labs"].get(k, 0) - old["labs"].get(k, 0)
                 for k in sorted(set(old["labs"]) | set(result["labs"]))}
        answer = {"total": result["total"] - old["total"],
                  "labs": {k: v for k, v in delta.items() if v}}
        self.records, self.result = staged, result
        return answer
