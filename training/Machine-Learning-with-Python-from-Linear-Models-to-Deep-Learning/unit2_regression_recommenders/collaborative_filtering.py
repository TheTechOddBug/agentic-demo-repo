"""
Unit 2 Lab: Collaborative filtering with matrix factorization.

Run:  python collaborative_filtering.py

Learns hidden user and item vectors by gradient descent so that their dot
products reproduce known ratings, then predicts the ratings we held out. This
is the math behind "people who liked this also liked" systems.
"""
import numpy as np


def matrix_factorization(R, mask, n_factors=3, lr=0.01, reg=0.05, epochs=2000):
    """
    R:    (n_users, n_items) ratings matrix.
    mask: (n_users, n_items) 1 where a rating is known, 0 where unknown.
    Returns user matrix U and item matrix V so that U @ V.T approximates R.
    """
    rng = np.random.default_rng(0)
    n_users, n_items = R.shape
    U = rng.normal(0, 0.1, size=(n_users, n_factors))
    V = rng.normal(0, 0.1, size=(n_items, n_factors))

    for _ in range(epochs):
        pred = U @ V.T
        err = mask * (R - pred)                    # only count known entries
        U += lr * (err @ V - reg * U)
        V += lr * (err.T @ U - reg * V)
    return U, V


def main():
    # 8 users, 6 items with two clear taste groups: users who love items 0-2
    # and users who love items 3-5. 0 means the rating is unknown.
    R = np.array([
        [5, 5, 4, 1, 1, 2],
        [4, 5, 5, 2, 1, 1],
        [5, 4, 5, 1, 2, 1],
        [4, 5, 4, 1, 1, 2],
        [1, 2, 1, 5, 4, 5],
        [2, 1, 1, 4, 5, 5],
        [1, 1, 2, 5, 5, 4],
        [1, 2, 1, 4, 4, 5],
    ], dtype=float)
    mask = (R > 0).astype(float)

    # Hold out a few known ratings to test prediction quality.
    test_cells = [(0, 0), (4, 4), (7, 5)]
    train_mask = mask.copy()
    truth = {}
    for (u, i) in test_cells:
        truth[(u, i)] = R[u, i]
        train_mask[u, i] = 0

    U, V = matrix_factorization(R, train_mask, n_factors=2, lr=0.02, reg=0.02, epochs=5000)
    pred = U @ V.T

    print("Predicting held-out ratings:")
    for (u, i), actual in truth.items():
        print(f"  user {u}, item {i}:  predicted {pred[u, i]:.2f}   actual {actual:.0f}")
    errors = [abs(pred[u, i] - truth[(u, i)]) for (u, i) in truth]
    print(f"\nMean absolute error on held-out ratings: {np.mean(errors):.2f}")
    print("Low error means the learned user/item vectors captured real taste patterns.")


if __name__ == "__main__":
    main()
