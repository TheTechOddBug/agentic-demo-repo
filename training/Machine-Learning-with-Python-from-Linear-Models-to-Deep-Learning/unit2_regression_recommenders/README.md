# Unit 2: Nonlinear Classification, Linear Regression, Collaborative Filtering

**Goal:** move from predicting categories to predicting numbers, from straight boundaries to curved ones, and learn the math behind recommendation engines.

**Time:** about 2 weeks.

## Train (watch and read)

1. **Linear regression** — 6.86x Unit 2 (Lecture 5). Intuition: StatQuest Linear Regression and Regularization: https://www.youtube.com/@statquest . Reference: ISLP regression chapters: https://www.statlearning.com/
2. **Nonlinear classification and kernels** — 6.86x Unit 2 (Lecture 6). StatQuest kernel trick video.
3. **Recommender systems** — 6.86x Unit 2 (Lecture 7). Andrew Ng's Specialization also covers this clearly: https://www.coursera.org/specializations/machine-learning-introduction

## Run (the labs, in order)

```bash
python linear_regression.py          # closed form AND gradient descent, plus ridge; vs scikit-learn
python kernel_features.py            # a feature map makes non-separable circles separable; saves a plot
python collaborative_filtering.py    # matrix-factorization recommender; predicts held-out ratings
python project2_mnist_linear.py      # PROJECT: digit recognition with linear methods
```

## Checkpoint

Your from-scratch regression matches scikit-learn, your recommender beats guessing the average rating, and you have seen linear methods plateau on digits (which is what motivates neural networks next).

## Project 2: Digit Recognition (linear methods)

Uses the built-in 8x8 digits dataset so it runs instantly. The file shows how to swap in full 28x28 MNIST via `fetch_openml`.
