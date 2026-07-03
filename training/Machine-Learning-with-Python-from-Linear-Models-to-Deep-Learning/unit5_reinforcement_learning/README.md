# Unit 5: Reinforcement Learning

**Goal:** train an agent that learns to make sequences of decisions by trial and error to maximize reward. This is the foundation under decision-making agents.

**Time:** about 2 weeks.

## Train (watch and read)

1. **MDPs and value iteration** — 6.86x Unit 5 (first RL lecture). Fuller hands-on treatment: the free Hugging Face Deep Reinforcement Learning Course: https://huggingface.co/learn/deep-rl-course . David Silver's classic "Introduction to Reinforcement Learning" lectures are also excellent (searchable on YouTube).
2. **Q-learning** — 6.86x Unit 5 (second RL lecture). The definitive free reference is Sutton and Barto, Reinforcement Learning: An Introduction: http://incompleteideas.net/book/the-book.html

## Run (the labs, in order)

```bash
python gridworld.py          # (optional) shows the environment layout
python value_iteration.py    # PLANNING: solves the world when the rules are known
python q_learning.py         # PROJECT: LEARNS the world from experience, no prior knowledge
```

`value_iteration.py` and `q_learning.py` both import `gridworld.py`, so keep the three files together.

## Checkpoint

Your value iteration finds the optimal path, your Q-learning agent learns a good policy through trial and error with no prior knowledge of the world, and you can articulate the exploration-versus-exploitation tradeoff.

## Project 3b: Reinforcement Learning agent

The Q-learning agent here learns the optimal gridworld policy from scratch. To match the actual 6.86x capstone, extend the same Q-learning code to a simple text-based game (a small world navigated by text commands): swap the gridworld for your text environment, keep the epsilon-greedy loop and the Q-update identical.
