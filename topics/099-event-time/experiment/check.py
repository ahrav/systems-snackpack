"""Compare Rust state after every command to an event-history oracle.

The oracle keeps accepted raw events and recomputes grouped sums using SQLite.
It derives first emissions from previous/current frontiers, independently of
Rust's retained aggregate and sink-membership implementation.
"""
import hashlib
import itertools
import json
import random
import sqlite3
import subprocess
import sys

class Oracle:
    def __init__(self, lateness):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("create table events(t integer, amount integer)")
        self.lateness = lateness
        self.f = -1
        self.p = [-1, -1]
        self.active = [True, True]
        self.sink = {}
        self.dropped = self.writes = 0
    def sums(self):
        return dict(self.db.execute("select (t / 10) * 10, sum(amount) from events group by (t / 10) * 10"))
    def step(self, line):
        a = line.split()
        op, i = a[0], int(a[1])
        old = self.f
        if op == "E":
            t, amount = map(int, a[2:])
            self.active[i] = True
            end = (t // 10 + 1) * 10
            if end + self.lateness <= self.f:
                self.dropped += 1
            else:
                self.db.execute("insert into events values (?,?)", (t, amount))
                if end <= self.f:
                    self.sink[end-10] = self.sums()[end-10]
                    self.writes += 1
        else:
            if op == "W":
                self.p[i] = max(self.p[i], int(a[2]))
                self.active[i] = True
            else:
                self.active[i] = op == "A"
            values = [v for v, active in zip(self.p, self.active) if active]
            if values:
                self.f = max(self.f, min(values))
            for start, total in self.sums().items():
                if old < start + 10 <= self.f:
                    self.sink[start] = total
                    self.writes += 1
        live = {s:v for s,v in self.sums().items() if s+10+self.lateness>self.f}
        def pairs(m):
            return ",".join(f"{k}:{v}" for k,v in sorted(m.items())) or "-"
        return f"{self.f} {self.dropped} {self.writes} {pairs(live)} {pairs(self.sink)}"

def main():
    scripts = []
    # Every permutation challenges watermark/event ordering and idle resumption.
    core = ["E 0 0 5", "E 1 9 7", "W 0 10", "W 1 15", "I 1", "A 1"]
    for lateness in [0, 1, 5, 20]:
        for order in itertools.permutations(core):
            scripts.append((lateness, list(order) + ["E 0 10 3", "W 0 30", "W 1 30", "E 1 9 4"]))
    r = random.Random(9905)
    for _ in range(300):
        script=[]
        for _ in range(100):
            op=r.choice(["E","E","E","W","I","A"]); i=r.randrange(2)
            if op=="E": script.append(f"E {i} {r.randrange(100)} {r.randrange(-9,20)}")
            elif op=="W": script.append(f"W {i} {r.randrange(125)}")
            else: script.append(f"{op} {i}")
        scripts.append((r.choice([0,1,5,20]),script))
    lines=[]; expected=[]
    for lateness, commands in scripts:
        o=Oracle(lateness)
        lines.append(f"R {lateness}"); expected.append("-1 0 0 - -")
        for command in commands:
            lines.append(command); expected.append(o.step(command))
        o.db.close()
    payload="\n".join(lines)+"\n"
    actual=subprocess.run([sys.argv[1]], input=payload, text=True, capture_output=True, check=True).stdout
    rows=actual.splitlines()
    assert len(rows)==len(expected), (len(rows),len(expected))
    for index,(got,want) in enumerate(zip(rows,expected)):
        assert got==want, (index,lines[max(0,index-12):index+1],got,want)
    print(json.dumps({"schedules":len(scripts),"state_comparisons":len(rows),"seed":9905,
        "input_sha256":hashlib.sha256(payload.encode()).hexdigest(),
        "output_sha256":hashlib.sha256(actual.encode()).hexdigest(),"status":"pass"},sort_keys=True))
if __name__=="__main__": main()
