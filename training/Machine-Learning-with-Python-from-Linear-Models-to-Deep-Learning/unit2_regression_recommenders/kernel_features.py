"""
Unit 2 Lab: Nonlinear classification with feature maps.

Run:  python kernel_features.py

A straight line cannot separate points arranged in two concentric circles.
By mapping the data into a higher-dimensional feature space (here, adding the
squared radius), a linear classifier suddenly can. This is the core idea
behind kernels. Saves a before/after plot to kernel_features.png.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.datasets import make_circles
from sklearn.linear_model import LogisticRegression


def add_radius_feature(X):
    """Map (x1, x2) -> (x1, x2, x1^2 + x2^2). The new feature is the squared radius."""
    r2 = (X[:, 0] ** 2 + X[:, 1] ** 2).reshape(-1, 1)
    return np.hstack([X, r2])


def main():
    X, y = make_circles(n_samples=300, factor=0.4, noise=0.08, random_state=0)

    # A linear classifier on the raw 2D features fails.
    raw_acc = LogisticRegression().fit(X, y).score(X, y)

    # The same classifier on the mapped features succeeds.
    X_mapped = add_radius_feature(X)
    mapped_acc = LogisticRegression().fit(X_mapped, y).score(X_mapped, y)

    print(f"Linear classifier on raw 2D features:      {raw_acc:.2%}")
    print(f"Linear classifier after adding r^2 feature: {mapped_acc:.2%}")
    print("The feature map turns an impossible problem into an easy one.")

    plt.figure(figsize=(6, 6))
    plt.scatter(X[:, 0], X[:, 1], c=y, cmap="coolwarm", s=15)
    plt.title("Concentric circles: not linearly separable in 2D")
    plt.savefig("kernel_features.png", dpi=120, bbox_inches="tight")
    print("Saved plot to kernel_features.png")


if __name__ == "__main__":
    main()
