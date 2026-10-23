from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
out = Path(__file__).resolve().parents[1] / 'measurements'
fig, ax = plt.subplots(figsize=(11, 6.4), dpi=170)
fig.patch.set_facecolor('#f8fafc'); ax.set_facecolor('#f8fafc')
ax.set_xlim(0, 11); ax.set_ylim(0, 6.4); ax.axis('off')
ax.text(.3, 6.05, 'The reduction tree changes the answer', fontsize=21, weight='bold', color='#14283f')
ax.text(.3, 5.55, 'Same binary64 inputs:  [M, 1, −M, 1]     M = 2⁵⁴     Exact sum = 2', fontsize=13)
rows = [
    (4.25, 'Ordered', '(((0 + M) + 1) − M) + 1', '1', '#ae4b36', 'The first 1 rounds away beside M.'),
    (2.75, 'Four lanes', '(M + 1) + (−M + 1)', '0', '#a66b13', 'Both 1s round away before the final add.'),
    (1.25, 'Compensated', 'running sum 1  +  saved correction 1', '2', '#14766d', 'Keep low-order pieces in a second accumulator.'),
]
for y, name, expr, result, color, note in rows:
    ax.add_patch(FancyBboxPatch((.25,y-.55),10.5,1.25,boxstyle='round,pad=0.05',facecolor='white',edgecolor='#cdd6e1'))
    ax.text(.5,y+.25,name,fontsize=14,weight='bold',color=color)
    ax.text(3.05,y+.25,expr,fontsize=14)
    ax.text(9.8,y+.22,result,fontsize=22,weight='bold',color=color)
    ax.text(.5,y-.23,note,fontsize=12,color='#33465d')
ax.text(.3,.22,'A faster candidate is eligible only if its answer meets the application contract.',fontsize=12,weight='bold')
fig.savefig(out/'rounding.png',bbox_inches='tight')
