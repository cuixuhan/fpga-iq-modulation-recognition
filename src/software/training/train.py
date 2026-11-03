"""FP32 optimization, deterministic setup and checkpoint persistence."""
import random
from pathlib import Path
import numpy as np
import torch
from torch import nn
from models.baseline_cnn import BaselineCNN


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.use_deterministic_algorithms(True)


def select_device():
    if torch.cuda.is_available():
        return torch.device('cuda')
    if torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


def train_epoch(model, loader, optimizer, device):
    model.train()
    loss_sum, correct, total = 0., 0, 0
    for x, y, _ in loader:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = nn.functional.cross_entropy(logits, y)
        if not torch.isfinite(loss):
            raise RuntimeError('non-finite training loss')
        loss.backward()
        optimizer.step()
        total += len(y)
        loss_sum += loss.item() * len(y)
        correct += (logits.argmax(1) == y).sum().item()
    return dict(loss=loss_sum / total, accuracy=correct / total, correct=correct, total=total)


def save_checkpoint(path, model, optimizer, epoch, validation_accuracy, config):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(dict(model_state_dict=model.state_dict(), optimizer_state_dict=optimizer.state_dict(),
                    epoch=epoch, validation_accuracy=validation_accuracy, config=config), path)


def load_checkpoint(path, device):
    state = torch.load(path, map_location=device, weights_only=True)
    model = BaselineCNN().to(device)
    model.load_state_dict(state['model_state_dict'])
    model.eval()
    return model, state


def tiny_overfit(dataset, device, seed=42, max_steps=300):
    """Gate uses only 32 seeded train samples; formal model is reset afterwards."""
    from torch.utils.data import Subset, DataLoader
    from training.evaluate import evaluate
    set_seed(seed)
    indices = torch.randperm(len(dataset), generator=torch.Generator().manual_seed(seed))[:32]
    loader = DataLoader(Subset(dataset, indices.tolist()), batch_size=32)
    model = BaselineCNN().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    initial = evaluate(model, loader, device)
    for step in range(1, max_steps + 1):
        train_epoch(model, loader, optimizer, device)
        if step % 10 == 0:
            result = evaluate(model, loader, device)
            print(f'Tiny step {step}: loss={result["loss"]:.4f}, accuracy={result["accuracy"]:.4f}', flush=True)
            if result['accuracy'] >= .95 and result['loss'] < initial['loss'] * .3:
                return dict(passed=True, steps=step, indices=indices.tolist(),
                            initial_loss=initial['loss'], final_loss=result['loss'],
                            initial_accuracy=initial['accuracy'], final_accuracy=result['accuracy'])
    raise RuntimeError('Tiny overfit gate failed; stop before formal training')
