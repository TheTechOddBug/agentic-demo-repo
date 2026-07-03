"""
Unit 5 PROJECT: Q-learning.

Run:  python q_learning.py

The difference from value iteration: the agent does NOT know the rewards or
transitions in advance. It learns purely by trying actions, seeing what
happens, and updating its estimate of each action's value (the Q-value). This
is real reinforcement learning: learning to control by trial and error.

It balances exploration (trying random actions to discover the world) against
exploitation (using what it has learned). We show its learned policy matches
the optimal one from value iteration.
"""
import numpy as np
from gridworld import Gridworld, ACTIONS
from value_iteration import value_iteration


def q_learning(env, episodes=12000, gamma=0.9, alpha=0.1,
               epsilon=0.3, seed=0):
    rng = np.random.default_rng(seed)
    # Q[state][action] estimate, starts at zero (the agent knows nothing).
    Q = {s: {a: 0.0 for a in ACTIONS} for s in env.states()}

    for _ in range(episodes):
        s = env.start
        for _ in range(100):                       # cap steps per episode
            if env.is_terminal(s):
                break
            # Epsilon-greedy: explore sometimes, exploit otherwise.
            if rng.random() < epsilon:
                a = rng.choice(ACTIONS)
            else:
                a = max(ACTIONS, key=lambda act: Q[s][act])

            s_next = env.step(s, a)
            r = env.reward(s_next)

            # Q-learning update rule.
            best_next = max(Q[s_next].values()) if not env.is_terminal(s_next) else 0.0
            Q[s][a] += alpha * (r + gamma * best_next - Q[s][a])
            s = s_next

    policy = {s: max(ACTIONS, key=lambda a: Q[s][a])
              for s in env.states() if not env.is_terminal(s)}
    return Q, policy


def main():
    env = Gridworld()

    print("Learning the world from scratch, by trial and error...\n")
    _, learned_policy = q_learning(env)

    print("Policy learned by Q-learning (no prior knowledge of the world):")
    env.render_policy(learned_policy)

    # Compare to the optimal policy from value iteration (which had full knowledge).
    _, optimal_policy = value_iteration(env)
    matches = sum(learned_policy[s] == optimal_policy[s] for s in learned_policy)
    total = len(learned_policy)
    print(f"\nAgreement with the optimal policy: {matches}/{total} states")
    if matches == total:
        print("The agent learned the optimal strategy purely from experience.")
    else:
        print("Very close. Any differences are usually equally-good alternate routes.")


if __name__ == "__main__":
    main()
