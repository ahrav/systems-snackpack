| Host | Blocks | Used | Trace | Writes | WAF rr / greedy / sample4 | ns/write rr / greedy / sample4 | Time selection | WAF selection |
|---|---:|---:|---|---:|---|---|---|---|
| arm | 64 | 50% | uniform | 20000 | 1.275 / 1.245 / 1.353 | 15.46 / 19.68 / 17.22 | rr | greedy |
| arm | 64 | 50% | hot | 20000 | 1.763 / 1.670 / 1.694 | 17.17 / 22.61 / 17.65 | unresolved | greedy |
| arm | 64 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.011 | 10.98 / 12.92 / 12.16 | rr | equal counts: rr+greedy |
| arm | 64 | 90% | uniform | 20000 | 6.016 / 5.194 / 6.166 | 43.86 / 65.64 / 48.03 | rr | greedy |
| arm | 64 | 90% | hot | 20000 | 6.997 / 6.327 / 6.902 | 48.16 / 72.34 / 51.46 | rr | greedy |
| arm | 64 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.420 | 11.01 / 12.51 / 14.79 | rr | equal counts: rr+greedy |
| arm | 256 | 50% | uniform | 20000 | 1.263 / 1.228 / 1.336 | 17.45 / 32.98 / 19.31 | rr | greedy |
| arm | 256 | 50% | hot | 20000 | 1.724 / 1.572 / 1.601 | 17.92 / 36.65 / 18.64 | unresolved | greedy |
| arm | 256 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.002 | 10.93 / 20.06 / 12.39 | unresolved | equal counts: rr+greedy |
| arm | 256 | 90% | uniform | 20000 | 5.338 / 4.676 / 5.513 | 43.12 / 112.81 / 48.57 | rr | greedy |
| arm | 256 | 90% | hot | 20000 | 6.346 / 5.897 / 6.273 | 47.01 / 132.37 / 51.46 | rr | greedy |
| arm | 256 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.069 | 11.06 / 17.03 / 12.85 | rr | equal counts: rr+greedy |
| arm | 64 | 90% | uniform | 32 | 1.000 / 1.000 / 1.000 | 13.45 / 13.64 / 13.44 | unresolved | equal counts: rr+greedy+sample4 |
| x86 | 64 | 50% | uniform | 20000 | 1.275 / 1.245 / 1.353 | 13.33 / 17.78 / 15.35 | unresolved | greedy |
| x86 | 64 | 50% | hot | 20000 | 1.763 / 1.670 / 1.694 | 15.03 / 20.84 / 16.68 | unresolved | greedy |
| x86 | 64 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.011 | 8.90 / 10.48 / 9.75 | unresolved | equal counts: rr+greedy |
| x86 | 64 | 90% | uniform | 20000 | 6.016 / 5.194 / 6.166 | 39.25 / 61.93 / 44.16 | unresolved | greedy |
| x86 | 64 | 90% | hot | 20000 | 6.997 / 6.327 / 6.902 | 41.94 / 69.06 / 47.46 | unresolved | greedy |
| x86 | 64 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.420 | 8.30 / 9.78 / 13.51 | unresolved | equal counts: rr+greedy |
| x86 | 256 | 50% | uniform | 20000 | 1.263 / 1.228 / 1.336 | 14.34 / 28.26 / 16.42 | unresolved | greedy |
| x86 | 256 | 50% | hot | 20000 | 1.724 / 1.572 / 1.601 | 16.07 / 32.58 / 16.31 | unresolved | greedy |
| x86 | 256 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.002 | 9.45 / 16.59 / 10.19 | unresolved | equal counts: rr+greedy |
| x86 | 256 | 90% | uniform | 20000 | 5.338 / 4.676 / 5.513 | 38.93 / 106.10 / 45.23 | rr | greedy |
| x86 | 256 | 90% | hot | 20000 | 6.346 / 5.897 / 6.273 | 41.11 / 121.60 / 46.76 | rr | greedy |
| x86 | 256 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.069 | 9.28 / 14.39 / 11.11 | rr | equal counts: rr+greedy |
| x86 | 64 | 90% | uniform | 32 | 1.000 / 1.000 / 1.000 | 12.88 / 12.72 / 12.56 | unresolved | equal counts: rr+greedy+sample4 |
