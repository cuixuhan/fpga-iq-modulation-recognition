"""Analytical per-sample Conv1d/Linear MACs; bias, BN, activations and pools excluded."""
import csv
from pathlib import Path
import torch
from torch import nn
from models.baseline_cnn import parameter_count


def profile_model(model: nn.Module, input_shape=(2, 1024)) -> dict:
    """Observe leaf modules without changing weights, buffers or training flags.

    BatchNorm running statistics are buffers, not parameters. One MAC is one
    multiply-accumulate; no FLOP estimate is implied. Linear counts include all
    positions per sample. Profiling always uses a batch of one.
    """
    rows, handles = [], []
    modes = {module: module.training for module in model.modules()}

    def capture(name):
        def hook(module, inputs, output):
            macs = 0
            if isinstance(module, nn.Conv1d):
                macs = output.shape[-1] * module.out_channels * (module.in_channels // module.groups) * module.kernel_size[0]
            elif isinstance(module, nn.Linear):
                macs = output.numel() // output.shape[0] * module.in_features
            rows.append(dict(layer_name=name, layer_type=type(module).__name__,
                             input_shape=list(inputs[0].shape), output_shape=list(output.shape),
                             parameters=sum(p.numel() for p in module.parameters(recurse=False)),
                             macs=int(macs)))
        return hook

    try:
        model.eval()
        for name, module in model.named_modules():
            if not list(module.children()):
                handles.append(module.register_forward_hook(capture(name or 'model')))
        parameter = next(model.parameters())
        with torch.inference_mode():
            output = model(torch.zeros((1, *input_shape), device=parameter.device, dtype=parameter.dtype))
    finally:
        for handle in handles:
            handle.remove()
        for module, mode in modes.items():
            module.training = mode
    counts = parameter_count(model)
    return dict(input_shape=[1, *input_shape], output_shape=list(output.shape), layers=rows,
                total_parameters=counts['total'], trainable_parameters=counts['trainable'],
                macs_per_sample=sum(row['macs'] for row in rows),
                convention='Per sample, Conv1d and Linear only; excludes bias adds, BN, ReLU, pooling and GAP. MACs are not FLOPs.')


def write_profile(path, profile: dict) -> None:
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['layer_name', 'layer_type', 'input_shape', 'output_shape', 'parameters', 'macs'])
        writer.writeheader()
        writer.writerows(profile['layers'])


def main():
    """Standalone profile; refuses to replace an existing CSV."""
    import argparse
    import json
    from training.train import load_checkpoint
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', default='checkpoints/best_model.pt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    model, _ = load_checkpoint(args.checkpoint, 'cpu')
    profile = profile_model(model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_profile(args.output, profile)
    print(json.dumps(profile, indent=2))


if __name__ == '__main__':
    main()
