#!/usr/bin/env python3
"""Draw scan.svg and scan.png: the four-chunk exclusive scan with its phase dependencies."""
import pathlib

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INPUT = [[3, 1], [4, 1], [5, 9], [2, 6]]
LOCAL = [[0, 3], [0, 4], [0, 5], [0, 2]]
TOTALS = [4, 5, 14, 8]
OFFSETS = [0, 4, 9, 23]
OUTPUT = [[0, 3], [4, 8], [9, 14], [23, 25]]
FILLS = ['#dcecff', '#e5e4fc', '#d9f2e8', '#ffebd3']
INK, MUTED, EDGE, ARROW, BG = '#132b49', '#46556a', '#8d9bae', '#52657f', '#f5f7fb'

W, H = 760.0, 358.0
LABEL_X, BOX_X0, BOX_W, GAP, BOX_H = 10.0, 196.0, 123.0, 18.0, 33.0
ROW_TOP = [80.0, 144.0, 208.0, 272.0]
ROWS = [('Input chunks', [' '.join(map(str, c)) for c in INPUT]),
        ('1. Local scans in parallel', [f'{LOCAL[k][0]} {LOCAL[k][1]}  | total {TOTALS[k]}' for k in range(4)]),
        ('2. Serial scan of four totals', [f'+ {o}' for o in OFFSETS]),
        ('3. Add offsets in parallel', [' '.join(map(str, c)) for c in OUTPUT])]


def col_x(k):
    return BOX_X0 + k * (BOX_W + GAP)


def y(top):
    return H - top


fig = plt.figure(figsize=(W / 72, H / 72), facecolor=BG)
ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis('off')
ax.text(LABEL_X, y(30), 'Change the dependency graph', color=INK, fontsize=22, fontweight='bold', va='baseline')
ax.text(LABEL_X, y(54), 'Exclusive scan: output[i] = sum of inputs before i', color=MUTED, fontsize=12, va='baseline')
for (label, cells), top in [(ROWS[r], ROW_TOP[r]) for r in range(4)]:
    ax.text(LABEL_X, y(top + BOX_H / 2), label, color=MUTED, fontsize=10, fontweight='bold', va='center')
    for k, text in enumerate(cells):
        ax.add_patch(FancyBboxPatch((col_x(k), y(top + BOX_H)), BOX_W, BOX_H, boxstyle='round,pad=0,rounding_size=3',
                                    facecolor=FILLS[k], edgecolor=EDGE, linewidth=1))
        ax.text(col_x(k) + BOX_W / 2, y(top + BOX_H / 2), text, color=INK, fontsize=11, fontweight='bold',
                ha='center', va='center')


def arrow(x0, y0, x1, y1, style='-|>'):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=9, color=ARROW,
                                 linewidth=1, shrinkA=0, shrinkB=0))


for k in range(4):
    cx = col_x(k) + BOX_W / 2
    for top, bottom in ((ROW_TOP[0], ROW_TOP[1]), (ROW_TOP[2], ROW_TOP[3])):
        arrow(cx, y(top + BOX_H + 2), cx, y(bottom - 2))
# offset[k+1] = offset[k] + total[k]: each total feeds only later chunks.
for k in range(3):
    arrow(col_x(k) + BOX_W * 0.75, y(ROW_TOP[1] + BOX_H + 2), col_x(k + 1) + BOX_W * 0.25, y(ROW_TOP[2] - 2))
    arrow(col_x(k) + BOX_W + 1, y(ROW_TOP[2] + BOX_H / 2), col_x(k + 1) - 1, y(ROW_TOP[2] + BOX_H / 2))
ax.text(LABEL_X, y(338), 'Only chunk summaries cross the middle phase: offset k sums totals 0..k-1. '
        'Output chunks have separate owners.', color=MUTED, fontsize=10, va='baseline')

here = pathlib.Path(__file__).resolve().parents[1]
fig.savefig(here / 'scan.svg', facecolor=BG, metadata={'Date': None})
fig.savefig(here / 'scan.png', facecolor=BG, dpi=160)
