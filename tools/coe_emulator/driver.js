/*
 * In-page driver for Craft of Exile's emulator ("Wraecrafter Ultra"), ticket #198.
 *
 * Loaded by emulator.py into the real page (served from the local copy in .claude/scratch/coe/),
 * after the emulator tab is open. It calls the emulator's own functions, the ones its buttons call,
 * and never re-implements a rule:
 *
 *   build(spec)        poec_simPickBaseGroup / PickBase / PickItem / FinishSetup, then one
 *                      poec_simApplyCraftGO({action: "add"}) per mod (the click on a mod in the
 *                      mod list), {action: "frac"} for a fractured one, poec_simSetRarity.
 *   legal()            what poec_updateActionEnabling left: crsim_actions.*.enabled, the subset
 *                      buttons' "disabled" class, and the reasons in crsim_dreasons / crsim_preasons.
 *   apply(craft, n)    n times: restore the built item, set crsim_params as the buttons do, call
 *                      poec_simApplyCraftGO(null, null, true) (poec_simAwaken for an Awakener's Orb),
 *                      and count the resulting items.
 *
 * A mod is {aid, tindex, bench, frac}: the CoE modifier id and the index into
 * poecd.tiers[aid][base] (ordered by item level, the highest tier last; -1 is the highest).
 */
(() => {
  const clone = (value) => (value === undefined || value === null ? value : JSON.parse(JSON.stringify(value)));
  const notices = [];
  const original = $.fn.mcuiNotice;
  $.fn.mcuiNotice = function (options) {
    if (options && options.text) notices.push(String(options.text));
    return original.apply(this, arguments);
  };
  const thrown = [];
  const originalThrow = window.poec_simThrowError;
  window.poec_simThrowError = function (error) {
    thrown.push(String(error));
    return originalThrow.apply(this, arguments);
  };

  const modifier = (aid) => poecd.modifiers.seq[poecd.modifiers.ind[String(aid)]];
  const INFLUENCES = { shaper: 2, elder: 3, crusader: 4, hunter: 5, warlord: 6, redeemer: 7 };
  const influenceId = (value) => (typeof value === "number" ? value : INFLUENCES[String(value).toLowerCase()]);
  let snapshot = null;

  function bitemOf(spec) {
    if (spec.bitem !== undefined) return String(spec.bitem);
    const found = poecd.bitems.seq.filter((item) => item.name_bitem === spec.item);
    if (found.length !== 1) throw new Error(`no single CoE item named ${spec.item}`);
    return String(found[0].id_bitem);
  }

  function describe() {
    return {
      rarity: crsim_settings.rarity,
      influences: clone(crsim_settings.influences),
      corrupted: crsim_settings.corrupted || 0,
      mods: crsim_data.iaffixes.map((affix) => ({
        aid: String(affix.id),
        side: affix.atype,
        tindex: affix.tindex,
        bench: affix.bench || 0,
        frac: affix.frac || 0,
        mgrp: String(affix.mgrp),
        name: affix.id > 0 ? modifier(affix.id).name_modifier : "veiled",
        nvalues: affix.nvalues,
        level: affix.id > 0 && affix.tindex !== "e" ? Number(poecd.tiers[affix.id][crsim_settings.base][affix.tindex].ilvl) : null,
      })),
      meta: clone(crsim_data.meta_flags),
    };
  }

  // The item as the emulator's export button writes it (also the donor format of the Awakener's Orb).
  function exported() {
    return {
      settings: clone(crsim_settings),
      params: clone(crsim_params),
      data: {
        implicits: clone(crsim_data.implicits), iaffixes: clone(crsim_data.iaffixes), iaffbt: clone(crsim_data.iaffbt),
        imprint: clone(crsim_data.imprint), eldritch: clone(crsim_data.eldritch), meta_flags: clone(crsim_data.meta_flags),
      },
      log: clone(crsim_log), spending: clone(crsim_spending), opened: clone(crsim_opened), catalyst: clone(crsim_catalyst),
    };
  }

  function refresh() {
    poec_simUpdateMeta();
    poec_updateItemAffixes();
    poec_updateActionEnabling();
    poec_simRefreshModPool();
  }

  function build(spec) {
    notices.length = 0;
    const bitem = bitemOf(spec);
    const base = String(poecd.bitems.seq[poecd.bitems.ind[bitem]].id_base);
    const bgroup = String(poecd.bases.seq[poecd.bases.ind[base]].id_bgroup);
    crsim_settings = null;
    crsim_data = null;
    poec_simGoToStart();
    poec_simPickBaseGroup(Number(bgroup));
    poec_simPickBase(base);
    poec_simPickItem(bitem);
    crsim_settings.ilvl = spec.ilvl ?? 100;
    crsim_settings.quality = spec.quality ?? 20;
    crsim_settings.influences = spec.influences && spec.influences.length ? spec.influences.map(influenceId) : null;
    poec_simFinishSetup();
    crsim_lock = false;
    for (const mod of spec.mods || []) {
      const before = crsim_data.iaffixes.length;
      const tiers = poecd.tiers[String(mod.aid)][base];
      const tindex = mod.tindex < 0 ? tiers.length + mod.tindex : mod.tindex;
      poec_simApplyCraftGO({ action: "add", ptype: mod.bench ? "cb" : "mp", affid: String(mod.aid), tindex }, null, true);
      if (crsim_data.iaffixes.length !== before + 1) throw new Error(`could not add mod ${mod.aid} tier ${mod.tindex}: ${notices.join("; ")}`);
      if (mod.frac) {
        poec_simApplyCraftGO({ action: "frac", ptype: modifier(mod.aid).affix, affid: String(mod.aid), tindex: before, extra: 1 }, null, true);
      }
      crsim_lock = false;
    }
    if (spec.rarity) poec_simSetRarity(spec.rarity);
    if (spec.corrupted) crsim_settings.corrupted = 1;
    refresh();
    snapshot = {
      settings: clone(crsim_settings), data: clone(crsim_data), catalyst: clone(crsim_catalyst), hasfrac: crsim_hasfrac,
      currency: Object.fromEntries(Object.entries(crsim_actions.currency).map(([code, entry]) => [code, entry.enabled])),
      actions: Object.fromEntries(Object.entries(crsim_actions.actions).map(([code, entry]) => [code, entry.enabled])),
    };
    return { item: describe(), notices: notices.slice(), exported: exported() };
  }

  function restore() {
    crsim_settings = clone(snapshot.settings);
    crsim_data = clone(snapshot.data);
    crsim_catalyst = clone(snapshot.catalyst);
    crsim_hasfrac = snapshot.hasfrac;
    for (const [code, enabled] of Object.entries(snapshot.currency)) crsim_actions.currency[code].enabled = enabled;
    for (const [code, enabled] of Object.entries(snapshot.actions)) crsim_actions.actions[code].enabled = enabled;
    crsim_lock = false;
    crsim_bypass = null;
  }

  function reasonsOf(code) {
    return [...(crsim_preasons[code] || []), ...(crsim_dreasons[code] || [])];
  }

  function legal() {
    restore();
    refresh();
    const result = { currency: {}, actions: {} };
    for (const [code, entry] of Object.entries(crsim_actions.currency)) {
      result.currency[code] = { enabled: entry.enabled !== false, reasons: reasonsOf(code) };
    }
    for (const [code, entry] of Object.entries(crsim_actions.actions)) {
      const subsets = {};
      for (const scode of Object.keys(entry.subset || {})) {
        const button = $("#crsimSubsets").find(".acs_" + code).find(".acs_" + code + scode);
        subsets[scode] = {
          enabled: button.length ? !button.hasClass("disabled") : null,
          reasons: reasonsOf(code + scode).concat(reasonsOf(scode)),
        };
      }
      result.actions[code] = { enabled: entry.enabled !== false, reasons: reasonsOf(code), subsets };
    }
    restore();
    return result;
  }

  function signature(item) {
    const mods = item.mods.map((mod) => `${mod.side}:${mod.aid}:${mod.tindex}${mod.bench ? ":b" : ""}${mod.frac ? ":f" : ""}`).sort();
    return JSON.stringify({ rarity: item.rarity, influences: item.influences, corrupted: item.corrupted, mods });
  }

  // craft: {currency, subaction?, ssaction?}, {action, subaction?, ssaction?} (an essence: subaction its
  // id_essence, ssaction its tier index) or {force: {ptype, aid, tindex}} (a bench craft: ptype "cb");
  // donor: an export (Awakener's Orb).
  function apply(craft, repeats, options = {}) {
    const counts = {};
    const examples = {};
    const failures = {};
    const pageErrors = [];
    for (let index = 0; index < repeats; index += 1) {
      restore();
      notices.length = 0;
      thrown.length = 0;
      if (craft.currency) {
        crsim_params.mode = "currency";
        crsim_params.currency = craft.currency;
        crsim_params.action = null;
      } else {
        crsim_params.mode = "action";
        crsim_params.currency = null;
        crsim_params.action = craft.action;
      }
      crsim_params.subaction = craft.subaction ?? null;
      crsim_params.ssaction = craft.ssaction ?? null;
      if (craft.action === "essence") {
        // the essence button keeps the forced mod of the chosen tier in crsim_curessmod (poec_simSetParams);
        // {essmod, ssaction} finds the essence by the button of its forced mod and tier
        let button = craft.subaction
          ? $("#crsimESSTChooser_" + craft.subaction).find("[sscode='" + craft.ssaction + "']")
          : $(`[essmod='${craft.essmod}'][sscode='${craft.ssaction}']`);
        if (button.length !== 1) throw new Error(`no single essence button for ${JSON.stringify(craft)}`);
        crsim_params.subaction = button.parent().attr("id").replace("crsimESSTChooser_", "");
        crsim_curessmod = button.attr("essmod");
      }
      const before = JSON.stringify(crsim_data.iaffixes) + JSON.stringify(crsim_settings);
      if (craft.currency === "woke") {
        // the importer window reads the selected currency button back when it closes (poec_simWokerClose)
        $("#crsimOptCur").children("div").removeClass("sel");
        $("#crsimOptCur").children(".ac_woke").addClass("sel");
        poec_simShowItemImporter("woker");
        $("#poecSimWokeData").removeClass("init error").val(JSON.stringify(options.donor));
        try {
          poec_simAwaken();
        } catch (error) {
          // after the craft the emulator itself throws: the enabling step unselects the Awakener's Orb
          // (the item is now dual-influenced) and poec_simWokerClose reads the selection back
          pageErrors.push(String(error));
        }
      } else if (craft.force) {
        // a click on one tier of the mod list (ptype "cb": the crafting bench), as poec_simForceAction gets it
        refresh();
        const { ptype, aid, tindex } = craft.force;
        const button = $(`[onclick='poec_simForceAction(this,"${ptype}",${aid},${tindex})']`);
        if (!button.length) throw new Error(`no ${ptype} button for mod ${aid} tier ${tindex} in the mod list`);
        poec_simForceAction(button[0], ptype, Number(aid), Number(tindex));
      } else {
        poec_simApplyCraftGO(null, null, true);
      }
      const changed = JSON.stringify(crsim_data.iaffixes) + JSON.stringify(crsim_settings) !== before;
      const message = notices.concat(thrown).join("; ");
      if (!changed) {
        const key = message || "no change";
        failures[key] = (failures[key] || 0) + 1;
        continue;
      }
      const item = describe();
      const key = signature(item);
      counts[key] = (counts[key] || 0) + 1;
      if (!examples[key]) examples[key] = { item, notice: message || null };
    }
    restore();
    const errors = [...new Set(pageErrors)];
    return { repeats, counts, examples, failures, ...(errors.length ? { page_errors_after_craft: errors } : {}) };
  }

  window.coeh = { build, legal, apply, describe, exported, restore };
  return true;
})();
