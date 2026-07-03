"""
Unit 2 Lab: Linear and Ridge Regression, from scratch, two ways.

Run:  python linear_regression.py

Implements linear regression with (a) the closed-form normal equation and
(b) gradient descent, confirms they agree, then adds ridge (L2) regularization.
Verifies against scikit-learn.
"""
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge


def fit_closed_form(X, y, l2=0.0):
    """Solve (X'X + l2*I) w = X'y directly. Includes a bias column."""
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    n_features = Xb.shape[1]
    reg = l2 * np.eye(n_features)
    reg[-1, -1] = 0.0   # do not regularize the bias
    w = np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y)
    return w[:-1], w[-1]


def fit_gradient_descent(X, y, lr=0.01, epochs=2000, l2=0.0):
    """Same objective, minimized step by step with gradient descent."""
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    n_samples, n_features = Xb.shape
    w = np.zeros(n_features)
    for _ in range(epochs):
        error = Xb @ w - y
        grad = (2 / n_samples) * (Xb.T @ error)
        grad[:-1] += 2 * l2 * w[:-1] / n_samples   # ridge penalty, not on bias
        w -= lr * grad
    return w[:-1], w[-1]


def predict(X, w, b):
    return X @ w + b


def main():
    rng = np.random.default_rng(0)
    X = rng.uniform(-3, 3, size=(200, 1))
    true_w, true_b = 2.5, -1.0
    y = true_w * X[:, 0] + true_b + rng.normal(0, 0.5, size=200)

    w_cf, b_cf = fit_closed_form(X, y)
    w_gd, b_gd = fit_gradient_descent(X, y, lr=0.05, epochs=3000)

    print(f"True parameters:        w = {true_w}, b = {true_b}")
    print(f"Closed form:            w = {w_cf[0]:.3f}, b = {b_cf:.3f}")
    print(f"Gradient descent:       w = {w_gd[0]:.3f}, b = {b_gd:.3f}")

    ref = LinearRegression().fit(X, y)
    print(f"scikit-learn:           w = {ref.coef_[0]:.3f}, b = {ref.intercept_:.3f}")

    # Ridge shrinks weights toward zero as l2 grows.
    print("\nRidge regression, effect of the penalty on the weight:")
    for l2 in [0.0, 1.0, 10.0, 100.0]:
        w_r, _ = fit_closed_form(X, y, l2=l2)
        ref_r = Ridge(alpha=l2).fit(X, y)
        print(f"  l2 = {l2:<6} mine = {w_r[0]:.3f}   scikit-learn = {ref_r.coef_[0]:.3f}")


if __name__ == "__main__":
    main()
