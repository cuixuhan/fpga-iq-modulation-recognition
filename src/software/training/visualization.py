"""Day 4 figures using measured predictions and saved training history."""
import csv
from pathlib import Path
import numpy as np
from training.metrics import plt
from comm_signal.visualization import waveform_psd


def plot_analysis(root, analysis, history_path, dataset, limit=6):
    root = Path(root)
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(root / name, dpi=150)
        plt.close(fig)
    cm = np.asarray(analysis['confusion_matrix'])
    names = [r['modulation'] for r in analysis['per_class']]
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, cmap='Blues')
    ax.set(xticks=range(len(names)), yticks=range(len(names)), xticklabels=names,
           yticklabels=names, xlabel='Predicted class', ylabel='True class', title='Test confusion matrix (counts)')
    for i in range(len(names)):
        for j in range(len(names)):
            ax.text(j, i, str(cm[i,j]), ha='center', va='center', color='white' if cm[i,j] > cm.max()/2 else 'black')
    fig.colorbar(im, ax=ax)
    save(fig, 'confusion_matrix.png')
    for by_class, filename in [(False, 'accuracy_vs_snr.png'), (True, 'per_class_accuracy_vs_snr.png')]:
        fig, ax = plt.subplots(figsize=(8, 5))
        groups = [(name, [r for r in analysis['per_class_accuracy_by_snr'] if r['modulation']==name]) for name in names] if by_class else [('All classes', analysis['accuracy_by_snr'])]
        for name, rows in groups:
            ax.plot([r['snr_db'] for r in rows], [np.nan if r['accuracy'] is None else r['accuracy'] for r in rows], marker='o', label=name)
        ax.set(xlabel='SNR (dB)', ylabel='Accuracy', ylim=(0,1))
        ax.legend(); ax.grid(alpha=.3)
        save(fig, filename)
    with Path(history_path).open() as stream:
        history = list(csv.DictReader(stream))
    fig, axes = plt.subplots(1, 2, figsize=(11,4))
    for ax, metric in zip(axes, ('loss','accuracy')):
        for split in ('train','val'):
            ax.plot([int(r['epoch']) for r in history], [float(r[f'{split}_{metric}']) for r in history], label=split)
        ax.set(xlabel='Epoch', ylabel=metric.capitalize()); ax.legend(); ax.grid(alpha=.3)
    save(fig, 'training_curves.png')
    fig, ax = plt.subplots(figsize=(7,4))
    for correct in (True, False):
        values = [r['confidence'] for r in analysis['predictions'] if r['correct']==correct]
        ax.hist(values, bins=np.linspace(0,1,21), alpha=.5, label='Correct' if correct else 'Incorrect')
    ax.set(xlabel='Maximum softmax score (uncalibrated)', ylabel='Samples'); ax.legend()
    save(fig, 'confidence.png')
    errors = analysis['misclassified_samples']
    # Interleave confidence, low-SNR and common-pair rankings, without duplicates.
    ranks = [sorted(errors, key=lambda r:-r['confidence']), sorted(errors, key=lambda r:(r['snr_db'],-r['confidence']))]
    pairs = analysis['common_confusion_pairs']
    if pairs:
        pair = pairs[0]
        ranks.append([r for r in ranks[0] if (r['true_label'],r['predicted_label'])==(pair['true_label'],pair['predicted_label'])])
    selected=[]
    for index in range(len(errors)):
        for rank in ranks:
            if index < len(rank) and rank[index] not in selected and len(selected)<limit:
                selected.append(rank[index])
        if len(selected)>=limit: break
    (root/'error_analysis').mkdir(exist_ok=True)
    for r in selected:
        iq = dataset.x[r['test_index']].numpy()
        fig, axes = plt.subplots(2,2,figsize=(11,7))
        for ax, channel in zip(axes[0], (0,1)):
            ax.plot(iq[channel], linewidth=.7); ax.set(xlabel='Sample', ylabel='I' if channel==0 else 'Q')
        axes[1,0].scatter(iq[0], iq[1],s=4,alpha=.4)
        axes[1,0].set(xlabel='I',ylabel='Q',title='All samples, including transitions'); axes[1,0].set_aspect('equal',adjustable='box')
        f,psd_db = waveform_psd(iq[0]+1j*iq[1], nperseg=256)
        axes[1,1].plot(f,psd_db)
        axes[1,1].set(xlabel='Frequency (cycles/sample)',ylabel='PSD (dB / cycles/sample)',title='Received waveform Welch PSD')
        fig.suptitle(f"ID {r['sample_id']} | {r['true_modulation']} -> {r['predicted_modulation']} | {r['snr_db']:g} dB | score {r['confidence']:.3f}")
        save(fig, f"error_analysis/sample_{r['sample_id']}.png")
    return [r['sample_id'] for r in selected]
