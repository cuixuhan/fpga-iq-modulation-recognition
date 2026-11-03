"""Pure NumPy evaluation metrics, independent of plotting and fixed SNR lists."""
import numpy as np


def overall_accuracy(y, pred) -> dict:
    y, pred = np.asarray(y), np.asarray(pred)
    if y.ndim != 1 or pred.shape != y.shape:
        raise ValueError('labels and predictions must be aligned vectors')
    total, correct = len(y), int((y == pred).sum())
    return dict(correct=correct, total=total, accuracy=correct / total if total else None)


def confusion_matrix(y, pred, class_mapping: dict) -> np.ndarray:
    overall_accuracy(y, pred)
    labels = sorted(class_mapping.values())
    if len(set(labels)) != len(labels):
        raise ValueError('duplicate class IDs')
    positions = {label: i for i, label in enumerate(labels)}
    cm = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for true, predicted in zip(y, pred):
        if true not in positions or predicted not in positions:
            raise ValueError('unknown class ID')
        cm[positions[true], positions[predicted]] += 1
    return cm


def per_class_accuracy(y, pred, class_mapping: dict) -> list:
    y, pred = np.asarray(y), np.asarray(pred)
    confusion_matrix(y, pred, class_mapping)
    return [dict(label=label, modulation=name, **overall_accuracy(y[y == label], pred[y == label]))
            for name, label in sorted(class_mapping.items(), key=lambda item: item[1])]


def accuracy_by_snr(y, pred, snr) -> list:
    y, pred, snr = np.asarray(y), np.asarray(pred), np.asarray(snr, dtype=float)
    overall_accuracy(y, pred)
    if snr.shape != y.shape or not np.isfinite(snr).all():
        raise ValueError('SNR must be a finite aligned vector')
    return [dict(snr_db=float(level), **overall_accuracy(y[snr == level], pred[snr == level]))
            for level in np.unique(snr)]


def accuracy_by_class_and_snr(y, pred, snr, class_mapping: dict) -> list:
    y, pred, snr = np.asarray(y), np.asarray(pred), np.asarray(snr, dtype=float)
    levels = [r['snr_db'] for r in accuracy_by_snr(y, pred, snr)]
    confusion_matrix(y, pred, class_mapping)
    rows = []
    for name, label in sorted(class_mapping.items(), key=lambda item: item[1]):
        for level in levels:
            mask = (y == label) & (snr == level)
            rows.append(dict(label=label, modulation=name, snr_db=level, **overall_accuracy(y[mask], pred[mask])))
    return rows


def analyze_predictions(result: dict, sample_ids, class_mapping: dict) -> dict:
    y, pred, snr, confidence = (np.asarray(result[k]) for k in ('y', 'pred', 'snr', 'confidence'))
    ids = np.asarray(sample_ids)
    cm = confusion_matrix(y, pred, class_mapping)
    if ids.shape != y.shape or len(np.unique(ids)) != len(ids):
        raise ValueError('sample IDs must be unique and aligned')
    if confidence.shape != y.shape or not np.isfinite(confidence).all() or np.any((confidence < 0) | (confidence > 1)):
        raise ValueError('invalid confidence')
    snr_rows = accuracy_by_snr(y, pred, snr)
    names = {label: name for name, label in class_mapping.items()}
    mean = lambda values: float(values.mean()) if len(values) else None
    correct = y == pred
    records = [dict(sample_id=int(ids[i]), test_index=i, true_label=int(y[i]), predicted_label=int(pred[i]),
                    true_modulation=names[y[i]], predicted_modulation=names[pred[i]], snr_db=float(snr[i]),
                    confidence=float(confidence[i]), correct=bool(correct[i])) for i in range(len(y))]
    labels = sorted(names)
    pairs = sorted([dict(true_label=labels[i], predicted_label=labels[j], true_modulation=names[labels[i]],
                         predicted_modulation=names[labels[j]], count=int(cm[i, j]))
                    for i in range(len(labels)) for j in range(len(labels)) if i != j and cm[i, j]],
                   key=lambda r: (-r['count'], r['true_label'], r['predicted_label']))
    return dict(overall=overall_accuracy(y, pred), per_class=per_class_accuracy(y, pred, class_mapping),
                confusion_matrix=cm.tolist(), confusion_matrix_label_order=labels,
                accuracy_by_snr=snr_rows, per_class_accuracy_by_snr=accuracy_by_class_and_snr(y, pred, snr, class_mapping),
                confidence=dict(mean=mean(confidence), correct_mean=mean(confidence[correct]),
                                incorrect_mean=mean(confidence[~correct]),
                                by_snr=[dict(snr_db=r['snr_db'], mean=mean(confidence[snr == r['snr_db']])) for r in snr_rows],
                                interpretation='Maximum softmax score; not a calibrated probability.'),
                common_confusion_pairs=pairs, predictions=records,
                misclassified_samples=[r for r in records if not r['correct']])


def aggregate_seed_runs(runs: list) -> dict:
    """Aggregate only executed, comparable runs; duplicate seeds are rejected."""
    if not runs:
        raise ValueError('no executed runs supplied')
    seeds = [r['seed'] for r in runs]
    if len(set(seeds)) != len(seeds):
        raise ValueError('duplicate seed evaluations are not independent training runs')
    signatures = [r['comparison_config'] for r in runs]
    if any(s != signatures[0] for s in signatures):
        raise ValueError('runs use different dataset or training configurations')
    values = np.asarray([r['test_accuracy'] for r in runs], dtype=float)
    return dict(executed_seeds=seeds, count=len(runs), mean=float(values.mean()),
                std=float(values.std(ddof=0)) if len(runs) > 1 else None,
                std_convention='Population standard deviation (ddof=0); undefined for a single executed seed here.')
