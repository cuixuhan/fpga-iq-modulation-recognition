"""Separate network path, sharing only the established Day 6 postprocessing."""
import numpy as np
from training.integer_model import IntegerModel
from training import integer_ops as op, sparse_ops as sparse


class SparseModel(IntegerModel):
    def __init__(self, arrays, metadata, mode='both_skip'):
        if mode not in sparse.MODES:
            raise ValueError('Unsupported sparse mode')
        super().__init__(arrays,metadata)
        self.mode = mode
        for i, layer in enumerate(metadata['layers']):
            if layer['weight_layout'] != ('OIK' if i<3 else 'OI') or any(layer.get(k,1)!=1 for k in ('stride','dilation','groups')):
                raise ValueError('Unsupported convolution/layout')

    def forward(self, q, trace=False):
        if q.dtype != np.int8 or q.ndim != 3 or list(q.shape[1:]) != self.metadata['input_shape']:
            raise ValueError('Expected INT8 (B,2,1024)')
        points={'input':q.copy()}; records={}; a=q
        grids=self.metadata['grids']
        for i, layer in enumerate(self.metadata['layers']):
            if i==3:
                gx=a
                a,acc,st=op.gap(a,grids['features.10']['zero_point'],self.arrays['gap_M'],self.arrays['gap_shift'],grids['features.11']['zero_point'])
                points['features.11']=a[:,:,None].copy()
                records['gap']=dict(input=gx.copy(),acc=acc,output=a.copy(),stats=st)
            key=layer['key']; inp=a
            w,b,m,s=(self.arrays[key+'_'+p] for p in ('weight','bias','M','shift'))
            zx=grids[layer['input']]['zero_point']; zy=grids[layer['output']]['zero_point']
            if i<3:
                acc,counts=sparse.conv1d(a,w,b,zx,padding=layer['padding'],mode=self.mode)
                a,st=op.requantize(acc,m[None,:,None],s[None,:,None],zy,relu=True)
            else:
                acc,counts=sparse.linear(a,w,b,zx,mode=self.mode)
                a,st=op.requantize(acc,m,s,zy)
            points[layer['output']]=a.copy()
            records[layer['name']]=dict(input=inp.copy(),acc=acc,output=a.copy(),stats=st,counts=counts)
            if i<2:
                a=op.maxpool(a); points[f'pool{i+1}']=a.copy()
        return (a,points,records) if trace else a
