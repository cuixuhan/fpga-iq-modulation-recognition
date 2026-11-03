"""Persist raw metrics and figures without smoothing."""
import csv
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / '.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from comm_signal.dataset import MODULATION_TO_LABEL, SNR_LIST


def test_metrics(result):
    y, pred, snr = result['y'], result['pred'], result['snr']
    cm = np.zeros((5, 5), dtype=np.int64)
    np.add.at(cm, (y, pred), 1)
    rows = []
    for level in SNR_LIST:
        mask = snr == level
        total = int(mask.sum())
        correct = int((y[mask] == pred[mask]).sum())
        rows.append(dict(snr_db=level, correct=correct, total=total,
                         accuracy=correct / total if total else None))
    return cm, rows


def write_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_artifacts(root, history, result, summary):
    root = Path(root)
    for name in ('training', 'confusion_matrix', 'snr_accuracy'):
        (root / name).mkdir(parents=True, exist_ok=True)
    write_csv(root / 'training/history.csv', history)
    for metric in ('loss', 'accuracy'):
        fig, ax = plt.subplots(figsize=(7, 4))
        for split in ('train', 'val'):
            ax.plot([h['epoch'] for h in history], [h[f'{split}_{metric}'] for h in history], label=split)
        ax.set(xlabel='Epoch', ylabel=metric.capitalize(), title=f'FP32 baseline {metric}')
        ax.legend()
        fig.tight_layout()
        fig.savefig(root / f'training/{metric}_curve.png', dpi=160)
        plt.close(fig)
    cm, rows = test_metrics(result)
    np.save(root / 'confusion_matrix/raw_counts.npy', cm)
    np.savetxt(root / 'confusion_matrix/raw_counts.csv', cm, delimiter=',', fmt='%d')
    normalized = np.divide(cm, cm.sum(1, keepdims=True), out=np.zeros_like(cm, dtype=float), where=cm.sum(1, keepdims=True) != 0)
    np.savetxt(root / 'confusion_matrix/normalized.csv', normalized, delimiter=',')
    fig, ax = plt.subplots(figsize=(7, 6))
    display = ax.imshow(normalized, vmin=0, vmax=1, cmap='Blues')
    ax.set(xticks=range(5), yticks=range(5), xticklabels=list(MODULATION_TO_LABEL),
           yticklabels=list(MODULATION_TO_LABEL), xlabel='Predicted class', ylabel='True class',
           title='Test confusion matrix (row normalized)')
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f'{normalized[i,j]:.2f}\n({cm[i,j]})', ha='center', va='center',
                    color='white' if normalized[i,j] > .5 else 'black')
    fig.colorbar(display, ax=ax)
    fig.tight_layout()
    fig.savefig(root / 'confusion_matrix/confusion_matrix.png', dpi=160)
    plt.close(fig)
    write_csv(root / 'snr_accuracy/accuracy_vs_snr.csv', rows)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([r['snr_db'] for r in rows], [r['accuracy'] for r in rows], marker='o')
    ax.set(xlabel='SNR (dB)', ylabel='Accuracy', ylim=(0, 1), xticks=SNR_LIST, title='FP32 test accuracy vs SNR')
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(root / 'snr_accuracy/accuracy_vs_snr.png', dpi=160)
    plt.close(fig)
    np.savez(root / 'training/test_predictions.npz', y=result['y'], pred=result['pred'], snr=result['snr'])
    summary.update(test={k: result[k] for k in ('loss', 'accuracy', 'correct', 'total')},
                   accuracy_by_snr=rows, confusion_matrix=cm.tolist())
    (root / 'training/summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary
