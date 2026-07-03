"""
Unit 3 PROJECT: Digit Recognition with a Convolutional Neural Network.

Run:  python project3_cnn_pytorch.py   (requires: pip install torch)

A small CNN in PyTorch. Convolutions exploit the 2D structure of images
(local patterns, weight sharing), which is why they beat flat networks on
image tasks. Trains on the 8x8 digits dataset reshaped to images.

To use full 28x28 MNIST, see the note at the bottom.
"""
import numpy as np
import torch
import torch.nn as nn
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split


class SmallCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 8, kernel_size=3, padding=1),   # 8 feature maps
            nn.ReLU(),
            nn.Conv2d(8, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),                             # downsample
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(16 * 4 * 4, 64),
            nn.ReLU(),
            nn.Linear(64, 10),
        )

    def forward(self, x):
        return self.head(self.conv(x))


def main():
    digits = load_digits()
    X = (digits.data / 16.0).reshape(-1, 1, 8, 8)   # reshape flat pixels into images
    y = digits.target
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0)

    X_train = torch.tensor(X_train, dtype=torch.float32)
    X_test = torch.tensor(X_test, dtype=torch.float32)
    y_train = torch.tensor(y_train, dtype=torch.long)
    y_test = torch.tensor(y_test, dtype=torch.long)

    model = SmallCNN()
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    print("Training a convolutional network:")
    batch = 64
    for epoch in range(30):
        perm = torch.randperm(len(X_train))
        for start in range(0, len(X_train), batch):
            b = perm[start:start + batch]
            optimizer.zero_grad()
            loss = loss_fn(model(X_train[b]), y_train[b])
            loss.backward()
            optimizer.step()
        if (epoch + 1) % 10 == 0:
            with torch.no_grad():
                acc = (model(X_test).argmax(1) == y_test).float().mean()
            print(f"  epoch {epoch+1:>2}: test accuracy {acc:.2%}")

    with torch.no_grad():
        final = (model(X_test).argmax(1) == y_test).float().mean()
    print(f"\nFinal CNN test accuracy: {final:.2%}")
    print("Convolutions read the 2D shape of a digit, not just a flat list of pixels.")

    print("\n--- To use full 28x28 MNIST ---")
    print("Load MNIST via torchvision.datasets.MNIST, keep the shape as (N, 1, 28, 28),")
    print("and change the Linear layer input to 16 * 7 * 7. The rest is identical.")


if __name__ == "__main__":
    main()
