# Exactness is verified in five layers

The planner promises exact odds and costs (ADR-0001, ADR-0009), so each link of the chain from rules to policy is checked against something written independently of it:

1. The compressed kernel equals full enumeration on concrete items, in integers and exact fractions; this proves the design-D merges exact (ADR-0009).
2. An independent `simulator`, written from the rules registry and not from the kernel code, agrees statistically with the kernel.
3. The solver matches HiGHS LP and brute force on small cases.
4. Every benchmark policy is run on concrete items: mean ± confidence interval against the computed value.
5. Published numbers (R12's and the other benchmark routes') are acceptance tests (ADR-0020).

For an ordinary query simulation is off by default and `--verify` turns it on; for benchmarks it is always on.

Origin: [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q19.

## Amendment: the Peek (B8, [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106), 2026-11-01)

Layer 3 gains an oracle for the `Peek` kind: the explicit product expansion, with states `(s, previews)`, of tiny models, solved by the existing solver, brute force and HiGHS, and the hand test of ADR-0054 (23.97, 66, break-even 42.03). Layer 2 samples each option of a Lock independently on a copy of the concrete item. Layer 4 adds R29 with the Lock. The details are in ADR-0057.
