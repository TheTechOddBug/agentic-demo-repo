# Unit 1: Linear Classifiers and Generalizations

**Goal:** understand how a machine draws a decision boundary, measures being wrong, and avoids memorizing the training data. Deliver the first capstone project.

**Time:** about 2 weeks.

## Train (watch and read)

1. **Intro and linear classifiers** — Audit 6.86x Unit 1 (Lectures 1 and 2): https://www.edx.org/learn/machine-learning/massachusetts-institute-of-technology-machine-learning-with-python-from-linear-models-to-deep-learning
   Accessible parallel: Andrew Ng's Machine Learning Specialization, Course 1: https://www.coursera.org/learn/machine-learning
2. **Hinge loss, margins, regularization** — 6.86x Unit 1 (Lectures 3 and 4). Intuition: StatQuest Support Vector Machines: https://www.youtube.com/@statquest
3. **Generalization and cross validation** — free textbook, An Introduction to Statistical Learning with Python (classification chapter): https://www.statlearning.com/

## Run (the labs, in order)

```bash
python perceptron.py                  # learns a boundary by fixing mistakes; saves a plot
python svm_pegasos.py                 # linear SVM via Pegasos; compares to scikit-learn
python cross_validation.py            # k-fold cross validation to pick regularization
python project1_review_analyzer.py    # PROJECT: sentiment classifier on reviews
```

## Checkpoint

Your from-scratch perceptron and SVM separate the toy data, your SVM accuracy is close to scikit-learn's, and your review analyzer classifies held-out reviews correctly. You can explain in your own words what regularization trades off.

## Project 1: Automatic Review Analyzer

Ships with a small built-in dataset so it runs instantly. The file shows how to point it at the full Stanford Large Movie Review dataset (https://ai.stanford.edu/~amaas/data/sentiment/) when you want the real thing.
