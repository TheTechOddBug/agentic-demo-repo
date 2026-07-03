# Phase 0: Math Foundations

**Goal:** make the math notation feel natural. You think in code already, so this is about comfort, not proofs. Do not skip it. Every later algorithm is this math turned into code.

**Time:** 1 to 3 weeks depending on how rusty you are.

## Train (watch and read)

1. **Linear algebra** — 3Blue1Brown, Essence of Linear Algebra: https://www.3blue1brown.com/topics/linear-algebra
   Priority: vectors, linear combinations and span, linear transformations and matrices, matrix multiplication, dot products.
2. **Calculus and gradients** — 3Blue1Brown, Essence of Calculus: https://www.3blue1brown.com/topics/calculus
   Priority: derivatives, the chain rule, partial derivatives. The chain rule IS backpropagation, so this pays off in Unit 3.
3. **Probability** — Khan Academy, Statistics and Probability: https://www.khanacademy.org/math/statistics-probability
   Priority: distributions, expectation, conditional probability, Bayes' rule.
4. **NumPy** — official Absolute Beginners guide: https://numpy.org/doc/stable/user/absolute_beginners.html

## Run (the lab)

```bash
python numerical_gradient.py
```

Builds core linear-algebra operations from scratch (verified against NumPy) and a numerical gradient checker you will reuse in Unit 3 to verify your backpropagation.

## Checkpoint

You can compute a partial derivative by hand for a two-variable function, you understand what a gradient represents, and you can rewrite a Python loop of elementwise math as a single vectorized NumPy expression.
