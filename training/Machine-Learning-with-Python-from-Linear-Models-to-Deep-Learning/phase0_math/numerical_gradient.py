"""
Phase 0 Lab: NumPy warmup and a numerical gradient checker.

Run:  python numerical_gradient.py

What you build here:
  1. Core linear-algebra ops from scratch, verified against NumPy.
  2. A numerical gradient function you will reuse in Unit 3 to check backprop.

Nothing here uses a machine learning library. This is the foundation.
"""
import numpy as np


# ---- 1. Core operations from scratch -------------------------------------

def my_dot(a, b):
    """Dot product of two 1D vectors, computed with an explicit loop."""
    total = 0.0
    for i in range(len(a)):
        total += a[i] * b[i]
    return total


def my_matmul(A, B):
    """Matrix multiply A (m x n) by B (n x p), computed from scratch."""
    m, n = A.shape
    n2, p = B.shape
    assert n == n2, "inner dimensions must match"
    out = np.zeros((m, p))
    for i in range(m):
        for j in range(p):
            for k in range(n):
                out[i, j] += A[i, k] * B[k, j]
    return out


def l2_norm(v):
    """Euclidean length of a vector, from scratch."""
    return np.sqrt(my_dot(v, v))


def standardize(X):
    """Subtract the mean and divide by the standard deviation, per column."""
    return (X - X.mean(axis=0)) / X.std(axis=0)


# ---- 2. Numerical gradient -----------------------------------------------

def numerical_gradient(f, x, eps=1e-6):
    """
    Estimate the gradient of f at x by nudging each input slightly.
    f takes a 1D numpy array and returns a scalar.
    """
    grad = np.zeros_like(x, dtype=float)
    for i in range(len(x)):
        x_plus = x.copy(); x_plus[i] += eps
        x_minus = x.copy(); x_minus[i] -= eps
        grad[i] = (f(x_plus) - f(x_minus)) / (2 * eps)
    return grad


# ---- Checks ---------------------------------------------------------------

def main():
    rng = np.random.default_rng(0)

    a = rng.random(5)
    b = rng.random(5)
    print("dot product:      mine =", round(my_dot(a, b), 6),
          " numpy =", round(float(np.dot(a, b)), 6))

    A = rng.random((3, 4))
    B = rng.random((4, 2))
    print("matmul matches numpy:", np.allclose(my_matmul(A, B), A @ B))

    v = np.array([3.0, 4.0])
    print("l2 norm of [3,4]: mine =", l2_norm(v), " (should be 5.0)")

    # Gradient of f(x, y) = x^2 + y^2 at (3, 4) should be (6, 8).
    f = lambda p: p[0] ** 2 + p[1] ** 2
    point = np.array([3.0, 4.0])
    print("numerical gradient of x^2+y^2 at (3,4):",
          np.round(numerical_gradient(f, point), 4), " (should be [6, 8])")

    print("\nPhase 0 complete. You now have the tools every later unit builds on.")


if __name__ == "__main__":
    main()
