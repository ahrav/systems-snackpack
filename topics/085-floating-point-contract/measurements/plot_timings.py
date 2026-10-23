from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]
s=json.loads((root/'measurements/raw/summary.json').read_text())
fig, axes=plt.subplots(1,2,figsize=(11,4.8),dpi=180,sharey=True)
colors={'ordered':'#b65736','lanes4':'#187e83','compensated':'#8467ad'}
for ax,(host,title) in zip(axes,(('arm','Arm host'),('xxl','x86-64 host'))):
 cells=s[host]
 for i,(method,color) in enumerate(colors.items()):
  vals=[cells[f'positive/{n}']['ns_per_item'][method] for n in [256,65536,1048576]]
  x=[j+(i-1)*.23 for j in range(3)]; y=[v['median'] for v in vals]
  ax.bar(x,y,width=.21,color=color,label=method)
  ax.errorbar(x,y,yerr=[[v['median']-v['min'] for v in vals],[v['max']-v['median'] for v in vals]],fmt='none',ecolor='#222',capsize=3,lw=1)
 ax.set_title(title,weight='bold')
 ax.set_xticks(range(3),['256','65,536','1,048,576'])
 ax.set_xlabel('Elements per array')
 ax.grid(axis='y',alpha=.2)
 ax.set_axisbelow(True)
axes[0].set_ylabel('Nanoseconds per element (lower is faster)')
axes[1].legend(frameon=False,fontsize=9)
fig.suptitle('Positive dyadic inputs: every candidate returns the exact sum',weight='bold',fontsize=14)
fig.text(.5,.015,'Bars: median of 12 processes. Whiskers: observed min/max. Warm repeated kernels; one pinned CPU.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.04,1,.94))
fig.savefig(root/'measurements/timings.png')
