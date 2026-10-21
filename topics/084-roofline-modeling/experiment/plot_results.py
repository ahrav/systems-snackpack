import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
s=json.loads(Path('measurements/raw/summary.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
colors=['#bd5034','#aa7a14','#188069']
for ax,(host,cells) in zip(axes,s.items()):
 for i,(mode,c) in enumerate(zip(('split','blocked','fused'),colors)):
  v=[x['modes'][mode]['median'] for x in cells]
  lo=[x['modes'][mode]['minimum'] for x in cells]; hi=[x['modes'][mode]['maximum'] for x in cells]
  x=np.arange(3)+(i-1)*.24
  ax.plot(x,v,'o',label=mode,color=c,markersize=6)
  ax.errorbar(x,v,yerr=[np.array(v)-lo,np.array(hi)-v],fmt='none',ecolor='#222222',capsize=3,lw=1)
 ax.set_xticks(range(3),['1,024','262,144','16,777,216'])
 ax.set_title('Arm Linux' if host=='arm' else 'x86-64 Linux (xxl)')
 ax.set(xlabel='Elements per pass',ylabel='ns/element (lower is better)',yscale='log')
 ax.grid(axis='y',alpha=.2); ax.legend(fontsize=9)
fig.suptitle('Same transform, different memory schedules\nMedian and full range; six processes per point; one pinned CPU',fontsize=13)
fig.savefig('measurements/schedules.png',dpi=170)
