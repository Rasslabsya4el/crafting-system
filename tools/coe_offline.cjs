"use strict";

// This bridge only loads complete CoE declarations at runtime.  Its inputs and
// diagnostics are intentionally separate from the frozen calculator source.
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const vm = require("vm");


const ROOT = process.cwd();
const DEFAULT_PACKAGE = path.join(ROOT, "sources", "raw", "coe", "package.js");
const DEFAULT_DATA = path.join(ROOT, "sources", "raw", "coe", "poec_data.json");
const PACKAGE_PATH = process.argv[2] === "--package" ? process.argv[3] : DEFAULT_PACKAGE;
const SOURCE_TIMEOUT_MS = 2_000;
const FROZEN_FUNCTION_LOCATIONS = Object.freeze({
  poec_computeFinalProbsV2: {
    offset: { start: 406614, end: 459392 },
    line: { start: 1021, end: 1198 },
  },
  poec_computePermutationsV2: {
    offset: { start: 459393, end: 476461 },
    line: { start: 1199, end: 1249 },
  },
});


function fail(message) {
  throw new Error(message);
}


function readSource(sourcePath) {
  if (!sourcePath || !fs.existsSync(sourcePath)) {
    fail(`missing CoE package source: ${sourcePath}`);
  }
  return fs.readFileSync(sourcePath, "utf8");
}


function sourceHash(source) {
  return crypto.createHash("sha256").update(source).digest("hex");
}


function readData(dataPath = DEFAULT_DATA) {
  if (!fs.existsSync(dataPath)) fail(`missing CoE data source: ${dataPath}`);
  const context = {};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(dataPath, "utf8"), context, { timeout: SOURCE_TIMEOUT_MS * 5 });
  if (!context.poecd || !context.poecd.modifiers || !context.poecd.tiers || !context.poecd.basemods) {
    fail("CoE data source did not define the required poecd tables");
  }
  return context.poecd;
}


function readDataHash(dataPath = DEFAULT_DATA) {
  if (!fs.existsSync(dataPath)) fail(`missing CoE data source: ${dataPath}`);
  return sourceHash(fs.readFileSync(dataPath, "utf8"));
}


function findFunction(source, name) {
  const marker = `function ${name}`;
  const start = source.indexOf(marker);
  if (start < 0) {
    fail(`missing CoE function: ${name}`);
  }
  const opening = source.indexOf("{", start + marker.length);
  if (opening < 0) {
    fail(`missing opening brace for CoE function: ${name}`);
  }
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
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === quote) {
        quote = null;
      }
      continue;
    }
    if (character === "/" && next === "/") {
      lineComment = true;
      index += 1;
      continue;
    }
    if (character === "/" && next === "*") {
      blockComment = true;
      index += 1;
      continue;
    }
    if (character === "'" || character === '"' || character === "`") {
      quote = character;
      continue;
    }
    if (character === "{") depth += 1;
    if (character === "}") {
      depth -= 1;
      if (depth === 0) {
        return { start, end: index + 1, declaration: source.slice(start, index + 1) };
      }
    }
  }
  fail(`unclosed CoE function: ${name}`);
}


function frozenLocation(name, extracted) {
  const expected = FROZEN_FUNCTION_LOCATIONS[name];
  if (!expected) fail(`no frozen location registered for CoE function: ${name}`);
  if (extracted.start !== expected.offset.start || extracted.end !== expected.offset.end) {
    fail(`frozen CoE function offset changed for ${name}`);
  }
  return { source_range: expected.offset, source_line_range: expected.line };
}


function jqueryEach(value, callback) {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) callback(index, value[index]);
    return value;
  }
  if (value && typeof value === "object") {
    for (const key of Object.keys(value)) callback(key, value[key]);
    return value;
  }
  return value;
}


function jqueryStub() {
  return jqueryStub;
}


for (const method of ["addClass", "attr", "children", "find", "hide", "html", "removeClass", "show"]) {
  jqueryStub[method] = () => jqueryStub;
}
jqueryStub.each = jqueryEach;


function validatePool(pool) {
  if (!Array.isArray(pool) || pool.length === 0) fail("pool must be a non-empty array");
  const identifiers = new Set();
  return pool.map((entry) => {
    if (!entry || typeof entry !== "object") fail("pool entries must be objects");
    const aid = String(entry.aid);
    const weight = Number(entry.weight);
    if (!aid || !Number.isFinite(weight) || weight <= 0) fail("pool entries need a positive weight and aid");
    if (identifiers.has(aid)) fail(`duplicate pool aid: ${aid}`);
    identifiers.add(aid);
    if (!Array.isArray(entry.modgroups) || entry.modgroups.length === 0) fail(`pool entry ${aid} needs modgroups`);
    return { aid, weight, modgroups: entry.modgroups.map(String) };
  });
}


function validateRequirements(requirements, available) {
  if (!Array.isArray(requirements) || requirements.length === 0) fail("requirements must be a non-empty array");
  return requirements.map((group, index) => {
    if (!Array.isArray(group) || group.length === 0) fail(`requirement group ${index} must be a non-empty array`);
    const checked = group.map(String);
    for (const aid of checked) if (!available.has(aid)) fail(`required aid is absent from pool: ${aid}`);
    return checked;
  });
}


function makeContext(source, data) {
  const permutation = findFunction(source, "poec_computePermutationsV2");
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
    poecd: data || { modifiers: { ind: {}, seq: [] } },
  };
  vm.createContext(context);
  vm.runInContext(readVariableStatement(source, "affPermutes"), context, { timeout: SOURCE_TIMEOUT_MS });
  vm.runInContext(permutation.declaration, context, { timeout: SOURCE_TIMEOUT_MS });
  return { context, permutation };
}


function runKernel(source, input, data) {
  const pool = validatePool(input.pool);
  const requirements = validateRequirements(input.requirements, new Set(pool.map((entry) => entry.aid)));
  const draws = Number(input.draws);
  if (!Number.isInteger(draws) || draws < 1 || draws > 3) fail("draws must be an integer from 1 to 3");
  if (requirements.length > draws) fail("requirement count exceeds draw count");
  const totalWeight = pool.reduce((sum, entry) => sum + entry.weight, 0);
  const selectedWeights = input.requirement_weights || {};
  if (!selectedWeights || typeof selectedWeights !== "object" || Array.isArray(selectedWeights)) {
    fail("requirement_weights must be an object when supplied");
  }
  const reqpool = pool.map((entry) => {
    if (!Object.hasOwn(selectedWeights, entry.aid)) return entry;
    const weight = Number(selectedWeights[entry.aid]);
    if (!Number.isFinite(weight) || weight <= 0 || weight > entry.weight) {
      fail(`invalid selected-tier weight for ${entry.aid}`);
    }
    return { ...entry, weight };
  });
  const override = {
    modpool: { prefix: pool, suffix: [] },
    reqpool: { prefix: reqpool, suffix: [] },
    rqgpool: { prefix: ["", ...requirements.map((affids) => ({ affids }))], suffix: [""] },
  };
  const { context, permutation } = makeContext(source, data);
  context.__input = { override, totalWeight, draws };
  vm.runInContext(
    "__result = poec_computePermutationsV2('prefix', {[__input.draws]: true}, __input.override.rqgpool.prefix, __input.totalWeight, 0, __input.override.modpool.prefix.length, __input.override, {prefix: 0, suffix: 0});",
    context,
    { timeout: SOURCE_TIMEOUT_MS },
  );
  const probability = Number(context.__result[draws]);
  if (!Number.isFinite(probability)) fail("cached CoE kernel returned no finite probability");
  return {
    method: "poec_computePermutationsV2",
    mode: "x",
    probability,
    pool_total: totalWeight,
    source_hash: sourceHash(source),
    ...frozenLocation("poec_computePermutationsV2", permutation),
  };
}


function parseGroups(rawGroups, aid) {
  let groups;
  try {
    groups = typeof rawGroups === "string" ? JSON.parse(rawGroups) : rawGroups;
  } catch (error) {
    fail(`invalid CoE modgroups for ${aid}: ${error.message}`);
  }
  if (!Array.isArray(groups) || groups.length === 0) fail(`empty CoE modgroups for ${aid}`);
  return groups.map(String);
}


function buildRealPool(data, baseId, itemLevel, excludedAids = [], extraExcludedGroups = []) {
  if (!Number.isInteger(itemLevel) || itemLevel < 1) fail("item_level must be a positive integer");
  const ids = data.basemods[String(baseId)];
  if (!Array.isArray(ids)) fail(`missing CoE basemods for base_id ${baseId}`);
  const excluded = new Set(excludedAids.map(String));
  const excludedGroups = new Set(extraExcludedGroups.map(String));
  for (const aid of excluded) {
    const modifier = data.modifiers.seq[data.modifiers.ind[aid]];
    if (!modifier) fail(`cannot exclude missing CoE aid: ${aid}`);
    for (const group of parseGroups(modifier.modgroups, aid)) excludedGroups.add(group);
  }
  const seen = new Set();
  const pool = { prefix: [], suffix: [] };
  for (const rawAid of ids) {
    const aid = String(rawAid);
    if (seen.has(aid) || excluded.has(aid)) continue;
    seen.add(aid);
    const index = data.modifiers.ind[aid];
    const modifier = data.modifiers.seq[index];
    if (!modifier || String(modifier.id_mgroup) !== "1") continue;
    const groups = parseGroups(modifier.modgroups, aid);
    if (groups.some((group) => excludedGroups.has(group))) continue;
    const side = modifier.affix;
    if (side !== "prefix" && side !== "suffix") continue;
    const tiers = data.tiers[aid] && data.tiers[aid][String(baseId)];
    if (!Array.isArray(tiers)) continue;
    const eligibleTiers = tiers
      .map((tier, index) => ({ ...tier, index, ilvl: Number(tier.ilvl), weight: Number(tier.weighting) }))
      .filter((tier) => Number.isFinite(tier.ilvl) && tier.ilvl <= itemLevel && Number.isFinite(tier.weight) && tier.weight > 0);
    const weight = eligibleTiers.reduce((sum, tier) => sum + tier.weight, 0);
    if (weight <= 0) continue;
    pool[side].push({
      aid,
      weight,
      modgroups: groups,
      eligible_tiers: eligibleTiers.map(({ index, ilvl, weight: tierWeight, nvalues }) => ({
        index, ilvl, weight: tierWeight, range: nvalues,
      })),
    });
  }
  for (const side of ["prefix", "suffix"]) {
    if (pool[side].length === 0) fail(`empty CoE ${side} pool for base_id ${baseId}`);
  }
  return pool;
}


function resolveForcedEssence(data, essenceName, baseId, itemLevel) {
  if (typeof essenceName !== "string" || !essenceName) fail("forced_essence_name must be a non-empty string");
  const matches = data.essences.seq.filter((essence) => essence.name_essence === essenceName);
  if (matches.length !== 1) fail(`ambiguous or missing CoE essence name: ${essenceName}`);
  let tiers;
  try {
    tiers = JSON.parse(matches[0].tiers);
  } catch (error) {
    fail(`invalid CoE essence tier mapping for ${essenceName}: ${error.message}`);
  }
  const aid = String(tiers[String(baseId)]);
  const modifier = data.modifiers.seq[data.modifiers.ind[aid]];
  if (!modifier) fail(`forced CoE essence modifier is absent: ${aid}`);
  const tierRows = data.tiers[aid] && data.tiers[aid][String(baseId)];
  if (!Array.isArray(tierRows)) fail(`forced CoE essence modifier has no tiers: ${aid}`);
  const eligible = tierRows
    .map((tier) => ({ ...tier, ilvl: Number(tier.ilvl) }))
    .filter((tier) => Number.isFinite(tier.ilvl) && tier.ilvl <= itemLevel);
  const tier = eligible.at(-1);
  if (!tier) fail(`forced CoE essence modifier has no eligible tier: ${aid}`);
  return {
    essence_id: String(matches[0].id_essence),
    essence_name: matches[0].name_essence,
    aid,
    side: modifier.affix,
    modgroups: parseGroups(modifier.modgroups, aid),
    level: tier.ilvl,
    range: tier.nvalues,
  };
}


function describeModifier(data, baseId, itemLevel, aid) {
  const modifier = data.modifiers.seq[data.modifiers.ind[String(aid)]];
  if (!modifier) fail(`missing CoE modifier: ${aid}`);
  const tiers = data.tiers[String(aid)] && data.tiers[String(aid)][String(baseId)];
  if (!Array.isArray(tiers)) fail(`missing CoE tiers for modifier ${aid} on base_id ${baseId}`);
  return {
    aid: String(aid),
    side: modifier.affix,
    modgroups: parseGroups(modifier.modgroups, String(aid)),
    tiers: tiers
      .map((tier) => ({ level: Number(tier.ilvl), range: tier.nvalues, weight: Number(tier.weighting) }))
      .filter((tier) => Number.isFinite(tier.level) && tier.level <= itemLevel),
  };
}


function describeExcludedModifiers(data, input) {
  const excluded = input.exclude_aids || [];
  if (!Array.isArray(excluded)) fail("exclude_aids must be an array when supplied");
  return excluded.map((aid) => describeModifier(data, String(input.base_id), input.item_level, aid));
}


function selectedTopTier(pool, side, aid) {
  const entry = pool[side].find((candidate) => candidate.aid === String(aid));
  if (!entry) fail(`target ${aid} is absent from the eligible CoE ${side} pool`);
  const tier = entry.eligible_tiers.at(-1);
  if (!tier) fail(`target ${aid} has no eligible CoE tier`);
  return { aid: entry.aid, side, weight: tier.weight, level: tier.ilvl, range: tier.range };
}


function buildTargets(pool, targets) {
  if (!targets || typeof targets !== "object") fail("targets must be an object with prefix and suffix arrays");
  const result = { prefix: [], suffix: [] };
  for (const side of ["prefix", "suffix"]) {
    if (!Array.isArray(targets[side] || [])) fail(`targets.${side} must be an array`);
    result[side] = (targets[side] || []).map((aid) => selectedTopTier(pool, side, aid));
  }
  return result;
}


function compactPool(pool) {
  return Object.fromEntries(Object.entries(pool).map(([side, entries]) => [
    side,
    entries.map(({ aid, weight, modgroups, eligible_tiers }) => ({ aid, weight, modgroups, eligible_tiers })),
  ]));
}


function runRealFinal(source, data, input) {
  const forced = input.forced_essence_name
    ? resolveForcedEssence(data, input.forced_essence_name, String(input.base_id), input.item_level)
    : null;
  if (forced && input.forced_side && input.forced_side !== forced.side) {
    fail(`forced CoE essence side differs from requested forced_side: ${forced.side}`);
  }
  const pool = buildRealPool(
    data, String(input.base_id), input.item_level, input.exclude_aids || [], forced ? forced.modgroups : [],
  );
  const targets = buildTargets(pool, input.targets);
  const calculated = runFinal(source, {
    method: input.method,
    forced_side: forced ? forced.side : input.forced_side,
    pools: compactPool(pool),
    requirements: {
      prefix: targets.prefix.map(({ aid, weight }) => ({ aid, weight })),
      suffix: targets.suffix.map(({ aid, weight }) => ({ aid, weight })),
    },
    req_max_groups: input.req_max_groups,
  }, data);
  return {
    ...calculated,
    base_id: String(input.base_id),
    item_level: input.item_level,
    targets,
    excluded_aids: (input.exclude_aids || []).map(String),
    excluded_modifiers: describeExcludedModifiers(data, input),
    forced_essence: forced,
  };
}


function runRealKernel(source, data, input) {
  const poolBySide = buildRealPool(data, String(input.base_id), input.item_level, input.exclude_aids || []);
  const selectedSides = input.pool_side === "both" ? ["prefix", "suffix"] : [input.pool_side];
  if (!selectedSides.every((side) => side === "prefix" || side === "suffix")) fail("pool_side must be prefix, suffix, or both");
  const pool = selectedSides.flatMap((side) => poolBySide[side]);
  const targets = buildTargets(poolBySide, input.targets);
  const targetRows = selectedSides.flatMap((side) => targets[side]);
  const calculated = runKernel(source, {
    pool,
    requirements: targetRows.map(({ aid }) => [aid]),
    requirement_weights: Object.fromEntries(targetRows.map(({ aid, weight }) => [aid, weight])),
    draws: input.draws,
  }, data);
  return {
    ...calculated,
    base_id: String(input.base_id),
    item_level: input.item_level,
    targets,
    excluded_aids: (input.exclude_aids || []).map(String),
    excluded_modifiers: describeExcludedModifiers(data, input),
    side_pool_totals: Object.fromEntries(["prefix", "suffix"].map((side) => [
      side,
      selectedSides.includes(side)
        ? poolBySide[side].reduce((sum, entry) => sum + entry.weight, 0)
        : 0,
    ])),
    combined_pool_total: calculated.pool_total,
    kernel_scope: "direct one-draw or side-local draw invocation with source-native weights",
  };
}


function reportRealPool(data, input) {
  const baseId = String(input.base_id);
  const excludedAids = Array.isArray(input.exclude_aids) ? input.exclude_aids : [];
  const pool = buildRealPool(data, baseId, input.item_level, excludedAids);
  return {
    base_id: baseId,
    item_level: input.item_level,
    pool,
    pool_totals: Object.fromEntries(Object.entries(pool).map(([side, entries]) => [
      side, entries.reduce((sum, entry) => sum + entry.weight, 0),
    ])),
  };
}


function readVariableStatement(source, name) {
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
  fail(`unclosed CoE variable declaration: ${name}`);
}


function validateSideRequirements(requirements, pool) {
  if (!Array.isArray(requirements)) fail("side requirements must be arrays");
  const byAid = new Map(pool.map((entry) => [entry.aid, entry]));
  return requirements.map((target) => {
    if (!target || typeof target !== "object") fail("side requirements must be target objects");
    const aid = String(target.aid);
    const entry = byAid.get(aid);
    if (!entry) fail(`required aid is absent from the CoE pool: ${aid}`);
    const weight = Number(target.weight);
    if (!Number.isFinite(weight) || weight <= 0 || weight > entry.weight) fail(`invalid selected-tier weight for ${aid}`);
    return { aid, weight };
  });
}


function runFinal(source, input, data) {
  if (!input.pools || typeof input.pools !== "object") fail("final requires pools");
  const pools = {
    prefix: validatePool(input.pools.prefix),
    suffix: validatePool(input.pools.suffix),
  };
  if (!input.requirements || typeof input.requirements !== "object") fail("final requires requirements");
  const requirements = {
    prefix: validateSideRequirements(input.requirements.prefix || [], pools.prefix),
    suffix: validateSideRequirements(input.requirements.suffix || [], pools.suffix),
  };
  const requiredSides = requirements.prefix.length + requirements.suffix.length;
  if (requiredSides === 0) fail("final requires at least one target");
  const reqMaxGrps = Number(input.req_max_groups);
  if (!Number.isInteger(reqMaxGrps) || reqMaxGrps < 1 || reqMaxGrps > 3) fail("req_max_groups must be 1, 2, or 3");
  const weight = Object.fromEntries(Object.entries(pools).map(([side, entries]) => [
    side, entries.reduce((sum, entry) => sum + entry.weight, 0),
  ]));
  const override = {
    weight,
    tiers: Object.fromEntries(Object.entries(pools).map(([side, entries]) => [
      side, entries.reduce((sum, entry) => sum + (entry.eligible_tiers ? entry.eligible_tiers.length : 1), 0),
    ])),
    mods: { prefix: pools.prefix.length, suffix: pools.suffix.length },
    modpool: pools,
    reqpool: requirements,
    rqgpool: {
      prefix: ["", ...requirements.prefix.map(({ aid }) => ({ affids: [aid] }))],
      suffix: ["", ...requirements.suffix.map(({ aid }) => ({ affids: [aid] }))],
    },
  };
  const { context, permutation } = makeContext(source, data);
  const final = findFunction(source, "poec_computeFinalProbsV2");
  Object.assign(context, {
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
    poec_cMethod: input.method || "chaos",
    poec_isFractured: 0,
    poec_nBase: { g: 0, i: 0 },
    reqMaxGrps,
    specialBases: { simplex: -1 },
    totReqAffixByType: { prefix: requirements.prefix.length, suffix: requirements.suffix.length },
  });
  vm.runInContext(readVariableStatement(source, "essNumProbs"), context, { timeout: SOURCE_TIMEOUT_MS });
  vm.runInContext(readVariableStatement(source, "affNumProbs"), context, { timeout: SOURCE_TIMEOUT_MS });
  vm.runInContext(findFunction(source, "perm").declaration, context, { timeout: SOURCE_TIMEOUT_MS });
  vm.runInContext(final.declaration, context, { timeout: SOURCE_TIMEOUT_MS });
  context.__override = override;
  vm.runInContext("__result = poec_computeFinalProbsV2(__override, false);", context, { timeout: SOURCE_TIMEOUT_MS });
  const probability = Number(context.__result);
  if (!Number.isFinite(probability)) fail("cached CoE final calculator returned no finite probability");
  return {
    method: "poec_computeFinalProbsV2",
    mode: "x",
    probability,
    pool_totals: weight,
    source_hash: sourceHash(source),
    source_ranges: {
      final: frozenLocation("poec_computeFinalProbsV2", final).source_range,
      permutations: frozenLocation("poec_computePermutationsV2", permutation).source_range,
    },
    source_line_ranges: {
      final: frozenLocation("poec_computeFinalProbsV2", final).source_line_range,
      permutations: frozenLocation("poec_computePermutationsV2", permutation).source_line_range,
    },
  };
}


function main() {
  const inputText = fs.readFileSync(0, "utf8");
  if (!inputText.trim()) fail("expected JSON on stdin");
  const input = JSON.parse(inputText);
  if (!input || typeof input.command !== "string") fail("command is required");
  const source = readSource(PACKAGE_PATH);
  if (input.command === "kernel") {
    process.stdout.write(`${JSON.stringify(runKernel(source, input, null))}\n`);
    return;
  }
  if (input.command === "real_pool") {
    process.stdout.write(`${JSON.stringify({
      ...reportRealPool(readData(), input),
      source_hashes: { package: sourceHash(source) },
    })}\n`);
    return;
  }
  if (input.command === "final") {
    process.stdout.write(`${JSON.stringify(runFinal(source, input, null))}\n`);
    return;
  }
  if (input.command === "real_final") {
    process.stdout.write(`${JSON.stringify(runRealFinal(source, readData(), input))}\n`);
    return;
  }
  if (input.command === "real_kernel") {
    process.stdout.write(`${JSON.stringify(runRealKernel(source, readData(), input))}\n`);
    return;
  }
  if (input.command === "batch") {
    if (!Array.isArray(input.cases) || input.cases.length === 0) fail("batch requires a non-empty cases array");
    const data = readData();
    const results = input.cases.map((caseInput) => {
      if (!caseInput || typeof caseInput !== "object") fail("batch cases must be objects");
      if (caseInput.command === "real_final") return runRealFinal(source, data, caseInput);
      if (caseInput.command === "real_kernel") return runRealKernel(source, data, caseInput);
      fail(`unsupported batch case command: ${caseInput.command}`);
    });
    process.stdout.write(`${JSON.stringify({
      node_version: process.version,
      source_hashes: { package: sourceHash(source), poec_data: readDataHash() },
      cases: results,
    })}\n`);
    return;
  }
  fail(`unsupported command: ${input.command}`);
}


try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
