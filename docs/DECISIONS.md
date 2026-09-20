# Decisions (one dated entry per design choice, with the alternatives rejected)

## 2026-09-20 D1. A local engine, not Craft of Exile as a service
The lead and the owner: crafting is data + about fifty action rules + a few sourced numbers; a local engine runs millions of
rolls a second, a website cannot be queried at that scale and must not be. Craft of Exile is read to learn the rules and is a
reference for a few dozen known-answer tests. Its code and compiled data are not copied.

## 2026-09-20 D2. Strategy TEMPLATES before any general solver
An optimal-policy solver over all item states is research. The prototype ranks a library of templates typed by mechanism
(spam, alt-aug-regal, protect-one-half, blocking, eldritch finishing, fracture-then-spam), each with an exact or Monte Carlo cost.
