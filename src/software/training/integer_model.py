"""Standalone integer package loader and forward. Torch used only offline."""
from pathlib import Path
import hashlib
import json
import numpy as np
from training import integer_ops as ops

POINTS = ('input','features.2','features.6','features.10','features.11','classifier')
LAYERS = ('features.0','features.4','features.8','classifier')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def prepare(folded, activations, weight_params, provenance):
    """Offline only: reuse frozen Day 5 scales, quantize fused bias in float64."""
    import torch
    arrays, layers = {}, []
    grids = {}
    if set(activations) != set(POINTS):
        raise ValueError('Missing frozen activation grids')
    for name, p in activations.items():
        s, z = float(p['scale']), p['zero_point']
        if not np.isfinite(s) or s <= 0 or int(z) != z or p['axis'] is not None or (p['qmin'],p['qmax']) != (-128,127):
            raise ValueError('Invalid activation grid')
        grids[name] = dict(scale=s, zero_point=ops.zero_point(int(z)))
    for i, name in enumerate(LAYERS):
        layer = folded.get_submodule(name)
        p = next(p for p in weight_params if p['scheme']=='channel' and p['layer']==name)
        sw = torch.tensor(p['scale'], dtype=torch.float32)
        if p['axis'] != 0 or tuple(sw.shape) != (layer.weight.shape[0],)+(1,)*(layer.weight.ndim-1) or not torch.isfinite(sw).all() or not (sw>0).all() or np.any(np.array(p['zero_point']) != 0) or (p['qmin'],p['qmax']) != (-127,127):
            raise ValueError('Invalid frozen channel grid')
        q = torch.round(layer.weight.detach()/sw).clamp(-127,127).to(torch.int8).numpy()
        inp, out = (POINTS[i],POINTS[i+1]) if i<3 else (POINTS[4],POINTS[5])
        sx, sy = grids[inp]['scale'], grids[out]['scale']
        bias_scales = sx*sw.numpy().reshape(-1).astype(np.float64)
        b = ops.bias_quantize(layer.bias.detach().numpy(), bias_scales)
        bound = ops.accumulator_bound(q,b,grids[inp]['zero_point'])
        ratio = bias_scales/sy
        m, s, err = ops.fixed_params(ratio,bound)
        if i<3:
            if layer.stride != (1,) or layer.dilation != (1,) or layer.groups != 1 or layer.padding_mode != 'zeros':
                raise ValueError('Unsupported frozen convolution')
            padding = layer.padding[0]
        else:
            padding = 0
        key = f'layer{i}'
        for suffix, arr in [('weight',q),('bias',b),('M',m),('shift',s)]:
            arrays[f'{key}_{suffix}'] = arr.copy()
        layers.append(dict(name=name,key=key,input=inp,output=out,padding=padding,
            weight_scale=sw.numpy().reshape(-1).tolist(), weight_zero_point=0, axis=0,
            weight_layout='OIK' if i<3 else 'OI', activation_layout='NCL' if i<3 else 'NC',
            bias_scale=bias_scales.tolist(), bound=bound.tolist(), ratio=ratio.tolist(),
            ratio_abs_error=err.tolist(), ratio_error_bound_codes=(bound*err).tolist(),
            product_bound=[int(x)*int(y) for x,y in zip(bound,m)],
            bias_rounding_max_codes=float(np.max(np.abs(b.astype(float)-layer.bias.detach().numpy()/bias_scales)))))
    length=256
    bound=length*max(abs(-128-grids[POINTS[3]]['zero_point']),abs(127-grids[POINTS[3]]['zero_point']))
    ratio=grids[POINTS[3]]['scale']/(length*grids[POINTS[4]]['scale'])
    m,s,e=ops.fixed_params([ratio],[bound])
    arrays['gap_M'], arrays['gap_shift'] = m,s
    metadata=dict(contract=ops.CONTRACT, grids=grids,layers=layers,provenance=provenance,
        input_shape=[2,1024], output_shape=[5], gap=dict(length=length,bound=bound,
        ratio=ratio,ratio_abs_error=float(e[0]),ratio_error_bound_codes=float(e[0]*bound),product_bound=bound*int(m[0])))
    return IntegerModel(arrays,metadata)


class IntegerModel:
    def __init__(self, arrays, metadata):
        self.arrays={k:v.copy() for k,v in arrays.items()}
        self.metadata=metadata
        for x in self.arrays.values():
            x.flags.writeable=False

    def encode(self, x):
        """FP32 -> INT8 boundary, same FP32 division/rounding as frozen Day 5."""
        p=self.metadata['grids']['input']
        a=np.asarray(x,dtype=np.float32)
        if not np.isfinite(a).all():
            raise ValueError('Nonfinite boundary input')
        return np.clip(np.rint(a/np.float32(p['scale']))+p['zero_point'],-128,127).astype(np.int8)

    def decode(self, q, point='classifier'):
        p=self.metadata['grids'][point]
        return (np.asarray(q).astype(np.float64)-p['zero_point'])*p['scale']

    def forward(self, q, trace=False):
        if q.dtype != np.int8 or q.ndim != 3 or list(q.shape[1:]) != self.metadata['input_shape']:
            raise ValueError('Expected INT8 (B,2,1024)')
        points={'input':q.copy()}; records={}; a=q
        grids=self.metadata['grids']
        for i,layer in enumerate(self.metadata['layers']):
            if i==3:
                gx=a
                a,acc,st=ops.gap(a,grids['features.10']['zero_point'],self.arrays['gap_M'],self.arrays['gap_shift'],grids['features.11']['zero_point'])
                points['features.11']=a[:,:,None].copy()
                records['gap']=dict(input=gx.copy(),acc=acc,output=a.copy(),stats=st)
            key=layer['key']; inp=a
            w,b,m,s=(self.arrays[key+'_'+part] for part in ('weight','bias','M','shift'))
            if i<3:
                acc=ops.conv1d(a,w,b,grids[layer['input']]['zero_point'],padding=layer['padding'])
                a,st=ops.requantize(acc,m[None,:,None],s[None,:,None],grids[layer['output']]['zero_point'],relu=True)
            else:
                acc=ops.linear(a,w,b,grids[layer['input']]['zero_point'])
                a,st=ops.requantize(acc,m,s,grids[layer['output']]['zero_point'])
            points[layer['output']]=a.copy()
            records[layer['name']]=dict(input=inp.copy(),acc=acc,output=a.copy(),stats=st)
            if i<2:
                a=ops.maxpool(a)
                points[f'pool{i+1}']=a.copy()
        return (a,points,records) if trace else a

    def export(self, directory):
        directory=Path(directory); directory.mkdir(parents=True,exist_ok=False)
        np.savez_compressed(directory/'integers.npz',**self.arrays)
        self.metadata['arrays']={k:dict(dtype=str(v.dtype),shape=list(v.shape),bytes=v.nbytes) for k,v in self.arrays.items()}
        save_json(directory/'metadata.json',self.metadata)
        save_json(directory/'manifest.json',{name:sha(directory/name) for name in ('metadata.json','integers.npz')})

    @classmethod
    def load(cls,directory):
        directory=Path(directory)
        manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        if set(manifest) != {'metadata.json','integers.npz'} or any(sha(directory/k)!=v for k,v in manifest.items()):
            raise ValueError('Package integrity failure')
        meta=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
        if meta['contract'] != ops.CONTRACT:
            raise ValueError('Unsupported integer contract')
        with np.load(directory/'integers.npz',allow_pickle=False) as f:
            arrays={k:f[k] for k in f.files}
        if set(arrays)!=set(meta['arrays']):
            raise ValueError('Package array keys mismatch')
        for k,v in arrays.items():
            d=meta['arrays'][k]
            if str(v.dtype)!=d['dtype'] or list(v.shape)!=d['shape'] or v.nbytes!=d['bytes']:
                raise ValueError('Package array schema mismatch')
            expected=np.int8 if k.endswith('_weight') else np.int32
            if v.dtype!=expected:
                raise ValueError('Incorrect integer storage dtype')
        for l in meta['layers']:
            k=l['key']; b=ops.accumulator_bound(arrays[k+'_weight'],arrays[k+'_bias'],meta['grids'][l['input']]['zero_point'])
            if b.tolist()!=l['bound'] or any(int(v)*int(m)>ops.I64 for v,m in zip(b,arrays[k+'_M'])):
                raise ValueError('Invalid package bounds')
        return cls(arrays,meta)
