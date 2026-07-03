"""
Unit 4 Lab: k-means clustering, from scratch.

Run:  python kmeans.py

Finds clusters in unlabeled data by alternating two steps: assign each point to
the nearest center, then move each center to the mean of its points. Verifies
against scikit-learn and saves a plot to kmeans_clusters.png.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.datasets import make_blobs
from sklearn.metrics import adjusted_rand_score


def kmeans(X, k, iters=100, seed=0):
    rng = np.random.default_rng(seed)
    centers = X[rng.choice(len(X), k, replace=False)]   # random initial centers
    for _ in range(iters):
        # Assign: nearest center for each point.
        dists = np.linalg.norm(X[:, None, :] - centers[None, :, :], axis=2)
        labels = dists.argmin(axis=1)
        # Update: move each center to the mean of its assigned points.
        new_centers = np.array([X[labels == j].mean(axis=0)
                                if np.any(labels == j) else centers[j]
                                for j in range(k)])
        if np.allclose(new_centers, centers):
            break        # converged
        centers = new_centers
    return labels, centers


def main():
    X, true_labels = make_blobs(n_samples=400, centers=3, cluster_std=0.8,
                                random_state=0)
    labels, centers = kmeans(X, k=3)

    # Compare my clustering to scikit-learn's (label numbers may differ, so we
    # use adjusted Rand score, which ignores label naming).
    from sklearn.cluster import KMeans
    sk_labels = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(X)
    agreement = adjusted_rand_score(labels, sk_labels)
    recovery = adjusted_rand_score(true_labels, labels)

    print(f"Agreement with scikit-learn (1.0 = identical): {agreement:.3f}")
    print(f"Recovery of the true clusters (1.0 = perfect):  {recovery:.3f}")

    plt.figure(figsize=(6, 6))
    plt.scatter(X[:, 0], X[:, 1], c=labels, cmap="viridis", s=12)
    plt.scatter(centers[:, 0], centers[:, 1], c="red", marker="X", s=200,
                label="centers")
    plt.legend(); plt.title("k-means clusters (from scratch)")
    plt.savefig("kmeans_clusters.png", dpi=120, bbox_inches="tight")
    print("Saved plot to kmeans_clusters.png")


if __name__ == "__main__":
    main()
