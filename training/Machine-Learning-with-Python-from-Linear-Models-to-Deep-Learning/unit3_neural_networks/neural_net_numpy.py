"""
Unit 3 Lab: A feedforward neural network from scratch in NumPy.

Run:  python neural_net_numpy.py

Implements forward pass, backpropagation by hand, and training with gradient
descent. No deep learning framework. Includes a gradient check that compares
the hand-derived gradients to numerical ones, so you can trust your backprop.
Trains on the 8x8 digits dataset.
"""
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split


def relu(z):
    return np.maximum(0, z)


def relu_deriv(z):
    return (z > 0).astype(float)


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)          # for numerical stability
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def one_hot(y, n_classes):
    out = np.zeros((len(y), n_classes))
    out[np.arange(len(y)), y] = 1
    return out


class NeuralNet:
    """One hidden layer: input -> ReLU hidden -> softmax output."""

    def __init__(self, n_in, n_hidden, n_out, seed=0):
        rng = np.random.default_rng(seed)
        # Small random init scaled by layer size (He initialization).
        self.W1 = rng.normal(0, np.sqrt(2 / n_in), size=(n_in, n_hidden))
        self.b1 = np.zeros(n_hidden)
        self.W2 = rng.normal(0, np.sqrt(2 / n_hidden), size=(n_hidden, n_out))
        self.b2 = np.zeros(n_out)

    def forward(self, X):
        self.z1 = X @ self.W1 + self.b1
        self.a1 = relu(self.z1)
        self.z2 = self.a1 @ self.W2 + self.b2
        self.a2 = softmax(self.z2)
        return self.a2

    def loss(self, probs, Y):
        # Cross-entropy loss.
        n = Y.shape[0]
        return -np.sum(Y * np.log(probs + 1e-9)) / n

    def backward(self, X, Y):
        """Backpropagation. Returns gradients for every parameter."""
        n = X.shape[0]
        dz2 = (self.a2 - Y) / n                     # gradient at output (softmax + cross-entropy)
        dW2 = self.a1.T @ dz2
        db2 = dz2.sum(axis=0)
        da1 = dz2 @ self.W2.T
        dz1 = da1 * relu_deriv(self.z1)            # chain rule through ReLU
        dW1 = X.T @ dz1
        db1 = dz1.sum(axis=0)
        return dW1, db1, dW2, db2

    def step(self, grads, lr):
        dW1, db1, dW2, db2 = grads
        self.W1 -= lr * dW1; self.b1 -= lr * db1
        self.W2 -= lr * dW2; self.b2 -= lr * db2


def gradient_check(net, X, Y, eps=1e-5):
    """Compare the backprop gradient for W1 to a numerical estimate."""
    net.forward(X)
    analytic = net.backward(X, Y)[0]               # dW1
    numeric = np.zeros_like(net.W1)
    for i in range(net.W1.shape[0]):
        for j in range(net.W1.shape[1]):
            orig = net.W1[i, j]
            net.W1[i, j] = orig + eps
            loss_plus = net.loss(net.forward(X), Y)
            net.W1[i, j] = orig - eps
            loss_minus = net.loss(net.forward(X), Y)
            net.W1[i, j] = orig
            numeric[i, j] = (loss_plus - loss_minus) / (2 * eps)
    rel_error = np.abs(analytic - numeric).max() / (np.abs(numeric).max() + 1e-9)
    return rel_error


def main():
    digits = load_digits()
    X, y = digits.data / 16.0, digits.target       # scale pixels to [0, 1]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0)
    Y_train = one_hot(y_train, 10)

    net = NeuralNet(n_in=64, n_hidden=64, n_out=10)

    # First, prove the backprop is correct on a small batch.
    err = gradient_check(net, X_train[:20], Y_train[:20])
    print(f"Gradient check relative error: {err:.2e}  (should be tiny, < 1e-5)")

    # Train with mini-batch gradient descent.
    print("\nTraining:")
    rng = np.random.default_rng(0)
    batch = 64
    for epoch in range(60):
        idx = rng.permutation(len(X_train))
        for start in range(0, len(X_train), batch):
            b = idx[start:start + batch]
            net.forward(X_train[b])
            net.step(net.backward(X_train[b], Y_train[b]), lr=0.5)
        if (epoch + 1) % 15 == 0:
            train_acc = (net.forward(X_train).argmax(1) == y_train).mean()
            test_acc = (net.forward(X_test).argmax(1) == y_test).mean()
            print(f"  epoch {epoch+1:>2}: train {train_acc:.2%}  test {test_acc:.2%}")

    final = (net.forward(X_test).argmax(1) == y_test).mean()
    print(f"\nFinal test accuracy: {final:.2%}")
    print("You built a working neural network, backprop and all, in pure NumPy.")
    print("On this small 8x8 set it ties the linear model. On full 28x28 MNIST and")
    print("harder data the neural net, and especially the CNN next, pulls clearly ahead.")


if __name__ == "__main__":
    main()
