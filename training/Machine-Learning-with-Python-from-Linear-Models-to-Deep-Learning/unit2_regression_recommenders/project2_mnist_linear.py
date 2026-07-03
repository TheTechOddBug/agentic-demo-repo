"""
Unit 2 PROJECT: Digit Recognition with linear methods.

Run:  python project2_mnist_linear.py

Classifies handwritten digits using linear models. Uses the built-in 8x8
digits dataset (loads instantly, no download). Shows that plain linear methods
do well but hit a ceiling, which motivates neural networks in Unit 3.

To use full 28x28 MNIST instead, see the note at the bottom.
"""
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline


def main():
    digits = load_digits()
    X, y = digits.data, digits.target
    print(f"Dataset: {X.shape[0]} images, each {X.shape[1]} pixels (8x8), 10 classes")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0)

    # Linear classifier (multinomial logistic regression) on raw pixels.
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    clf.fit(X_train, y_train)
    acc = clf.score(X_test, y_test)
    print(f"\nLinear classifier accuracy on raw pixels: {acc:.2%}")

    # Add simple engineered features (squared pixels) to give the linear model
    # a bit of nonlinearity. This is the feature-map idea from kernel_features.py.
    def add_squares(A):
        return np.hstack([A, A ** 2])
    clf2 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    clf2.fit(add_squares(X_train), y_train)
    acc2 = clf2.score(add_squares(X_test), y_test)
    print(f"Linear classifier with squared-pixel features: {acc2:.2%}")

    print("\nLinear methods get you far, but they plateau here.")
    print("In Unit 3 a neural network will push past this ceiling.")

    print("\n--- To use full 28x28 MNIST ---")
    print("Replace load_digits() with:")
    print("  from sklearn.datasets import fetch_openml")
    print("  mnist = fetch_openml('mnist_784', version=1, as_frame=False)")
    print("  X, y = mnist.data, mnist.target.astype(int)")
    print("Everything else stays the same (it will just take longer to train).")


if __name__ == "__main__":
    main()
