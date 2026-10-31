"use strict";

/*
 * Offline bridge to Craft of Exile's own probability kernel (ticket #73).
 *
 * The oracle for tests/test_proto_coe_comparison.py. It reads the local copy of Craft of Exile
 * (package.js and poec_data.json, git-ignored, never copied into the repo), cuts the original
 * declarations of `poec_computeFinalProbsV2`, `poec_computePermutationsV2`, `perm` and the three
 * cached count tables out of package.js, and runs them unchanged in a Node vm context. Only the
 * UI diagnostics ($, poec_odiagV2, poec_startDiag, poec_endDiag) are stubbed. No network, no
 * install, no page automation.
 *
 * Ported from the prototype's tools/coe_offline.cjs (branch archive/prototype), trimmed to what
 * the carried cases need: the "real_final" path (a Chaos Orb reroll and an essence reroll of a
 * rare item, both through poec_computeFinalProbsV2 in mode "x"). The kernel-only path of the
 * prototype (Exalted, Regal on magic items) is not carried: those cases wait for their tickets.
 * The frozen-offset check of the prototype is replaced by the SHA256 of package.js, which the
 * Python side pins: with the same bytes the extracted declarations are the same.
 *
 * Usage:  node coe_bridge.cjs <folder of the Craft of Exile copy>   (JSON on stdin, JSON on stdout)
 *
 * Input:  {"cases": [{"id", "base_id", "item_level", "method": "chaos" | "essence",
 *                     "req_max_groups", "targets": {"prefix": [aid..], "suffix": [aid..]},
 *                     "exclude_aids": [aid..], "forced_side", "forced_essence_name"}]}
 * Output: {"node_version", "source_hashes", "cases": [{"id", "probability", "pool_totals",
 *          "targets", "forced_essence"}]}
 *
 * A target is a Craft of Exile modifier id (aid); the bridge scores its top tier eligible at the
 * item level, as CoE's own selected-tier requirement does, and reports that tier's level and
 * value range so that the caller can check it against its own data.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const TIMEOUT_MS = 2000;

function fail(message) {
  throw new Error(message);
}

function sha256(text) {
  return crypto.createHash("sha256").update(text).digest("hex");
}

function readText(file) {
  if (!fs.existsSync(file)) fail(`missing Craft of Exile file: ${file}`);
  return fs.readFileSync(file, "utf8");
}

// The complete text of `function name(...) { ... }`, found by brace counting that skips strings
// and comments.
function findFunction(source, name) {
  const marker = `function ${name}`;
  const start = source.indexOf(marker);
  if (start < 0) fail(`missing CoE function: ${name}`);
  const opening = source.indexOf("{", start + marker.length);
  if (opening < 0) fail(`missing opening brace for CoE function: ${name}`);
  let depth = 0;
  let quote = null;
  let escaped = false;
  let lineComment = false;
  let blockComment = false;
  for (let index = opening; index < source.length; index += 1) {
    const character = source[index];
    const next = source[index + 1];
    if (lineComment) {
      if (character === "\n") lineComment = false;
      continue;
    }
    if (blockComment) {
      if (character === "*" && next === "/") {
        blockComment = false;
        index += 1;
      }
      continue;
    }
    if (quote) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === "/" && next === "/") {
      lineComment = true;
      index += 1;
    } else if (character === "/" && next === "*") {
      blockComment = true;
      index += 1;
    } else if (character === "'" || character === '"' || character === "`") {
      quote = character;
    } else if (character === "{") {
      depth += 1;
    } else if (character === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  return fail(`unclosed CoE function: ${name}`);
}

// The complete text of `var name=...;`
function findVariable(source, name) {
  const marker = `var ${name}=`;
  const start = source.indexOf(marker);
  if (start < 0) fail(`missing CoE variable declaration: ${name}`);
  let quote = null;
  let escaped = false;
  for (let index = start + marker.length; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === quote) quote = null;
    } else if (character === "'" || character === '"' || character === "`") {
      quote = character;
    } else if (character === ";") {
      return source.slice(start, index + 1);
    }
  }
  return fail(`unclosed CoE variable declaration: ${name}`);
}

function readData(text) {
  const context = {};
  vm.createContext(context);
  vm.runInContext(text, context, { timeout: TIMEOUT_MS * 5 });
  const data = context.poecd;
  if (!data || !data.modifiers || !data.tiers || !data.basemods || !data.essences) {
    fail("CoE data did not define the required poecd tables");
  }
  return data;
}

function jqueryStub() {
  return jqueryStub;
}
for (const method of ["addClass", "attr", "children", "find", "hide", "html", "removeClass", "show"]) {
  jqueryStub[method] = () => jqueryStub;
}
jqueryStub.each = (value, callback) => {
  if (Array.isArray(value)) value.forEach((item, index) => callback(index, item));
  else if (value && typeof value === "object") Object.keys(value).forEach((key) => callback(key, value[key]));
  return value;
};

function parseGroups(raw, aid) {
  const groups = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!Array.isArray(groups) || groups.length === 0) fail(`empty CoE modgroups for ${aid}`);
  return groups.map(String);
}

// CoE's pool of one base: the ordinary modifiers (id_mgroup 1) of basemods[base] whose tiers are
// positive-weight and not above the item level, minus the excluded aids and every modifier that
// shares an exclusion group with them or with the forced essence modifier.
function buildPool(data, baseId, itemLevel, excludedAids, extraExcludedGroups) {
  const ids = data.basemods[baseId];
  if (!Array.isArray(ids)) fail(`missing CoE basemods for base ${baseId}`);
  const excluded = new Set(excludedAids.map(String));
  const excludedGroups = new Set(extraExcludedGroups.map(String));
  for (const aid of excluded) {
    const modifier = data.modifiers.seq[data.modifiers.ind[aid]];
    if (!modifier) fail(`cannot exclude missing CoE aid: ${aid}`);
    parseGroups(modifier.modgroups, aid).forEach((group) => excludedGroups.add(group));
  }
  const seen = new Set();
  const pool = { prefix: [], suffix: [] };
  for (const rawAid of ids) {
    const aid = String(rawAid);
    if (seen.has(aid) || excluded.has(aid)) continue;
    seen.add(aid);
    const modifier = data.modifiers.seq[data.modifiers.ind[aid]];
    if (!modifier || String(modifier.id_mgroup) !== "1") continue;
    const groups = parseGroups(modifier.modgroups, aid);
    if (groups.some((group) => excludedGroups.has(group))) continue;
    const side = modifier.affix;
    if (side !== "prefix" && side !== "suffix") continue;
    const tiers = data.tiers[aid] && data.tiers[aid][baseId];
    if (!Array.isArray(tiers)) continue;
    const eligible = tiers
      .map((tier) => ({ ilvl: Number(tier.ilvl), weight: Number(tier.weighting), range: tier.nvalues }))
      .filter((tier) => Number.isFinite(tier.ilvl) && tier.ilvl <= itemLevel && Number.isFinite(tier.weight) && tier.weight > 0);
    const weight = eligible.reduce((sum, tier) => sum + tier.weight, 0);
    if (weight > 0) pool[side].push({ aid, weight, modgroups: groups, eligible_tiers: eligible });
  }
  return pool;
}

function resolveForcedEssence(data, essenceName, baseId, itemLevel) {
  const matches = data.essences.seq.filter((essence) => essence.name_essence === essenceName);
  if (matches.length !== 1) fail(`ambiguous or missing CoE essence name: ${essenceName}`);
  const aid = String(JSON.parse(matches[0].tiers)[baseId]);
  const modifier = data.modifiers.seq[data.modifiers.ind[aid]];
  if (!modifier) fail(`forced CoE essence modifier is absent: ${aid}`);
  const rows = (data.tiers[aid] && data.tiers[aid][baseId]) || [];
  const tier = rows.map((row) => ({ ...row, ilvl: Number(row.ilvl) })).filter((row) => row.ilvl <= itemLevel).at(-1);
  if (!tier) fail(`forced CoE essence modifier has no eligible tier: ${aid}`);
  return {
    essence_id: String(matches[0].id_essence),
    aid,
    side: modifier.affix,
    modgroups: parseGroups(modifier.modgroups, aid),
    level: tier.ilvl,
    range: tier.nvalues,
  };
}

function topTier(pool, side, aid) {
  const entry = pool[side].find((candidate) => candidate.aid === String(aid));
  if (!entry) fail(`target ${aid} is absent from the eligible CoE ${side} pool`);
  const tier = entry.eligible_tiers.at(-1);
  return { aid: entry.aid, side, weight: tier.weight, level: tier.ilvl, range: tier.range };
}

function runFinal(source, data, input) {
  const baseId = String(input.base_id);
  const forced = input.forced_essence_name
    ? resolveForcedEssence(data, input.forced_essence_name, baseId, input.item_level)
    : null;
  if (forced && forced.side !== input.forced_side) fail(`forced essence side is ${forced.side}`);
  const pools = buildPool(data, baseId, input.item_level, input.exclude_aids || [], forced ? forced.modgroups : []);
  for (const side of ["prefix", "suffix"]) if (pools[side].length === 0) fail(`empty CoE ${side} pool`);
  const targets = { prefix: [], suffix: [] };
  for (const side of ["prefix", "suffix"]) targets[side] = (input.targets[side] || []).map((aid) => topTier(pools, side, aid));
  if (targets.prefix.length + targets.suffix.length === 0) fail("a case needs at least one target");

  const weight = {};
  for (const side of ["prefix", "suffix"]) weight[side] = pools[side].reduce((sum, entry) => sum + entry.weight, 0);
  const override = {
    weight,
    tiers: Object.fromEntries(
      ["prefix", "suffix"].map((side) => [side, pools[side].reduce((sum, entry) => sum + entry.eligible_tiers.length, 0)]),
    ),
    mods: { prefix: pools.prefix.length, suffix: pools.suffix.length },
    modpool: pools,
    reqpool: {
      prefix: targets.prefix.map(({ aid, weight: w }) => ({ aid, weight: w })),
      suffix: targets.suffix.map(({ aid, weight: w }) => ({ aid, weight: w })),
    },
    rqgpool: {
      prefix: ["", ...targets.prefix.map(({ aid }) => ({ affids: [aid] }))],
      suffix: ["", ...targets.suffix.map(({ aid }) => ({ affids: [aid] }))],
    },
  };

  const context = {
    $: jqueryStub,
    numModifersToExact: 10,
    pavgaffs: {},
    pavgcnts: {},
    poec_cAlgoMode: "x",
    poec_cUniqueNotable: false,
    poec_endDiag: () => undefined,
    poec_odiagV2: () => undefined,
    poec_startDiag: () => 0,
    poecd: data,
    aconsts: { game: "poe1" },
    curEssence: input.forced_side ? { atype: input.forced_side } : null,
    has_glyphic: false,
    has_hollow: false,
    peoc_cGraveyardEffect: null,
    poec_cAdvMet: null,
    poec_cBuild: {},
    poec_cCatalyst: null,
    poec_cEssence: input.forced_side ? "offline-forced" : null,
    poec_cMandatory: { prefix: null, suffix: null },
    poec_cMethod: input.method,
    poec_isFractured: 0,
    poec_nBase: { g: 0, i: 0 },
    reqMaxGrps: input.req_max_groups,
    specialBases: { simplex: -1 },
    totReqAffixByType: { prefix: targets.prefix.length, suffix: targets.suffix.length },
    __override: override,
  };
  vm.createContext(context);
  for (const text of [
    findVariable(source, "affPermutes"),
    findVariable(source, "essNumProbs"),
    findVariable(source, "affNumProbs"),
    findFunction(source, "perm"),
    findFunction(source, "poec_computePermutationsV2"),
    findFunction(source, "poec_computeFinalProbsV2"),
  ]) {
    vm.runInContext(text, context, { timeout: TIMEOUT_MS });
  }
  vm.runInContext("__result = poec_computeFinalProbsV2(__override, false);", context, { timeout: TIMEOUT_MS });
  const probability = Number(context.__result);
  if (!Number.isFinite(probability)) fail("the CoE final calculator returned no finite probability");
  return { id: input.id, probability, pool_totals: weight, targets, forced_essence: forced };
}

function main() {
  const folder = process.argv[2];
  if (!folder) fail("usage: node coe_bridge.cjs <folder of the Craft of Exile copy>");
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  if (!input || !Array.isArray(input.cases) || input.cases.length === 0) fail("expected a non-empty cases array");
  const source = readText(path.join(folder, "package.js"));
  const dataText = readText(path.join(folder, "poec_data.json"));
  const data = readData(dataText);
  const cases = input.cases.map((one) => runFinal(source, data, one));
  process.stdout.write(`${JSON.stringify({
    node_version: process.version,
    source_hashes: { package: sha256(source), poec_data: sha256(dataText) },
    cases,
  })}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
