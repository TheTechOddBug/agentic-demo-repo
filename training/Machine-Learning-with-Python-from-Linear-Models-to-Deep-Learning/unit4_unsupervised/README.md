# Unit 4: Unsupervised Learning

**Goal:** find structure in data that has no labels. Covers clustering, mixtures, and the EM algorithm.

**Time:** about 2 weeks.

## Train (watch and read)

1. **Clustering** — 6.86x Unit 4 (clustering lecture). Intuition: StatQuest k-means clustering: https://www.youtube.com/@statquest . Reference: ISLP clustering chapter: https://www.statlearning.com/
2. **Mixtures and the EM algorithm** — 6.86x Unit 4 (generative models, mixtures, EM). This is the conceptually hardest idea in the course, so give it time. StatQuest has clear videos on Gaussian mixture models and expectation-maximization.

## Run (the labs, in order)

```bash
python kmeans.py      # k-means from scratch; matches scikit-learn; saves a cluster plot
python gmm_em.py      # Gaussian mixture via EM; recovers the parameters of data you generate
```

## Checkpoint

Your k-means matches scikit-learn, your EM recovers the true parameters of a mixture you generated, and you can explain the two-step logic of EM: estimate the hidden assignments, then update the parameters, and repeat.
