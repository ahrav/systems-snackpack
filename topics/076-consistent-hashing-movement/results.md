# Local committed-source results

Apple M1 Pro, Darwin 25.6.0, 10 available CPUs. rustc 1.93.1/LLVM 21.1.8,
default target features, release. Six paired process blocks, min/max dispersion.
Source b6c88c1fb7c57c4b47ace1a5a6c9a24dcc289b5e. Exact source/runner archive hashes verified.

|Nodes|Pattern|Modulo ns|HRW ns|Ring 1 ns|Ring 64 ns|HRW vs Ring 64 steady|HRW vs Ring 64 build/first pass|
|---:|---|---:|---:|---:|---:|---|---|
|8|small|1.79|14.00|3.86|8.76|ring64|hrw|
|8|uniform|1.67|13.61|3.66|8.42|ring64|ring64|
|8|hot|1.66|13.42|3.66|8.42|ring64|ring64|
|64|small|1.65|117.67|5.22|12.06|ring64|hrw|
|64|uniform|1.65|117.73|5.11|11.92|ring64|ring64|
|64|hot|1.61|115.41|5.11|11.69|ring64|ring64|
|256|small|1.77|475.98|7.23|22.38|ring64|hrw|
|256|uniform|1.64|488.14|7.24|24.24|ring64|ring64|
|256|hot|1.73|484.37|7.16|14.98|ring64|ring64|

Modulo won all 9 steady all-candidate cells, but fails strict add/remove locality.
Ring1 is faster than ring64 but ownership is less balanced in the finite movement case.
HRW/ring64 eligibility is declared for that comparison, not an assertion of a balance SLA.

|Nodes|Pattern|HRW ns range|Ring 64 ns range|HRW first-pass us range|Ring 64 first-pass us range|
|---:|---|---|---|---|---|
|8|small|13.88–14.26|8.69–9.10|2.42–2.58|13.04–13.58|
|8|uniform|13.39–13.85|8.24–8.72|436.42–462.83|283.38–397.54|
|8|hot|13.16–13.82|7.96–8.62|435.29–442.92|276.42–286.83|
|64|small|115.33–120.75|11.93–13.58|16.38–16.79|90.21–115.04|
|64|uniform|116.23–119.41|11.71–11.97|3740.88–3960.46|468.50–528.75|
|64|hot|114.87–116.46|11.64–12.11|3797.12–3904.67|464.50–479.71|
|256|small|471.19–481.26|20.55–23.81|62.88–73.79|332.08–379.25|
|256|uniform|471.64–499.69|23.65–24.37|15676.29–16576.67|1059.04–1219.83|
|256|hot|481.66–489.80|14.56–15.43|15381.58–16090.50|810.42–979.50|

## Movement accounting

```csv
kind,event,keys,moved,unrelated,max_over_mean,bytes_fraction,request_fraction,hops
mod,add,65536,58085,50752,1.019669,0.886844,0.443157,58085
mod,remove,65536,57235,49069,1.009583,0.999014,0.436672,57235
mod,replace,65536,40899,24522,1.006958,0.997074,0.312037,114531
hrw,add,65536,7173,0,1.037109,0.110766,0.054726,7173
hrw,remove,65536,8305,0,1.022400,0.993315,0.063363,8305
hrw,replace,65536,14558,0,1.033325,0.994046,0.111070,16408
ring1,add,65536,4489,0,2.190536,0.000274,0.034249,4489
ring1,remove,65536,15951,0,1.964584,0.996973,0.621694,15951
ring1,replace,65536,20440,0,2.245239,0.997247,0.655942,20440
ring64,add,65536,5905,0,1.287460,0.107992,0.045052,5905
ring64,remove,65536,7990,0,1.268280,0.993016,0.060959,7990
ring64,replace,65536,13031,0,1.313599,0.993627,0.099419,14579
```

The 65,536-key corpus is fixed. Bytes/request weights are deliberately skewed;
byte weights depend on old owner within each candidate and are not a common
cross-candidate physical dataset. HRW remove3 moves12.67%keys and99.33%bytes.
Replacement endpoint HRW 14,558 keys differs from 16,408 remove/add transfer events.

## Limits

Both declared Linux hosts rejected expired Midway authentication before identity
or transfer; exact-source replay remains pending. No Linux, network, migration
throughput, latency-tail, hardware-isolation, or ISA-wide inference. The scratch
campaign is retained separately; these figures come only from committed source.
