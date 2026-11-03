"""Run Day 3 gates, 30 epochs, reload best validation checkpoint, then test."""
from pathlib import Path
import sys
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import json
import platform
import time
import torch
from models.baseline_cnn import BaselineCNN, parameter_count
from training.data import load_splits, make_loaders
from training.train import set_seed, select_device, train_epoch, save_checkpoint, load_checkpoint, tiny_overfit
from training.evaluate import evaluate
from training.metrics import generate_artifacts, write_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--dataset', type=Path, default=Path('data/modulation_dataset.npz'))
    parser.add_argument('--output', type=Path, default=Path('.'))
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('--threads must be positive')
    torch.set_num_threads(args.threads)
    device = select_device()
    config = dict(seed=42, batch_size=64, epochs=30, optimizer='Adam', learning_rate=.001,
                  loss='CrossEntropyLoss', dtype='float32', device=str(device), threads=args.threads,
                  input_shape=[2, 1024], classes=5)
    if args.config:
        saved = json.loads(args.config.read_text(encoding='utf-8'))
        for key in ('seed', 'batch_size', 'epochs', 'optimizer', 'learning_rate', 'loss', 'dtype', 'input_shape', 'classes'):
            config[key] = saved[key]
        args.dataset = Path(saved['dataset'])
        if hashlib.sha256(args.dataset.read_bytes()).hexdigest() != saved['dataset_sha256']:
            raise ValueError('Frozen dataset hash mismatch')
        if config['optimizer'] != 'Adam' or config['loss'] != 'CrossEntropyLoss' or config['dtype'] != 'float32' or config['input_shape'] != [2, 1024] or config['classes'] != 5:
            raise ValueError('Unsupported baseline configuration')
    if args.seed is not None:
        config['seed'] = args.seed
    if config['epochs'] < 1 or config['batch_size'] < 1 or config['learning_rate'] <= 0:
        raise ValueError('Training configuration must be positive')
    if (args.output / 'checkpoints/best_model.pt').exists() or (args.output / 'results/training/history.csv').exists():
        raise FileExistsError('Choose a fresh --output to preserve existing training artifacts')
    set_seed(config['seed'])
    splits, metadata = load_splits(args.dataset)
    dataset_hash = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    print('Day 3 FP32 Baseline\n' + json.dumps(config, indent=2), flush=True)
    model = BaselineCNN().to(device)
    counts = parameter_count(model)
    print(model, flush=True)
    print(f'Total parameters: {counts["total"]}; Trainable parameters: {counts["trainable"]}', flush=True)
    started = time.time()
    tiny = tiny_overfit(splits['train'], device, config['seed'])
    training_dir = args.output / 'results/training'
    training_dir.mkdir(parents=True, exist_ok=True)
    (training_dir / 'tiny_overfit.json').write_text(json.dumps(tiny, indent=2), encoding='utf-8')
    # Smoke uses train/validation only; never consumes the test loader.
    set_seed(config['seed'])
    loaders = make_loaders(splits, config['batch_size'], config['seed'])
    model = BaselineCNN().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    smoke_train = train_epoch(model, loaders['train'], optimizer, device)
    smoke_val = evaluate(model, loaders['val'], device)
    smoke_path = args.output / 'checkpoints/smoke_model.pt'
    save_checkpoint(smoke_path, model, optimizer, 1, smoke_val['accuracy'], config)
    restored, _ = load_checkpoint(smoke_path, device)
    reloaded = evaluate(restored, loaders['val'], device)
    assert smoke_val['accuracy'] == reloaded['accuracy']
    smoke = dict(train=smoke_train, validation={k: smoke_val[k] for k in ('loss', 'accuracy', 'total')},
                 checkpoint_reload_passed=True)
    print('Smoke passed: ' + json.dumps(smoke), flush=True)
    # Fresh weights, optimizer and shuffle generator for the formal baseline.
    set_seed(config['seed'])
    loaders = make_loaders(splits, config['batch_size'], config['seed'])
    model = BaselineCNN().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    history, best_accuracy = [], -1.
    checkpoint = args.output / 'checkpoints/best_model.pt'
    for epoch in range(1, config['epochs'] + 1):
        train = train_epoch(model, loaders['train'], optimizer, device)
        val = evaluate(model, loaders['val'], device)
        row = dict(epoch=epoch, train_loss=train['loss'], train_accuracy=train['accuracy'],
                   val_loss=val['loss'], val_accuracy=val['accuracy'])
        history.append(row)
        write_csv(training_dir / 'history.csv', history)
        if val['accuracy'] > best_accuracy:
            best_accuracy = val['accuracy']
            save_checkpoint(checkpoint, model, optimizer, epoch, best_accuracy, config)
        print(f'Epoch {epoch}/{config["epochs"]}: ' + json.dumps(row), flush=True)
    model, state = load_checkpoint(checkpoint, device)
    test = evaluate(model, loaders['test'], device)
    assert test['total'] == len(splits['test'])
    assert hashlib.sha256(args.dataset.read_bytes()).hexdigest() == dataset_hash
    summary = dict(config=config, parameters=counts, dataset_metadata=metadata,
                   dataset_sha256=dataset_hash, samples={s: len(ds) for s, ds in splits.items()},
                   environment=dict(python=platform.python_version(), torch=str(torch.__version__), platform=platform.platform()),
                   tiny_overfit=tiny, smoke=smoke, best_epoch=state['epoch'],
                   best_validation_accuracy=state['validation_accuracy'],
                   best_train_accuracy=max(h['train_accuracy'] for h in history),
                   final_train_metrics=history[-1], best_epoch_metrics=history[state['epoch'] - 1],
                   checkpoint=str(checkpoint), elapsed_seconds=time.time() - started,
                   possible_overfitting=max(h['train_accuracy'] for h in history) - best_accuracy > .10)
    summary = generate_artifacts(args.output / 'results', history, test, summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
