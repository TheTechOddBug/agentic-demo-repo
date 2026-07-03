"""
Unit 5 Lab: Value Iteration.

Run:  python value_iteration.py

When you know how the world works (the rewards and transitions), value
iteration computes the optimal value of every state by repeatedly applying the
Bellman update, then reads off the best action in each state. This is planning
with full knowledge of the environment.
"""
from gridworld import Gridworld, ACTIONS


def value_iteration(env, gamma=0.9, theta=1e-6):
    V = {s: 0.0 for s in env.states()}
    while True:
        delta = 0
        for s in env.states():
            if env.is_terminal(s):
                V[s] = env.reward(s)
                continue
            # Bellman update: value = reward now + discounted best next value.
            best = max(env.reward(s) + gamma * V[env.step(s, a)] for a in ACTIONS)
            delta = max(delta, abs(best - V[s]))
            V[s] = best
        if delta < theta:
            break

    # Derive the optimal policy: the action leading to the best next value.
    policy = {}
    for s in env.states():
        if env.is_terminal(s):
            continue
        policy[s] = max(ACTIONS, key=lambda a: V[env.step(s, a)])
    return V, policy


def main():
    env = Gridworld()
    V, policy = value_iteration(env)

    print("Optimal value of each state:")
    for r in range(env.rows):
        row = ""
        for c in range(env.cols):
            if (r, c) in env.walls:
                row += "   #  "
            else:
                row += f"{V[(r, c)]:>6.2f}"
        print(row)

    print("\nOptimal policy (arrows point the way to the goal G):")
    env.render_policy(policy)


if __name__ == "__main__":
    main()
