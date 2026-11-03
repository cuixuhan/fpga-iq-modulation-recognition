"""Day 5 comparisons using the unchanged Day 4 prediction/metric conventions."""
import torch
import numpy as np
from training.evaluate import evaluate
from training.metrics import plt, write_csv
from training.quantization import error_metrics, fake_quantize
from training.quantized_model import ACTIVATION_POINTS


def evaluate_logits(model, loader):
    chunks = []
    hook = model.register_forward_hook(lambda module, args, output: chunks.append(output.detach().cpu()))
    try:
        result = evaluate(model, loader, 'cpu')
    finally:
        hook.remove()
    return result, torch.cat(chunks)


@torch.inference_mode()
def activation_errors(folded, loader, params):
    """Local Q/DQ error on FP32 activations, not propagated network error."""
    totals = {name: dict(count=0, absolute=0., squared=0., maximum=0., clipped=0) for name in ACTIVATION_POINTS}
    def observe(name, x):
        dq = fake_quantize(x, params[name])
        delta = (x.double() - dq.double()).abs()
        raw = torch.round(x / params[name].scale) + params[name].zero_point
        row = totals[name]
        row['count'] += x.numel()
        row['absolute'] += delta.sum().item()
        row['squared'] += delta.square().sum().item()
        row['maximum'] = max(row['maximum'], delta.max().item())
        row['clipped'] += ((raw < params[name].qmin) | (raw > params[name].qmax)).sum().item()
    hooks = []
    try:
        for name in ACTIVATION_POINTS[1:]:
            hooks.append(folded.get_submodule(name).register_forward_hook(
                lambda module, args, output, name=name: observe(name, output)))
        for x, _, _ in loader:
            observe('input', x)
            folded(x)
    finally:
        for hook in hooks:
            hook.remove()
    return [dict(layer=name, count=r['count'], mae=r['absolute']/r['count'],
                 mse=r['squared']/r['count'], max_abs_error=r['maximum'],
                 clipping_fraction=r['clipped']/r['count']) for name, r in totals.items()]


def plot_comparison(root, analyses, iq, input_params):
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(root / name, dpi=150)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4))
    names = list(analyses)
    values = [analyses[name]['overall']['accuracy'] * 100 for name in names]
    bars = ax.bar(names, values)
    ax.bar_label(bars, fmt='%.2f%%')
    ax.set(ylabel='Test accuracy (%)', ylim=(0, 100), title='Day 5 PTQ numerical reference')
    ax.tick_params(axis='x', labelrotation=15)
    save(fig, 'fp32_vs_int8_accuracy.png')
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, analysis in analyses.items():
        rows = analysis['accuracy_by_snr']
        ax.plot([r['snr_db'] for r in rows], [r['accuracy'] for r in rows], marker='o', label=name)
    ax.set(xlabel='SNR (dB)', ylabel='Test accuracy', ylim=(0, 1))
    ax.legend(); ax.grid(alpha=.3)
    save(fig, 'fp32_vs_int8_snr.png')
    selected = analyses['W8A8_channel']
    cm = np.asarray(selected['confusion_matrix'])
    labels = [r['modulation'] for r in selected['per_class']]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(cm, cmap='Blues')
    for i in range(5):
        for j in range(5):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center', color='white' if cm[i,j] > cm.max()/2 else 'black')
    ax.set(xticks=range(5), yticks=range(5), xticklabels=labels, yticklabels=labels,
           xlabel='Predicted', ylabel='True', title='W8A8 per-channel confusion matrix (counts)')
    save(fig, 'confusion_matrix_int8.png')
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey=True)
    for ax, label in zip(axes.flat, labels):
        for name in ('FP32', 'W8A8_channel', 'W8A8_tensor'):
            rows = [r for r in analyses[name]['per_class_accuracy_by_snr'] if r['modulation'] == label]
            ax.plot([r['snr_db'] for r in rows], [r['accuracy'] for r in rows], marker='.', label=name)
        ax.set(title=label, xlabel='SNR (dB)', ylabel='Accuracy', ylim=(0, 1))
        ax.grid(alpha=.3)
    axes[0,0].legend(fontsize=8)
    axes[-1,-1].set_visible(False)
    save(fig, 'per_class_accuracy_vs_snr.png')
    dq = fake_quantize(iq, input_params)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes[0,0].plot(iq[0, :128], label='FP32')
    axes[0,0].plot(dq[0, :128], '--', label='INT8 dequantized')
    axes[0,0].set(title='I waveform (first 128 samples)', xlabel='Sample', ylabel='I')
    axes[0,0].legend()
    axes[0,1].plot((dq-iq)[0, :128])
    axes[0,1].set(title='I quantization error', xlabel='Sample', ylabel='Reconstructed - original')
    for ax, x, title in zip(axes[1], (iq, dq), ('FP32 IQ', 'INT8 dequantized IQ')):
        ax.scatter(x[0], x[1], s=5, alpha=.5)
        ax.set(title=title, xlabel='I', ylabel='Q', aspect='equal')
    save(fig, 'iq_quantization.png')
