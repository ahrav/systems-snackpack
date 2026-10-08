| Host | Blocks | Used | Trace | Writes | WAF rr / greedy / sample4 | ns/write rr / greedy / sample4 | Time selection | WAF selection |
|---|---:|---:|---|---:|---|---|---|---|
| arm | 64 | 50% | uniform | 20000 | 1.275 / 1.245 / 1.353 | 15.46 / 19.71 / 17.29 | rr | greedy |
| arm | 64 | 50% | hot | 20000 | 1.763 / 1.670 / 1.694 | 17.24 / 22.47 / 17.66 | unresolved | greedy |
| arm | 64 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.011 | 11.00 / 13.05 / 12.05 | rr | equal counts: rr+greedy |
| arm | 64 | 90% | uniform | 20000 | 6.016 / 5.194 / 6.166 | 43.70 / 65.49 / 48.03 | rr | greedy |
| arm | 64 | 90% | hot | 20000 | 6.997 / 6.327 / 6.902 | 48.23 / 72.94 / 51.41 | rr | greedy |
| arm | 64 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.420 | 11.03 / 12.66 / 14.82 | rr | equal counts: rr+greedy |
| arm | 256 | 50% | uniform | 20000 | 1.263 / 1.228 / 1.336 | 17.43 / 32.79 / 19.16 | unresolved | greedy |
| arm | 256 | 50% | hot | 20000 | 1.724 / 1.572 / 1.601 | 17.88 / 37.10 / 18.71 | unresolved | greedy |
| arm | 256 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.002 | 10.93 / 20.12 / 12.43 | rr | equal counts: rr+greedy |
| arm | 256 | 90% | uniform | 20000 | 5.338 / 4.676 / 5.513 | 43.41 / 112.63 / 48.67 | rr | greedy |
| arm | 256 | 90% | hot | 20000 | 6.346 / 5.897 / 6.273 | 46.90 / 132.89 / 51.34 | rr | greedy |
| arm | 256 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.069 | 10.99 / 17.46 / 13.15 | rr | equal counts: rr+greedy |
| arm | 64 | 90% | uniform | 32 | 1.000 / 1.000 / 1.000 | 12.16 / 12.45 / 12.42 | unresolved | equal counts: rr+greedy+sample4 |
| x86 | 64 | 50% | uniform | 20000 | 1.275 / 1.245 / 1.353 | 13.39 / 17.57 / 15.11 | rr | greedy |
| x86 | 64 | 50% | hot | 20000 | 1.763 / 1.670 / 1.694 | 15.11 / 20.24 / 15.46 | unresolved | greedy |
| x86 | 64 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.011 | 8.42 / 10.63 / 10.28 | unresolved | equal counts: rr+greedy |
| x86 | 64 | 90% | uniform | 20000 | 6.016 / 5.194 / 6.166 | 39.61 / 62.91 / 44.82 | unresolved | greedy |
| x86 | 64 | 90% | hot | 20000 | 6.997 / 6.327 / 6.902 | 42.47 / 66.91 / 46.16 | unresolved | greedy |
| x86 | 64 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.420 | 8.39 / 9.74 / 12.92 | rr | equal counts: rr+greedy |
| x86 | 256 | 50% | uniform | 20000 | 1.263 / 1.228 / 1.336 | 14.36 / 28.75 / 16.94 | unresolved | greedy |
| x86 | 256 | 50% | hot | 20000 | 1.724 / 1.572 / 1.601 | 15.56 / 32.49 / 16.34 | unresolved | greedy |
| x86 | 256 | 50% | cyclic | 20000 | 1.000 / 1.000 / 1.002 | 8.82 / 17.07 / 10.62 | unresolved | equal counts: rr+greedy |
| x86 | 256 | 90% | uniform | 20000 | 5.338 / 4.676 / 5.513 | 39.48 / 106.82 / 46.01 | rr | greedy |
| x86 | 256 | 90% | hot | 20000 | 6.346 / 5.897 / 6.273 | 41.78 / 122.36 / 47.76 | rr | greedy |
| x86 | 256 | 90% | cyclic | 20000 | 1.000 / 1.000 / 1.069 | 9.25 / 14.18 / 11.12 | unresolved | equal counts: rr+greedy |
| x86 | 64 | 90% | uniform | 32 | 1.000 / 1.000 / 1.000 | 12.94 / 13.97 / 12.98 | unresolved | equal counts: rr+greedy+sample4 |
