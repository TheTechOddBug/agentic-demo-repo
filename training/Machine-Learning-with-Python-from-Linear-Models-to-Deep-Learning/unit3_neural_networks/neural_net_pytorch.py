"""
Unit 3 Lab: The same neural network, rebuilt in PyTorch.

Run:  python neural_net_pytorch.py   (requires: pip install torch)

This is the exact same one-hidden-layer network you built by hand in
neural_net_numpy.py, now in PyTorch. Compare how little code it takes once the
framework handles the backprop you wrote yourself. That contrast is the lesson.
"""
import numpy as np
import torch
import torch.nn as nn
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split


def main():
    digits = load_digits()
    X, y = digits.data / 16.0, digits.target
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0)

    X_train = torch.tensor(X_train, dtype=torch.float32)
    X_test = torch.tensor(X_test, dtype=torch.float32)
    y_train = torch.tensor(y_train, dtype=torch.long)
    y_test = torch.tensor(y_test, dtype=torch.long)

    # The whole network. Compare this to the NumPy version's forward+backward.
    model = nn.Sequential(
        nn.Linear(64, 64),
        nn.ReLU(),
        nn.Linear(64, 10),
    )
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    print("Training:")
    for epoch in range(60):
        optimizer.zero_grad()
        logits = model(X_train)
        loss = loss_fn(logits, y_train)
        loss.backward()          # PyTorch does the backprop you wrote by hand
        optimizer.step()
        if (epoch + 1) % 15 == 0:
            with torch.no_grad():
                test_acc = (model(X_test).argmax(1) == y_test).float().mean()
            print(f"  epoch {epoch+1:>2}: loss {loss.item():.3f}  test {test_acc:.2%}")

    with torch.no_grad():
        final = (model(X_test).argmax(1) == y_test).float().mean()
    print(f"\nFinal test accuracy: {final:.2%}")
    print("Same network, a fraction of the code. Now you know what .backward() does.")


if __name__ == "__main__":
    main()
