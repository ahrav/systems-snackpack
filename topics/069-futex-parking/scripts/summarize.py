import json, pathlib, random, statistics, sys

source, output = map(pathlib.Path, sys.argv[1:])
rows = [json.loads(l) for l in source.read_text().splitlines()]
policies = ['spin','one','all','hybrid']
rng = random.Random(69)
def q(a,p):
    s=sorted(a); x=(len(s)-1)*p; i=int(x); return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(x-i)
result=[]
for cell in dict.fromkeys(r['cell'] for r in rows):
    data={p:sorted([r for r in rows if r['cell']==cell and r['policy']==p],key=lambda r:r['block']) for p in policies}
    assert all(len(v)==8 for v in data.values())
    assert all(len({r['checksum'] for r in rows if r['cell']==cell})==1 for p in policies)
    times={p:[r['wall_ns']/r['operations'] for r in data[p]] for p in policies}
    meds={p:statistics.median(times[p]) for p in policies}; best=min(meds,key=meds.get)
    pairs={}
    for p in policies:
        if p==best:continue
        ratio=[a/b for a,b in zip(times[best],times[p])]
        boots=[statistics.median(rng.choices(ratio,k=8)) for _ in range(10000)]
        pairs[p]={'median_paired_ratio':statistics.median(ratio),'interval95':[q(boots,.025),q(boots,.975)]}
    resolved=all(meds[best]/meds[p]<=.98 and pairs[p]['interval95'][1]<1 for p in pairs)
    summary={p:{'wall_ns_op_median':meds[p],'wall_ns_op_iqr':[q(times[p],.25),q(times[p],.75)],
        'cpu_ns_op_median':statistics.median(r['cpu_ns']/r['operations'] for r in data[p]),
        **{key+'_per_op':statistics.median(r[key]/r['operations'] for r in data[p]) for key in ['waits','again','wakes','woken']}} for p in policies}
    result.append({'cell':cell,'lowest_median':best,'selection':best if resolved else 'unresolved','candidates':summary,'paired_vs_lowest':pairs})
output.write_text(json.dumps(result,indent=2)+'\n')
for r in result:
 print(r['cell'],r['selection'],'lowest='+r['lowest_median'], ' '.join(p+'='+str(round(r['candidates'][p]['wall_ns_op_median'],2)) for p in policies))
