# Quality on weapons and armour is bought before the orbs

Quality on a weapon or armour matters to the finish in two places: the Chromatic Orb's non-white chance has the factor `1 + min(quality, 30) / 100` (ADR-0047), and the Orb of Fusing's table exists for 20% quality only. #81 put "quality as it affects sockets" in B6. This is the weapon and armour counterpart of ADR-0029's catalyst quality.

## How quality is bought

Blacksmith's Whetstones raise the quality of weapons and Armourer's Scraps that of armours, to at most 20% (wiki, checked 2026-11-01). Since 3.25.0 the amount of one currency item depends on the item level and not on the rarity: the same formula as the catalysts of ADR-0029, `f = max(1, min(30·e^(−ilvl/30) − 0.3, 20))`, floored with the fraction as a chance of one more point. The expected number to 20% is about 9.5 currency items at item level 75, 13.3 at 84, 20 from 95 up. **The draft's "+5% normal, +2% magic, +1% rare" is the rule of version 0.8.1 and is out of date**; the wiki's Whetstone page keeps it in the version history only, and unique items (never a start item or a target) get 1%. Harvest enchantments that change what quality does leave the socket effect of quality unchanged, so they do not matter here.

## What the finish does with it

The finish (ADR-0045) is solved at two quality levels, **the start item's own and 20%**, and takes the cheaper: the cost of reaching 20% is the expected currency count times its price, added at the start of the finish. Partial raising is not offered: orbs cost far more than scraps, so the cap is nearly always the right level, and the narrow band where a smaller amount would pay is not worth a state dimension. At the item's own level below 20% the Orb of Fusing is not offered (ADR-0047). A start item above 20% (random drops reach 30%) uses its own quality for the Chromatic Orb and the 20% table for Fusing.

## Kind of quality, target and state

`Quality` becomes a value with a kind: the catalyst quality of jewellery (type and percent, ADR-0027) or the plain percent of a weapon or armour; the two never share an item class, so an item holds one. A target that asks for `quality: {min_percent}` on a weapon or armour is bought by the same currencies as part of the finish; the displayed damage or defence is the base times `1 + quality / 100` and is not a requirement on a roll. The quality enters the compressed state only when an enabled action reads it, as ADR-0027 says; the finish holds it as a constant of its sub-problem.

## Prices

Whetstone and Scrap are added to the price names; both are cheap and can be priced from the currency exchange or the trade site as any currency.

Origin: [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (draft, with the wiki check of 2026-11-01); [Sockets, links and colours in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/99); [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81); ADR-0027, ADR-0029, ADR-0045, ADR-0047.
