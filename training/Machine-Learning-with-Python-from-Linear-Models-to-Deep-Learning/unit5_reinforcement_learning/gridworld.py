"""
Unit 5: A small Gridworld environment.

Imported by value_iteration.py and q_learning.py. Not usually run directly,
but you can run it to see the layout:  python gridworld.py

The world is a grid. The agent starts top-left and wants to reach the goal
(reward +1). One cell is a pit (reward -1). Every step costs a little to
encourage short paths. '#' cells are walls the agent cannot enter.
"""
import numpy as np

# Layout:  S = start, G = goal (+1), P = pit (-1), # = wall, . = empty
LAYOUT = [
    ["S", ".", ".", "."],
    [".", "#", ".", "P"],
    [".", "#", ".", "."],
    [".", ".", ".", "G"],
]

ACTIONS = ["up", "down", "left", "right"]
MOVES = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
STEP_COST = -0.04


class Gridworld:
    def __init__(self, layout=LAYOUT):
        self.grid = layout
        self.rows = len(layout)
        self.cols = len(layout[0])
        self.walls = {(r, c) for r in range(self.rows) for c in range(self.cols)
                      if layout[r][c] == "#"}
        self.goal = self._find("G")
        self.pit = self._find("P")
        self.start = self._find("S")
        self.terminals = {self.goal, self.pit}

    def _find(self, symbol):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == symbol:
                    return (r, c)
        return None

    def states(self):
        return [(r, c) for r in range(self.rows) for c in range(self.cols)
                if (r, c) not in self.walls]

    def is_terminal(self, s):
        return s in self.terminals

    def reward(self, s):
        if s == self.goal:
            return 1.0
        if s == self.pit:
            return -1.0
        return STEP_COST

    def step(self, s, action):
        """Return the next state after taking an action from state s."""
        dr, dc = MOVES[action]
        nr, nc = s[0] + dr, s[1] + dc
        if 0 <= nr < self.rows and 0 <= nc < self.cols and (nr, nc) not in self.walls:
            return (nr, nc)
        return s   # bumping into a wall or edge keeps you in place

    def render_policy(self, policy):
        arrows = {"up": "^", "down": "v", "left": "<", "right": ">"}
        for r in range(self.rows):
            row = ""
            for c in range(self.cols):
                if (r, c) in self.walls:
                    row += " # "
                elif (r, c) == self.goal:
                    row += " G "
                elif (r, c) == self.pit:
                    row += " P "
                else:
                    row += f" {arrows[policy[(r, c)]]} "
            print(row)


if __name__ == "__main__":
    env = Gridworld()
    print(f"Grid is {env.rows}x{env.cols}. Start {env.start}, goal {env.goal}, pit {env.pit}.")
    for row in env.grid:
        print(" ".join(cell if cell != "." else "." for cell in row))
