import gc
import itertools
import json
import random
import statistics
import sys
import time
import tracemalloc
from engine import Engine
from reference import Engine as Reference
from samples import INITIAL, CORRECTION, INITIAL_RESULT, FINAL_RESULT, DELTA

def record(k, rev, a, b, w, start=0, end=10):
    return dict(id=k, rev=rev, lab=a, device=b, units=w, start=start, end=end)

def brute(records):
    active = [e for e in records.values() if e["units"]]
    labs = sorted({e["lab"] for e in active})
    devices = sorted({e["device"] for e in active})
    out = dict.fromkeys(labs, 0)
    total = 0
    # Independent witness enumeration, not the reference's squared-dot-product identity.
    for a,c in itertools.combinations(labs,2):
        for b,d in itertools.combinations(devices,2):
            groups = [[e for e in active if (e["lab"],e["device"]) == p]
                      for p in ((a,b),(a,d),(c,b),(c,d))]
            for witness in itertools.product(*groups):
                lo = max(e["start"] for e in witness)
                hi = min(e["end"] for e in witness)
                value = max(0,hi-lo)
                for e in witness:
                    value *= e["units"]
                total += value
                out[a] += value
                out[c] += value
    return dict(total=total,labs=out)

def normal():
    e = Engine(INITIAL)
    assert e.read() == INITIAL_RESULT
    assert e.apply(CORRECTION) == DELTA
    assert e.read() == FINAL_RESULT
    assert e.apply(CORRECTION) == dict(total=0, labs={})
    saved = e.read()
    try:
        e.apply([record("fresh",1,"L4","D4",9),
                 record("a",1,"L1","D1",999)])
    except ValueError:
        pass
    else:
        raise AssertionError("conflict accepted")
    assert e.read() == saved
    assert e.apply([record("fresh",1,"L4","D4",1)]) == dict(total=0,labs={})
    # Validation applies even to stale records; partial acceptance must never escape.
    for bad in (
        [record("new",1,"X","Y",1),record("a",0,"L1","D1",1)],
        [record("new",1,"X","Y",1),record("a",2,"L1","D1",True)],
        [record("new",1,"X","Y",1),record("a",2,"L1","D1",1,5,5)],
        [record("a",2,"L1","D1",1),record("a",3,"L1","D1",1)],
    ):
        before = e.read()
        try:
            e.apply(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid batch accepted")
        assert e.read() == before
    assert e.apply([record("new",1,"X","Y",2)]) == dict(total=0,labs={})
    assert e.read()["labs"]["X"] == 0
    assert e.apply([]) == dict(total=0,labs={})
    r = Reference(INITIAL)
    e = Engine(INITIAL)
    rng = random.Random(72031)
    for _ in range(120):
        batch = []
        for k in rng.sample(range(18), rng.randrange(1,7)):
            key = str(k)
            old = r.records.get(key)
            rev = (old["rev"] + 1) if old else 1
            batch.append(record(key,rev,"L"+str(rng.randrange(5)),
                                "D"+str(rng.randrange(5)),rng.choice([0,1,2,10**20]),rng.randrange(-5,5),rng.randrange(5,15)))
        assert e.apply(batch) == r.apply(batch)
        assert e.read() == brute(r.records)
    copy = e.read()
    copy["labs"].clear()
    assert e.read() == r.read()
    print("NORMAL_REGRESSION_OK")

def workload(kind, n, seed):
    rng = random.Random(seed)
    rows = []
    def add(a,b):
        rows.append(record(str(len(rows)),1,a,b,1+rng.randrange(3),0,10**15))
    if kind == "dense":
        for a in range(n):
            for b in range(n):
                add("L"+str(a),"D"+str(b))
        hot = list(range(len(rows)))
    else:
        # One connected component: two opposite stars joined by a dense 2x2 core.
        for a in range(n):
            for b in range(2):
                add("L"+str(a),"D"+str(b))
        for a in range(2):
            for b in range(2,n):
                add("L"+str(a),"D"+str(b))
        hot = [i for i,e in enumerate(rows)
               if e["lab"] in ("L0","L1") and e["device"] in ("D0","D1")]
    state = {e["id"]: dict(e) for e in rows}
    batches = []
    hub_l,hub_d = ["L0","L1"],["D0","D1"]
    for step in range(5):
        if kind == "cross" and step in (2,4):
            # Move both high-degree sides together, with old/new keys overlapping.
            new_l = rng.sample(["L"+str(a) for a in range(n) if "L"+str(a) not in hub_l],2)
            new_d = rng.sample(["D"+str(b) for b in range(n) if "D"+str(b) not in hub_d],2)
            lmap = dict(zip(hub_l+new_l,new_l+hub_l))
            dmap = dict(zip(hub_d+new_d,new_d+hub_d))
            hub_l,hub_d = new_l,new_d
            batch = []
            for key,old in state.items():
                a,b = lmap.get(old["lab"],old["lab"]),dmap.get(old["device"],old["device"])
                if (a,b) != (old["lab"],old["device"]):
                    e = dict(old,lab=a,device=b,rev=old["rev"]+1)
                    if int(key) % 11 == 0:
                        e["units"] = (old["units"]+1) % 6
                        e["start"] = (old["start"]+10**12) % (5*10**12)
                    state[key] = e
                    batch.append(e)
            batches.append(batch)
            continue
        ids = set(rng.sample(hot,min(2,len(hot))))
        ids.update(rng.sample(range(len(rows)),min(4,len(rows))))
        batch = []
        for i in sorted(ids):
            e = dict(state[str(i)])
            e["rev"] += 1
            # Correlated endpoint moves, cancellations, deletions and restoration.
            if step % 3 == 1:
                e["lab"],e["device"] = "L"+str(rng.randrange(n)),"D"+str(rng.randrange(n))
            e["units"] = rng.choice([0,1,2,5])
            e["start"] = rng.randrange(4)*10**12
            e["end"] = 10**15-rng.randrange(4)*10**12
            state[e["id"]] = e
            batch.append(e)
        batches.append(batch)
    return rows,batches

def exercise(cls, rows, batches):
    e = cls(rows)
    snapshots = []
    elapsed = []
    for batch in batches:
        t = time.perf_counter()
        delta = e.apply(batch)
        elapsed.append(time.perf_counter()-t)
        snapshots.append((delta,e.read()))
    return e, snapshots, elapsed

def measure(kind,n,seed):
    rows,batches = workload(kind,n,seed)
    ref, expected, rt = exercise(Reference,rows,batches)
    del ref
    # Warmup is a fresh engine; timed repetitions are also independent fresh engines.
    warm, actual, _ = exercise(Engine,rows,batches)
    assert actual == expected
    del warm
    times = [[] for _ in batches]
    for _ in range(3):
        e, actual, ts = exercise(Engine,rows,batches)
        assert actual == expected
        for bucket,value in zip(times,ts):
            bucket.append(value)
        del e
    candidate = [statistics.median(x) for x in times]
    # Separate instrumented pass: construction counts toward resident Python allocation.
    gc.collect()
    tracemalloc.start()
    e = Engine(rows)
    for batch in batches:
        e.apply(batch)
    current,peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert e.read() == expected[-1][1]
    # Repeat reference for the same per-position median methodology.
    ref_times = [[v] for v in rt]
    for _ in range(2):
        ref,actual,ts = exercise(Reference,rows,batches)
        assert actual == expected
        for bucket,value in zip(ref_times,ts):
            bucket.append(value)
        del ref
    baseline = [statistics.median(x) for x in ref_times]
    return dict(kind=kind,n=n,reference_seconds=baseline,candidate_seconds=candidate,
                worst_ratio=max(a/max(b,1e-12) for a,b in zip(candidate,baseline)),
                batch_median=statistics.median(candidate),peak_bytes=peak,
                final_total=expected[-1][1]["total"])

def bench(enforce=False):
    reports = []
    for kind,sizes in (("dense",(24,96)),("cross",(240,960))):
        group = [measure(kind,n,8439+n) for n in sizes]
        for item in group:
            print(json.dumps(item,sort_keys=True),flush=True)
        growth = group[1]["batch_median"]/max(group[0]["batch_median"],1e-12)
        print(json.dumps(dict(kind=kind,growth=growth)),flush=True)
        reports.extend(group)
        if enforce:
            assert all(x["worst_ratio"] <= 0.125 for x in group), "SPEED_GATE"
            assert growth <= 6.0, "SCALING_GATE"
    if enforce:
        assert all(x["peak_bytes"] <= 48*1024*1024 for x in reports), "MEMORY_GATE"
    print("TARGET_BENCH_OK" if enforce else "BASELINE_BENCH_OK")

def demo():
    e = Engine(INITIAL)
    print(json.dumps(dict(input=INITIAL,result=e.read()),sort_keys=True))
    delta = e.apply(CORRECTION)
    print(json.dumps(dict(input=CORRECTION,delta=delta,result=e.read()),sort_keys=True))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv)>1 else "normal"
    if mode in ("normal","verify","target"):
        normal()
    if mode in ("bench","verify","target"):
        bench(mode == "target")
    if mode == "demo":
        demo()
    if mode not in ("normal","verify","target","bench","demo"):
        raise SystemExit("unknown mode")
