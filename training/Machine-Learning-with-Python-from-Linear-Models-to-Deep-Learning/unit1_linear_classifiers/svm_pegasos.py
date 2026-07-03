"""
Unit 1 Lab: Linear Support Vector Machine trained with Pegasos.

Run:  python svm_pegasos.py

Pegasos minimizes hinge loss plus L2 regularization using stochastic gradient
descent. This is the algorithm 6.86x has you implement. Compares your accuracy
to scikit-learn's LinearSVC on the same data.
"""
import numpy as np
from sklearn.svm import LinearSVC


def pegasos_train(X, y, lambda_reg=0.01, epochs=50, seed=0):
    """
    X: (n_samples, n_features), y in {-1, +1}.
    Returns weights w and bias b.

    We append a constant 1 feature so the bias is learned as a regularized
    weight. Without this, the bias can grow unbounded and swamp the real
    features. Regularizing it keeps everything balanced.
    """
    rng = np.random.default_rng(seed)
    n_samples = X.shape[0]
    X_aug = np.hstack([X, np.ones((n_samples, 1))])   # last column is the bias feature
    w = np.zeros(X_aug.shape[1])
    t = 0
    for _ in range(epochs):
        for i in rng.permutation(n_samples):
            t += 1
            eta = 1.0 / (lambda_reg * t)              # decaying step size
            if y[i] * np.dot(w, X_aug[i]) < 1:        # inside the margin
                w = (1 - eta * lambda_reg) * w + eta * y[i] * X_aug[i]
            else:                                      # outside the margin, only shrink
                w = (1 - eta * lambda_reg) * w
    return w[:-1], w[-1]   # split back into feature weights and bias


def predict(X, w, b):
    return np.sign(X @ w + b)


def main():
    rng = np.random.default_rng(2)
    pos = rng.normal(loc=[2, 2], scale=1.0, size=(100, 2))
    neg = rng.normal(loc=[-1, -1], scale=1.0, size=(100, 2))
    X = np.vstack([pos, neg])
    y = np.array([1] * 100 + [-1] * 100)

    w, b = pegasos_train(X, y, lambda_reg=0.01, epochs=50)
    my_acc = (predict(X, w, b) == y).mean()

    ref = LinearSVC(C=1.0, max_iter=5000).fit(X, y)
    ref_acc = ref.score(X, y)

    print(f"My Pegasos SVM accuracy:   {my_acc:.2%}")
    print(f"scikit-learn LinearSVC:    {ref_acc:.2%}")
    print("If these are close, your from-scratch SVM is working correctly.")


if __name__ == "__main__":
    main()
