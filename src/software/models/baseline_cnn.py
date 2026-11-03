"""Fixed Day 3 network; outputs unnormalized class logits."""
from torch import nn


class BaselineCNN(nn.Module):
    def __init__(self):
        super().__init__()
        layers = []
        for index, (cin, cout, kernel) in enumerate(((2, 32, 7), (32, 64, 5), (64, 128, 3))):
            layers.extend([nn.Conv1d(cin, cout, kernel, padding=kernel // 2),
                           nn.BatchNorm1d(cout), nn.ReLU()])
            if index < 2:
                layers.append(nn.MaxPool1d(2))
        self.features = nn.Sequential(*layers, nn.AdaptiveAvgPool1d(1))
        self.classifier = nn.Linear(128, 5)

    def forward(self, x):
        return self.classifier(self.features(x).flatten(1))


def parameter_count(model):
    return {"total": sum(p.numel() for p in model.parameters()),
            "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad)}
