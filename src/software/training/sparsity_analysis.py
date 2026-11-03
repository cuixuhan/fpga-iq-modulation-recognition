"""Day 7 tables; weighted group rates always use sums of element/MAC counts."""
import csv
from collections import defaultdict
import numpy as np


def write_csv(path,rows):
    rows=list(rows)
    if not rows: raise ValueError('No rows to write')
    with open(path,'w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def grouped(rows,dimensions,counts,rate=None):
    groups=defaultdict(list)
    for r in rows:
        for kind,label,snr in [('overall','all','all'),('class',r['label'],'all'),('snr','all',r['snr_db']),('class_snr',r['label'],r['snr_db'])]:
            groups[(kind,label,snr,*(r[d] for d in dimensions))].append(r)
    out=[]
    for key,items in groups.items():
        row=dict(group=key[0],label=key[1],snr_db=key[2],**dict(zip(dimensions,key[3:])))
        row.update({k:sum(int(r[k]) for r in items) for k in counts})
        row['samples']=len(items)
        if rate:
            numerator,denominator,name=rate
            row[name]=row[numerator]/row[denominator] if row[denominator] else None
            rates=[r[numerator]/r[denominator] for r in items if r[denominator]]
            row.update(sample_rate_min=min(rates) if rates else None,
                       sample_rate_median=float(np.median(rates)) if rates else None,
                       sample_rate_max=max(rates) if rates else None)
        out.append(row)
    return out


def activation_rows(values,z,location,ids,labels,snr):
    zeros=np.count_nonzero(values.reshape(len(values),-1)==z,axis=1)
    total=values[0].size
    return [dict(sample_id=int(ids[j]),label=int(labels[j]),snr_db=int(snr[j]),location=location,
                 zero_point=int(z),zero=int(v),total=total,zero_fraction=int(v)/total)
            for j,v in enumerate(zeros)]


def mac_rows(counts,mode,layer,ids,labels,snr):
    rows=[]
    for j in range(len(ids)):
        for region,index in [('in_bounds',0),('padding',1),('total',None)]:
            pair=counts['pairs'][j].sum(0) if index is None else counts['pairs'][j,index]
            executed=int(counts['executed'][j].sum() if index is None else counts['executed'][j,index])
            d=int(pair.sum());skipped=d-executed
            rows.append(dict(sample_id=int(ids[j]),label=int(labels[j]),snr_db=int(snr[j]),layer=layer,mode=mode,region=region,
                             **dict(zip(('n00','n01','n10','n11'),map(int,pair))),D=d,executed=executed,skipped=skipped,
                             skip_fraction=skipped/d if d else None))
    return rows
