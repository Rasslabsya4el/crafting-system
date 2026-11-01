# A plan may burn a Lock and lock again; the Lock is a priced, used-up resource

The Lock costs money each time it is bought, so what a plan does when no preview is good enough decides its value. This ADR is the price, the use-up and the burn. The Peek that holds them is ADR-0054; what previews is ADR-0055.

## The Lock as a resource

- **Price.** One use consumes 1 `Hinekora's Lock` from the price file (ADR-0007, ADR-0011): 271 to 272 Divine Orbs on poe.ninja's Allflame data on 2026-10-31, which the file dates. The exchange is the only price source: the beast recipe, drops and divination cards have no price (ADR-0055). With no price the Lock is dropped and the report lists it with the other actions dropped for a missing price (ADR-0007). A hand override works as for any line, so a cheap Lock can be tried.
- **Used up** on use (owner, [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) answer 3d). A second Lock is a second purchase, so a relock pays `L` again.

## Burn and relock is allowed

After looking, the player may accept an option, apply an unpreviewed action, or give the Lock up by changing the item with a cheap currency, the **burn**, and lock again (the wiki: the way to get fresh previews; 2023 players describe it). The solver takes it only when it pays: it is a candidate for the fallback `F(s)`, and under independence the relock throws every draw again (ADR-0054).

- **A burn is a currency that changes no mod and is allowed on the item.** Actions declare it (`burn`, default false). The candidates, from the wiki:
  - **Chromatic Orb** on an item that has sockets (weapons and armour). It always changes the colours (it cannot return the ones the item has, ADR-0047), so it is a move wherever the state keeps sockets (below);
  - **a re-anoint** on rings and amulets (the wiki: "least destructive"); refused where the target requires the enchantment it would replace (ADR-0050);
  - **a Blessed Orb** on an item with a ranged implicit, a belt for instance, when no requirement reads the implicit; not on an item with an Eldritch implicit (ADR-0027);
  - a quality currency, only where the compressed state keeps quality.

  The burn of a state is the cheapest legal candidate at the prices of the price file. Each candidate is a claim with its price name.
- **A jewel has no burn**: no cheap currency is known to end its foresight, and a jewel has no quality, sockets or anoint (note, open point 5). Its `F` is the unpreviewed actions, or the restart if the target names a start price.
- **A burn is never offered as a plain action.** An action that changes nothing the state keeps gives a target nothing, so only the fallback of a Peek uses it.
- **A start item that states no sockets counts as having one for the burn.** The item stores sockets since B6 (ADR-0046), but a start item that states none is given one only when the target names sockets. A real base always has sockets, so for the burn alone an item of a socketable class is assumed to have at least one; the claim is `approximate` and the assumption is listed on any answer that burns with a Chromatic Orb.

### How the solver sees a burn

A burn is an ordinary unpreviewed action with its own kernel from `outcomes`, so the Peek needs no special case.

- If the burn changes nothing the compressed state keeps (the sockets of a target with no socket requirement, the implicit of a target that does not read it), it leads back to `s`: `V(s)` appears on both sides, a self-loop whose chance is "no preview is good enough", which the solver handles as a cycle through the Lock in the policy expansion (ADR-0054; the self-loop elimination of ADR-0010 does not apply to it).
- If it changes a dimension the state keeps (quality when it is a target, sockets and links once a target names them, ADR-0046), it is a move to another state `s'`, and `F(s)` uses `c_burn + V(s')`; there is no loop. A quality burn runs out at maximum quality, so it is a finite chain, never a free loop.

B6 designed the real Chromatic Orb with a socket state (ADR-0045 to ADR-0047): once it is built it declares `burn`, B8 builds no burn-only Chromatic kind, and the move rule above applies when a target names sockets. Neither B6 nor B7 adds an anoint action (B7's enchants are the Tempering and Tailoring Orbs and the Harvest quality enchants, ADR-0050), so the re-anoint stays a burn-only kind; the state keeps no enchantment (ADR-0050), so it never changes the state.

Origin: [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) (the round draft, "Burn and relock is allowed"; owner answer 3d); [Hinekora's Lock in 3.29](../research/2026-10-31-hinekora-lock.md) sections 3.2, 5 and 6.1; ADR-0007, ADR-0010, ADR-0027, ADR-0054.
