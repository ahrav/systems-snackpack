import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
out=Path('measurements')
x=np.geomspace(.025,32,400)
fig,ax=plt.subplots(figsize=(9,5.1),layout='constrained')
ax.loglog(x,np.minimum(200,50*x),lw=3,color='#2457a6',label='Illustrative roof: min(200 GFLOP/s, 50 GB/s × I)')
ax.axvline(4,color='#777777',ls='--',lw=1)
ax.annotate('Ridge = 4 FLOP/byte',xy=(4,200),xytext=(1.1,310),arrowprops={'arrowstyle':'->'})
for name,i,c in [('Split, cold temporal stores',3/48,'#bd5034'),('Fused, cold temporal stores',3/24,'#188069')]:
    ax.scatter([i],[50*i],s=70,color=c,zorder=4)
    ax.annotate(name+'\nI = '+f'{i:.4f} FLOP/byte',xy=(i,50*i),xytext=(i*1.3,50*i*.60),fontsize=10,arrowprops={'arrowstyle':'-'})
ax.set(xlabel='Operational intensity at the DRAM boundary (FLOP/byte)',ylabel='Model ceiling (GFLOP/s)',ylim=(1,500),xlim=(.025,32))
ax.set_title('Roofline turns traffic reduction into a testable hypothesis\nIllustrative inputs only; these are not host measurements',loc='left',fontsize=13)
ax.grid(which='both',alpha=.18)
ax.legend(loc='lower right',fontsize=9)
fig.savefig(out/'roofline-model.png',dpi=170)
