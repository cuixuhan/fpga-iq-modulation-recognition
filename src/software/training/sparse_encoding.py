"""Canonical output-row CSR; decoding is explicit, not compressed execution."""
from pathlib import Path
import json
import math
import numpy as np
from training.integer_model import sha, save_json


def uint_dtype(maximum):
    if not isinstance(maximum, (int,np.integer)) or maximum < 0:
        raise ValueError('Invalid unsigned capacity')
    for dtype in (np.uint8,np.uint16,np.uint32,np.uint64):
        if maximum <= np.iinfo(dtype).max:
            return np.dtype(dtype)
    raise OverflowError('Index capacity exceeds uint64')


def encode(w):
    if w.dtype != np.int8 or w.ndim not in (2,3) or any(d<=0 for d in w.shape) or np.any(w==-128):
        raise ValueError('Expected symmetric INT8 OI/OIK weights')
    rows=w.reshape(w.shape[0],-1); r,c=np.nonzero(rows)
    values=rows[r,c].copy()
    indices=c.astype(uint_dtype(rows.shape[1]-1))
    indptr=np.concatenate(([0],np.cumsum(np.count_nonzero(rows,axis=1),dtype=np.int64))).astype(uint_dtype(len(values)))
    meta=dict(version='day7-csr-v1',shape=list(w.shape),layout='OIK' if w.ndim==3 else 'OI',flatten='C',
              dtypes={k:str(v.dtype) for k,v in dict(values=values,indices=indices,indptr=indptr).items()})
    return dict(values=values,indices=indices,indptr=indptr),meta


def decode(arrays, meta):
    if meta.get('version')!='day7-csr-v1' or meta.get('flatten')!='C':
        raise ValueError('Corrupt encoding metadata')
    shape=meta.get('shape',[])
    if not isinstance(shape,list) or len(shape) not in (2,3) or any(type(d)!=int or d<=0 for d in shape) or meta.get('layout')!=('OIK' if len(shape)==3 else 'OI'):
        raise ValueError('Invalid encoding shape/layout')
    if set(arrays)!= {'values','indices','indptr'} or set(meta.get('dtypes',{}))!=set(arrays):
        raise ValueError('Invalid encoding keys')
    v,c,p=(arrays[k] for k in ('values','indices','indptr'))
    if any(a.ndim!=1 or str(a.dtype)!=meta['dtypes'][k] for k,a in arrays.items()):
        raise ValueError('Invalid encoding dtype/dimension')
    columns=math.prod(shape[1:])
    if v.dtype!=np.int8 or c.dtype!=uint_dtype(columns-1) or p.dtype!=uint_dtype(len(v)) or np.any(v==0) or np.any(v==-128):
        raise ValueError('Invalid canonical values/index/pointer dtype')
    if len(c)!=len(v) or len(p)!=shape[0]+1 or int(p[0])!=0 or int(p[-1])!=len(v) or any(int(y)<int(x) for x,y in zip(p,p[1:])) or np.any(c>=columns):
        raise ValueError('Invalid encoding pointer/index')
    for i in range(shape[0]):
        cols=c[int(p[i]):int(p[i+1])]
        if np.any(cols[1:]<=cols[:-1]):
            raise ValueError('Indices must be strictly increasing')
    out=np.zeros((shape[0],columns),np.int8)
    for i in range(shape[0]):
        lo,hi=int(p[i]),int(p[i+1]);out[i,c[lo:hi]]=v[lo:hi]
    return out.reshape(shape)


def export(w,directory):
    root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    arrays,meta=encode(w)
    for k,v in arrays.items(): np.save(root/(k+'.npy'),v,allow_pickle=False)
    meta['hashes']={k+'.npy':sha(root/(k+'.npy')) for k in arrays}
    save_json(root/'metadata.json',meta)
    save_json(root/'manifest.json',{'metadata.json':sha(root/'metadata.json')})
    return dict(dense_weight_bytes=w.nbytes,**{k+'_bytes':v.nbytes for k,v in arrays.items()},
                sparse_payload_bytes=sum(v.nbytes for v in arrays.values()),
                actual_file_bytes=sum(p.stat().st_size for p in root.iterdir()))


def load(directory):
    root=Path(directory)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest!={'metadata.json':sha(root/'metadata.json')}:
        raise ValueError('Encoding metadata integrity failure')
    meta=json.loads((root/'metadata.json').read_text(encoding='utf-8'))
    if set(meta.get('hashes',{}))!={'values.npy','indices.npy','indptr.npy'} or any(sha(root/k)!=h for k,h in meta['hashes'].items()):
        raise ValueError('Encoding array integrity failure')
    return decode({k:np.load(root/(k+'.npy'),allow_pickle=False) for k in ('values','indices','indptr')},meta)
