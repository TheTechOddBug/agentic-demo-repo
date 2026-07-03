"""
Unit 1 Lab: The Perceptron algorithm, from scratch.

Run:  python perceptron.py

Builds a linear classifier that learns a decision boundary by correcting its
mistakes one point at a time. Trains on 2D toy data and saves a plot of the
learned boundary to perceptron_boundary.png.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")  # save plots to file instead of opening a window
import matplotlib.pyplot as plt


def perceptron_train(X, y, epochs=20):
    """
    X: (n_samples, n_features), y: labels in {-1, +1}.
    Returns weight vector w and bias b.
    """
    n_samples, n_features = X.shape
    w = np.zeros(n_features)
    b = 0.0
    for _ in range(epochs):
        errors = 0
        for i in range(n_samples):
            if y[i] * (np.dot(w, X[i]) + b) <= 0:   # misclassified
                w += y[i] * X[i]                     # the update rule
                b += y[i]
                errors += 1
        if errors == 0:
            break   # data is separated, stop early
    return w, b


def predict(X, w, b):
    return np.sign(X @ w + b)


def main():
    rng = np.random.default_rng(1)
    # Two clearly separable clusters.
    class_pos = rng.normal(loc=[2, 2], scale=0.6, size=(50, 2))
    class_neg = rng.normal(loc=[-2, -2], scale=0.6, size=(50, 2))
    X = np.vstack([class_pos, class_neg])
    y = np.array([1] * 50 + [-1] * 50)

    w, b = perceptron_train(X, y)
    acc = (predict(X, w, b) == y).mean()
    print(f"Learned weights: {np.round(w, 3)}, bias: {round(b, 3)}")
    print(f"Training accuracy: {acc:.2%}")

    # Plot the points and the decision boundary line  w . x + b = 0
    plt.figure(figsize=(6, 6))
    plt.scatter(class_pos[:, 0], class_pos[:, 1], c="tab:blue", label="+1")
    plt.scatter(class_neg[:, 0], class_neg[:, 1], c="tab:red", label="-1")
    xs = np.linspace(X[:, 0].min(), X[:, 0].max(), 100)
    if abs(w[1]) > 1e-9:
        ys = -(w[0] * xs + b) / w[1]
        plt.plot(xs, ys, "k--", label="decision boundary")
    plt.legend(); plt.title("Perceptron decision boundary")
    plt.savefig("perceptron_boundary.png", dpi=120, bbox_inches="tight")
    print("Saved plot to perceptron_boundary.png")


if __name__ == "__main__":
    main()
