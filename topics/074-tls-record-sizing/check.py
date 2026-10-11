#!/usr/bin/env python3
"""Check cap/write boundaries against an iterative external framing oracle.

Every gate is an explicit conditional so `python -O` cannot disable it.
"""
import json,pathlib,subprocess,sys
binary=str(pathlib.Path(sys.argv[1]).resolve());count=0
for cap in (1024,4096,16384):
    for length in (1,127,128,1023,1024,1025,4095,4096,4097,16383,16384,16385):
        for write_size in sorted({128,4096,length}):
            row=json.loads(subprocess.check_output([binary,str(cap),str(length),str(write_size),'1'],text=True))
            pending=length;records=0;wire=0
            while pending:
                group=min(pending,write_size);pending-=group
                while group:
                    take=min(group,cap);group-=take;records+=1;wire+=take+22
            if (row['cap'],row['length'],row['write_size'],row['repeats'])!=(cap,length,write_size,1):sys.exit(f'row echoes ({row["cap"]},{row["length"]},{row["write_size"]},{row["repeats"]}) for invocation ({cap},{length},{write_size},1)')
            if not (row['correct'] and row['records']==records and row['wire_bytes']==wire):sys.exit(f'oracle mismatch cap={cap} length={length} write_size={write_size}: expected records={records} wire_bytes={wire}, got {row}')
            count+=1
for args in [('0','1','1','1'),('16385','1','1','1'),('1024','0','1','1'),('1024','1','0','1'),('1024','1','1','0'),('1024','1048577','1','1'),('1024','-1','1','1')]:
    if subprocess.run([binary,*args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:sys.exit(f'invalid input accepted: {args}')
print(f'{count} boundary oracle cases; 7 invalid-input rejections passed')
