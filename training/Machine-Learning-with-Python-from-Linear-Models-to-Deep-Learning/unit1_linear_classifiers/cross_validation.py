"""
Unit 1 Lab: k-fold cross validation, from scratch.

Run:  python cross_validation.py

Cross validation gives an honest estimate of accuracy by rotating which slice
of data is held out for testing. Here we use it to pick the Pegasos
regularization strength (lambda).
"""
import numpy as np
from svm_pegasos import pegasos_train, predict


def k_fold_indices(n, k, seed=0):
    """Return a list of (train_idx, val_idx) pairs."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, k)
    splits = []
    for i in range(k):
        val = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        splits.append((train, val))
    return splits


def cross_val_score(X, y, lambda_reg, k=5):
    scores = []
    for train_idx, val_idx in k_fold_indices(len(y), k):
        w, b = pegasos_train(X[train_idx], y[train_idx], lambda_reg=lambda_reg, epochs=30)
        acc = (predict(X[val_idx], w, b) == y[val_idx]).mean()
        scores.append(acc)
    return np.mean(scores)


def main():
    rng = np.random.default_rng(3)
    pos = rng.normal(loc=[2, 2], scale=1.2, size=(120, 2))
    neg = rng.normal(loc=[-1, -1], scale=1.2, size=(120, 2))
    X = np.vstack([pos, neg])
    y = np.array([1] * 120 + [-1] * 120)

    print("Searching for the best regularization strength:")
    best_lambda, best_score = None, -1
    for lam in [0.001, 0.01, 0.1, 1.0]:
        score = cross_val_score(X, y, lam)
        print(f"  lambda = {lam:<6}  cross-val accuracy = {score:.2%}")
        if score > best_score:
            best_score, best_lambda = score, lam

    print(f"\nBest lambda: {best_lambda} with cross-val accuracy {best_score:.2%}")


if __name__ == "__main__":
    main()
