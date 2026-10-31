"""Shared setup of the #130 prototype: R14-like Hunter Thicket Bow, real 3.29.3.3 data."""
import os, sys, time
sys.path.insert(0, os.path.abspath("src")); sys.path.insert(0, os.path.abspath("tests"))
os.environ.setdefault("CRAFTING_CACHE_DIR", os.path.abspath(".claude/scratch/real-cache"))
from crafting_system.abstraction import Abstraction, Goal, Wanted, integer_weights
from crafting_system.actions import (AlterationOrb, AugmentationOrb, RegalOrb, TransmutationOrb, ScouringOrb, ExaltedOrb,
    AnnulmentOrb, ChaosOrb, build_pool, ActionError)
from crafting_system.data import load_game_data
from crafting_system.items import Item, Rarity, Influence, tier_table, ExplicitMod

BASE = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
LEVEL = 78

def data():
    return load_game_data()

def start(d, influences=(Influence.HUNTER,), rarity=Rarity.NORMAL):
    return Item.build(d, base_id=BASE, item_level=LEVEL, rarity=rarity, influences=frozenset(influences))

def fam_ids(d, family):
    return frozenset(m.id for m in d.mods.values() if m.families == (family,))
