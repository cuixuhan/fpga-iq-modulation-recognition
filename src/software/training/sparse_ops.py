"""Day 7: select operands BEFORE multiplication; counts come from that selection.

Counts have axes [sample, region (data,padding), pair (00,01,10,11)].
Only Conv/Linear MACs are counted, not bias, requantization, pooling or scans.
"""
import numpy as np
from training import integer_ops as op

MODES = ('dense', 'weight_skip', 'activation_skip', 'both_skip')


def _schedule(patches, weights, bias, bounds, valid, mode):
    if mode not in MODES:
        raise ValueError('Unsupported sparse mode')
    n, length, fanin = patches.shape
    counts = np.zeros((n, 2, 4), np.int64)
    executed = np.zeros((n, 2), np.int64)
    result = np.empty((n, len(weights), length), np.int64)
    az = patches == 0
    region_counts = [((az & inside).sum(axis=1), ((~az) & inside).sum(axis=1))
                     for inside in (valid, ~valid)]
    for o, weight in enumerate(weights):
        wz = weight == 0
        # Pair classification is separate from the actual multiply selection below.
        for region, (a0,a1) in enumerate(region_counts):
            counts[:, region, 0] += a0[:, wz].sum(1)
            counts[:, region, 1] += a1[:, wz].sum(1)
            counts[:, region, 2] += a0[:, ~wz].sum(1)
            counts[:, region, 3] += a1[:, ~wz].sum(1)
        columns = np.flatnonzero(~wz) if mode in ('weight_skip', 'both_skip') else np.arange(fanin)
        a = patches[:, :, columns]
        w = weight[columns]
        region_mask = valid[:, columns]
        if mode in ('activation_skip', 'both_skip'):
            # There is no multiply on the excluded entries. INT64 precedes centering.
            batch, pos, col = np.nonzero(a)
            products = np.zeros(a.shape, np.int64)
            products[batch, pos, col] = a[batch, pos, col] * w[col]
            real = region_mask[pos, col]
            executed[:, 0] += np.bincount(batch[real], minlength=n)
            executed[:, 1] += np.bincount(batch[~real], minlength=n)
        else:
            products = a * w
            executed[:, 0] += int(region_mask.sum())
            executed[:, 1] += int((~region_mask).sum())
        result[:, o] = products.sum(2) + int(bias[o])
    if np.any(np.abs(result) > bounds[None, :, None]):
        raise OverflowError('Accumulator violated Day 6 bound')
    return result, dict(pairs=counts, executed=executed,
                        skipped=counts.sum(2)-executed)


def conv1d(x, w, b, zx, padding=0, mode='dense', stride=1, dilation=1, groups=1):
    if stride != 1 or dilation != 1 or groups != 1 or not isinstance(padding, int) or padding < 0:
        raise ValueError('Only stride=dilation=groups=1, nonnegative integer padding')
    a, weight = op.codes(x), op.codes(w)
    if a.ndim != 3 or weight.ndim != 3 or a.shape[1] != weight.shape[1]:
        raise ValueError('Expected NCL/OIK')
    bounds = op.accumulator_bound(w, b, zx)
    n, ci, length = a.shape
    kernel = w.shape[2]
    outlen = length + 2*padding-kernel+1
    if outlen <= 0:
        raise ValueError('Kernel longer than padded input')
    a = np.pad(a, ((0,0),(0,0),(padding,padding)), constant_values=zx)-zx
    patches = np.lib.stride_tricks.sliding_window_view(a, kernel, axis=2)
    patches = patches.transpose(0,2,1,3).reshape(n,outlen,ci*kernel)
    positions = np.arange(outlen)[:,None]+np.arange(kernel)[None,:]-padding
    valid = np.tile((positions >= 0) & (positions < length), (1,ci))
    return _schedule(patches, weight.reshape(len(w),-1), b, bounds, valid, mode)


def linear(x, w, b, zx, mode='dense'):
    a, weight = op.codes(x), op.codes(w)
    if a.ndim != 2 or weight.ndim != 2 or a.shape[1] != weight.shape[1]:
        raise ValueError('Expected NC/OI')
    bounds = op.accumulator_bound(w,b,zx)
    out, stats = _schedule((a-zx)[:,None,:],weight,b,bounds,np.ones((1,a.shape[1]),bool),mode)
    return out[:,:,0], stats
