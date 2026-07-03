# Machine Learning Training Program

A complete, runnable, self-driven program that mirrors MIT's 6.86x (Machine Learning with Python: from Linear Models to Deep Learning). Every algorithm is implemented from scratch in code you can run, then checked against a trusted library. Each phase pairs training links (what to watch and read) with working labs (what to run).

This is built to be followed start to finish. Work through the phases in order.

## How to use this program

For each phase:
1. **Train** on the linked resources listed in that phase's `README.md` (video courses, readings). This is where you learn the idea.
2. **Run the labs** in that folder with `python filename.py`. Read the code, change things, break it, fix it. This is where it sticks.
3. **Hit the checkpoint** described in the phase README before moving on.

The golden rule, straight from 6.86x: **build it yourself before you import it.** Every lab implements the algorithm by hand first, then compares to scikit-learn or PyTorch so you can trust your version.

## Setup

```bash
# From inside this folder:
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Everything runs on CPU. PyTorch (used only in Unit 3) is the one large install; the rest is quick. Every script is self-contained and either generates its own data or uses small built-in datasets, so there are no downloads to run the labs as shipped. Notes inside the files show how to swap in the full-size datasets (IMDB reviews, 28x28 MNIST) when you want to scale up.

## The program at a glance

| Phase | Folder | What you build | Key training |
|-------|--------|----------------|--------------|
| 0. Math | `phase0_math` | Numerical gradient, NumPy ops | 3Blue1Brown |
| 1. Linear classifiers | `unit1_linear_classifiers` | Perceptron, SVM, review analyzer | 6.86x Unit 1, Andrew Ng C1 |
| 2. Regression, recommenders | `unit2_regression_recommenders` | Regression, kernels, recommender | 6.86x Unit 2, StatQuest |
| 3. Neural networks | `unit3_neural_networks` | Backprop from scratch, CNN | Karpathy, 3Blue1Brown |
| Interlude. Theory | `interlude_generalization` | (reading only) | Caltech Learning From Data |
| 4. Unsupervised | `unit4_unsupervised` | k-means, EM / mixtures | 6.86x Unit 4, StatQuest |
| 5. Reinforcement learning | `unit5_reinforcement_learning` | Value iteration, Q-learning | Hugging Face Deep RL |
| NLP bridge | `nlp_bridge` | (reading + optional build) | Jay Alammar, Karpathy GPT |

## Suggested pace

About 15 weeks of content plus the math ramp, so roughly four to five months at an evenings-and-weekends pace. The point is not speed. The point is that by the end you have a repository full of machine learning algorithms you built and understand.

## The three capstone projects

These are the heart of the program, matching the three real 6.86x projects:
1. **Automatic Review Analyzer** (`unit1_linear_classifiers/project1_review_analyzer.py`)
2. **Digit Recognition with Neural Networks** (`unit3_neural_networks/project3_cnn_pytorch.py`)
3. **Reinforcement Learning agent** (`unit5_reinforcement_learning/q_learning.py`)

## Recommended run order

```
phase0_math/numerical_gradient.py

unit1_linear_classifiers/perceptron.py
unit1_linear_classifiers/svm_pegasos.py
unit1_linear_classifiers/cross_validation.py
unit1_linear_classifiers/project1_review_analyzer.py

unit2_regression_recommenders/linear_regression.py
unit2_regression_recommenders/kernel_features.py
unit2_regression_recommenders/collaborative_filtering.py
unit2_regression_recommenders/project2_mnist_linear.py

unit3_neural_networks/neural_net_numpy.py
unit3_neural_networks/neural_net_pytorch.py
unit3_neural_networks/project3_cnn_pytorch.py

unit4_unsupervised/kmeans.py
unit4_unsupervised/gmm_em.py

unit5_reinforcement_learning/value_iteration.py
unit5_reinforcement_learning/q_learning.py
```

Read the `README.md` in each folder first. It tells you what to learn before you run the code, and what the checkpoint is.
