# Unit 3: Neural Networks

**Goal:** build a neural network and its training algorithm from nothing. This demystifies all of modern deep learning. This is the most important unit in the program.

**Time:** about 2.5 weeks.

## Train (watch and read)

1. **Intuition first** — 3Blue1Brown, Neural Networks (watch before coding, especially the backprop chapters): https://www.3blue1brown.com/topics/neural-networks
2. **Backprop by building it** — Andrej Karpathy, Neural Networks: Zero to Hero: https://karpathy.ai/zero-to-hero.html (repo: https://github.com/karpathy/nn-zero-to-hero). The first lecture builds micrograd, a tiny autograd engine, from scratch. Code along. This is the clearest explanation of backpropagation anywhere and matches this program's from-scratch spirit exactly.
3. **The course's formal treatment** — 6.86x Unit 3 (Lectures 8 to 12). CNN reference: Stanford CS231n notes: https://cs231n.github.io/
4. **Optional structured parallel** — Andrew Ng, Deep Learning Specialization: https://www.coursera.org/specializations/deep-learning

## Run (the labs, in order)

```bash
python neural_net_numpy.py           # feedforward net + backprop BY HAND; includes a gradient check
python neural_net_pytorch.py         # the same network in PyTorch; see what .backward() replaces
python project3_cnn_pytorch.py       # PROJECT: a convolutional network on digit images
```

Requires PyTorch (`pip install torch`), used only in this unit.

## Checkpoint

Your from-scratch NumPy network trains and improves, its gradient check passes (relative error near 1e-8), and you can explain how the gradient flows backward through a hidden layer. You have seen the CNN edge ahead of the flat network on images.

## Project 3: Digit Recognition with Neural Networks

Runs on the built-in 8x8 digits set. The CNN file shows how to move to full 28x28 MNIST via torchvision. After this, the natural next step is Karpathy's "Let's build GPT from scratch," which extends straight into the LLM world (see `nlp_bridge`).
