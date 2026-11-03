"""Inference-only W8/W8A8 fake quantization. All MACs and biases remain FP32."""
from copy import deepcopy
import torch
from torch import nn
from training.quantization import calculate_qparams, fake_quantize, error_metrics

ACTIVATION_POINTS = ('input', 'features.2', 'features.6', 'features.10', 'features.11', 'classifier')
WEIGHT_POINTS = ('features.0', 'features.4', 'features.8', 'classifier')


def fold_batch_norm(model):
    if any(m.training for m in model.modules()):
        raise ValueError('BN folding requires an eval model')
    folded = deepcopy(model)
    for index in (0, 4, 8):
        conv, bn = folded.features[index:index + 2]
        if not isinstance(conv, nn.Conv1d) or not isinstance(bn, nn.BatchNorm1d):
            raise ValueError('Unexpected baseline architecture')
        folded.features[index] = torch.nn.utils.fuse_conv_bn_eval(conv, bn)
        folded.features[index + 1] = nn.Identity()
    return folded.eval()


class FakeQuantizer(nn.Module):
    def __init__(self, params):
        super().__init__()
        self.register_buffer('scale', params.scale.clone())
        self.register_buffer('zero_point', params.zero_point.clone())
        self.qmin, self.qmax, self.axis = params.qmin, params.qmax, params.axis

    def forward(self, x):
        return fake_quantize(x, self)


class PTQReference(nn.Module):
    def __init__(self, folded, per_channel=True, activation_params=None, layers=None):
        super().__init__()
        if any(isinstance(m, nn.BatchNorm1d) for m in folded.modules()):
            raise ValueError('Fold BN before quantizing weights')
        self.model = deepcopy(folded).eval()
        selected = set(WEIGHT_POINTS if layers is None else layers)
        if not selected.issubset(WEIGHT_POINTS):
            raise ValueError('Unknown weight layer')
        self.weight_report = []
        with torch.no_grad():
            for name, layer in self.model.named_modules():
                if name in selected:
                    params = calculate_qparams(layer.weight, axis=0 if per_channel else None)
                    dq = fake_quantize(layer.weight, params)
                    self.weight_report.append(dict(layer=name, count=layer.weight.numel(),
                        **params.as_dict(), **error_metrics(layer.weight, dq)))
                    layer.weight.copy_(dq)
        self.input_quantizer = nn.Identity()
        if activation_params is not None:
            if set(activation_params) != set(ACTIVATION_POINTS):
                raise ValueError('Missing or unexpected activation calibration points')
            self.input_quantizer = FakeQuantizer(activation_params['input'])
            for name in ACTIVATION_POINTS[1:]:
                parent_name, _, key = name.rpartition('.')
                parent = self.model.get_submodule(parent_name) if parent_name else self.model
                original = getattr(parent, key)
                setattr(parent, key, nn.Sequential(original, FakeQuantizer(activation_params[name])))
        self.requires_grad_(False)
        self.eval()

    def forward(self, x):
        return self.model(self.input_quantizer(x))
