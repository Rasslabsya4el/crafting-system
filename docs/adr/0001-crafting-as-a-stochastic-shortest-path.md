# Crafting is a stochastic shortest path over a compressed item state

The planner models crafting as a stochastic shortest path problem (an MDP that minimises the expected cost of reaching the target) and solves it backwards over a compressed item state; routes are never enumerated as chains. Only primitives are coded, one per kind of game action; crafting methods such as essence spam or fracture-then-reforge are never coded, they emerge from the solver, so a cheaper method nobody wrote down can still be found. "Spam until hit" loops are solved by formula (self-loop elimination), and simulation only verifies a policy the solver has found.

Settled in the feasibility session before [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) and recorded there under "Settled before the grill".

## Considered options

- Hand-written method recipes searched by an optimizer (the old prototype on `archive/prototype`): rejected, it only finds the routes someone already wrote down.
- Monte Carlo over candidate routes: rejected as the way to compute odds; simulation is kept only as a check (ADR-0019).
