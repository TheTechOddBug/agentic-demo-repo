"""
Unit 4 Lab: Gaussian Mixture Model trained with Expectation-Maximization.

Run:  python gmm_em.py

EM is the general recipe for fitting models with hidden structure. Here the
hidden structure is "which Gaussian did each point come from." We generate data
from a known mix of Gaussians, then use EM to recover the parameters we chose.
Recovering them is proof the algorithm works.

EM alternates two steps:
  E-step: given current parameters, estimate the probability each point belongs
          to each Gaussian (the "responsibilities").
  M-step: given those responsibilities, update the parameters.
"""
import numpy as np


def gaussian_pdf(x, mean, var):
    return np.exp(-0.5 * (x - mean) ** 2 / var) / np.sqrt(2 * np.pi * var)


def em_gmm(x, k=2, iters=100, seed=0):
    rng = np.random.default_rng(seed)
    n = len(x)
    # Initialize parameters.
    means = rng.choice(x, k)
    variances = np.full(k, np.var(x))
    weights = np.full(k, 1.0 / k)

    for _ in range(iters):
        # E-step: responsibilities r[i, j] = P(point i came from Gaussian j).
        r = np.array([weights[j] * gaussian_pdf(x, means[j], variances[j])
                      for j in range(k)]).T
        r /= r.sum(axis=1, keepdims=True)

        # M-step: update weights, means, variances from the responsibilities.
        Nk = r.sum(axis=0)
        weights = Nk / n
        means = (r * x[:, None]).sum(axis=0) / Nk
        variances = (r * (x[:, None] - means) ** 2).sum(axis=0) / Nk
        variances = np.maximum(variances, 1e-6)   # guard against collapse

    return weights, means, variances


def main():
    rng = np.random.default_rng(1)
    # True parameters we will try to recover.
    true_means = [0.0, 6.0]
    true_vars = [1.0, 1.5]
    true_weights = [0.4, 0.6]

    n = 2000
    comp = rng.random(n) < true_weights[0]
    x = np.where(comp,
                 rng.normal(true_means[0], np.sqrt(true_vars[0]), n),
                 rng.normal(true_means[1], np.sqrt(true_vars[1]), n))

    weights, means, variances = em_gmm(x, k=2)

    # Sort by mean so the recovered components line up with the true ones.
    order = np.argsort(means)
    print("Recovering the parameters of the mixture from data alone:\n")
    print(f"{'':<12}{'true':>10}{'recovered':>12}")
    for idx, o in enumerate(order):
        print(f"mean {idx}      {true_means[idx]:>10.2f}{means[o]:>12.2f}")
        print(f"variance {idx}  {true_vars[idx]:>10.2f}{variances[o]:>12.2f}")
        print(f"weight {idx}    {true_weights[idx]:>10.2f}{weights[o]:>12.2f}")
    print("\nClose recovery means your EM implementation is correct.")


if __name__ == "__main__":
    main()
