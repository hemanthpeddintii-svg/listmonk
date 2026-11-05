#!/usr/bin/env python3
"""Tiny cron for the worker container: no downloads, no system cron, IST aware, one run of a job at a time.

    python scheduler.py                 # run forever using ./crontab
    python scheduler.py --list          # show each job's next 3 run times and exit
    python scheduler.py --run digest    # run the job whose command contains "digest" right now and exit
Env: SCHEDULER_TZ (default Asia/Kolkata), SCHEDULER_FILE (default ./crontab), JOB_TIMEOUT seconds (default 7200).
Dump the container env for the jobs first (done by the image entrypoint): 
"""
import os, subprocess, sys, threading, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo(os.environ.get("SCHEDULER_TZ", "Asia/Kolkata"))
FILE = os.environ.get("SCHEDULER_FILE", os.path.join(HERE, "crontab"))
TIMEOUT = int(os.environ.get("JOB_TIMEOUT", "7200"))
RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def field(spec, lo, hi, dow=False):
    out = set()
    for part in spec.split(","):
        rng, _, step = part.partition("/")
        step = int(step) if step else 1
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            a, b = map(int, rng.split("-"))
        else:
            a = int(rng); b = hi if step > 1 else a
        out |= set(range(a, b + 1, step))
    return {v % 7 for v in out} if dow else out


def parse(path):
    jobs = []
    for raw in open(path):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        p = line.split(None, 5)
        if len(p) < 6:
            raise SystemExit(f"bad crontab line: {raw!r}")
        sets = [field(p[i], *RANGES[i], dow=(i == 4)) for i in range(5)]
        jobs.append(dict(sets=sets, cmd=p[5].strip(), dom_star=p[2] == "*", dow_star=p[4] == "*", lock=threading.Lock()))
    return jobs


def due(job, t):
    m, h, dom, mon, dow = job["sets"]
    if t.minute not in m or t.hour not in h or t.month not in mon:
        return False
    d_ok, w_ok = t.day in dom, ((t.weekday() + 1) % 7) in dow          # cron: Sunday = 0
    return (d_ok and w_ok) if (job["dom_star"] or job["dow_star"]) else (d_ok or w_ok)


def run(job):
    if not job["lock"].acquire(blocking=False):
        print(f"[{datetime.now(TZ):%F %T}] skip (still running): {job['cmd']}", flush=True)
        return
    try:
        print(f"[{datetime.now(TZ):%F %T}] start: {job['cmd']}", flush=True)
        try:
            r = subprocess.run(job["cmd"], shell=True, cwd=HERE, timeout=TIMEOUT)
            print(f"[{datetime.now(TZ):%F %T}] done (exit {r.returncode}): {job['cmd']}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"[{datetime.now(TZ):%F %T}] TIMEOUT after {TIMEOUT}s: {job['cmd']}", flush=True)
    finally:
        job["lock"].release()


def next_runs(job, n=3):
    t = datetime.now(TZ).replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    while len(out) < n and len(out) < 50 and t < datetime.now(TZ) + timedelta(days=400):
        if due(job, t):
            out.append(t)
        t += timedelta(minutes=1)
    return out


def main():
    jobs = parse(FILE)
    if "--list" in sys.argv:
        for j in jobs:
            print(j["cmd"].ljust(32), " | ".join(f"{t:%a %F %H:%M}" for t in next_runs(j)), TZ.key)
        return
    if "--run" in sys.argv:
        key = sys.argv[sys.argv.index("--run") + 1]
        hit = [j for j in jobs if key in j["cmd"]]
        if not hit:
            raise SystemExit(f"no job matching {key!r}")
        run(hit[0]); return
    print(f"scheduler: {len(jobs)} jobs from {FILE}, timezone {TZ.key}", flush=True)
    last = None
    while True:
        now = datetime.now(TZ).replace(second=0, microsecond=0)
        if now != last:
            last = now
            for j in jobs:
                if due(j, now):
                    threading.Thread(target=run, args=(j,), daemon=True).start()
        time.sleep(max(1, 60 - datetime.now(TZ).second))


if __name__ == "__main__":
    main()
