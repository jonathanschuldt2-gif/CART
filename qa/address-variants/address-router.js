/*
 * Address router: normalizes messy address variants and routes each one back
 * to the original address it most likely came from.
 *
 * Rules come from USPS Publication 28 (see KNOWLEDGE_BASE.md):
 *   C1 street suffixes, C2 secondary unit designators, plus directionals.
 * Works in the browser (window.AddressRouter) and in Node (module.exports).
 */
(function (root) {
  "use strict";

  // ---- USPS Pub 28 C1: standard suffix -> accepted spellings ----
  var SUFFIXES = {
    AVE: ["AV", "AVE", "AVEN", "AVENU", "AVENUE", "AVN", "AVNUE"],
    BLVD: ["BLVD", "BOUL", "BOULEVARD", "BOULV"],
    CIR: ["CIR", "CIRC", "CIRCL", "CIRCLE", "CRCL", "CRCLE"],
    CT: ["COURT", "CT"],
    CV: ["COVE", "CV"],
    DR: ["DR", "DRIV", "DRIVE", "DRV"],
    EXPY: ["EXP", "EXPR", "EXPRESS", "EXPRESSWAY", "EXPW", "EXPY"],
    HWY: ["HIGHWAY", "HIGHWY", "HIWAY", "HIWY", "HWAY", "HWY"],
    LN: ["LANE", "LN"],
    PKWY: ["PARKWAY", "PARKWY", "PKWAY", "PKWY", "PKY"],
    PL: ["PL", "PLACE"],
    PLZ: ["PLAZA", "PLZ", "PLZA"],
    RD: ["RD", "ROAD"],
    SQ: ["SQ", "SQR", "SQRE", "SQU", "SQUARE"],
    ST: ["STREET", "STRT", "ST", "STR"],
    TER: ["TER", "TERR", "TERRACE"],
    TRL: ["TRAIL", "TRAILS", "TRL", "TRLS"],
    WAY: ["WAY", "WY"]
  };

  var DIRECTIONALS = {
    N: ["NORTH", "NTH", "N"],
    S: ["SOUTH", "STH", "S"],
    E: ["EAST", "E"],
    W: ["WEST", "WST", "W"],
    NE: ["NORTHEAST", "NE"],
    NW: ["NORTHWEST", "NW"],
    SE: ["SOUTHEAST", "SE"],
    SW: ["SOUTHWEST", "SW"]
  };

  // ---- USPS Pub 28 C2: secondary unit designators ----
  var UNIT_DESIGNATORS = {
    APARTMENT: "APT", APT: "APT", BASEMENT: "BSMT", BSMT: "BSMT",
    BUILDING: "BLDG", BLDG: "BLDG", DEPARTMENT: "DEPT", DEPT: "DEPT",
    FLOOR: "FL", FL: "FL", FRONT: "FRNT", FRNT: "FRNT", HANGAR: "HNGR",
    HNGR: "HNGR", KEY: "KEY", LOBBY: "LBBY", LBBY: "LBBY", LOT: "LOT",
    LOWER: "LOWR", LOWR: "LOWR", OFFICE: "OFC", OFC: "OFC",
    PENTHOUSE: "PH", PH: "PH", PIER: "PIER", REAR: "REAR", ROOM: "RM",
    RM: "RM", SIDE: "SIDE", SLIP: "SLIP", SPACE: "SPC", SPC: "SPC",
    STOP: "STOP", SUITE: "STE", STE: "STE", TRAILER: "TRLR", TRLR: "TRLR",
    UNIT: "UNIT", UPPER: "UPPR", UPPR: "UPPR", "#": "#"
  };

  // Letters commonly typed/OCR'd in place of digits.
  var DIGIT_LOOKALIKES = { B: "8", S: "5", I: "1", L: "1", O: "0", Z: "2", G: "6" };

  var SUFFIX_LOOKUP = {};
  Object.keys(SUFFIXES).forEach(function (std) {
    SUFFIXES[std].forEach(function (v) { SUFFIX_LOOKUP[v] = std; });
  });
  var DIR_LOOKUP = {};
  Object.keys(DIRECTIONALS).forEach(function (std) {
    DIRECTIONALS[std].forEach(function (v) { DIR_LOOKUP[v] = std; });
  });

  // Optimal string alignment distance (Levenshtein + adjacent transpositions).
  function editDistance(a, b) {
    var m = a.length, n = b.length, d = [], i, j;
    for (i = 0; i <= m; i++) { d[i] = [i]; }
    for (j = 0; j <= n; j++) { d[0][j] = j; }
    for (i = 1; i <= m; i++) {
      for (j = 1; j <= n; j++) {
        var cost = a[i - 1] === b[j - 1] ? 0 : 1;
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
        }
      }
    }
    return d[m][n];
  }

  function clean(s) {
    return String(s || "").toUpperCase().replace(/[.,]/g, " ").replace(/-/g, " ")
      .replace(/\s+/g, " ").trim();
  }

  function isDigitish(tok) {
    return /\d/.test(tok) && /^[0-9BSILOZG]+$/.test(tok);
  }

  function foldDigits(tok) {
    return tok.replace(/[BSILOZG]/g, function (c) { return DIGIT_LOOKALIKES[c]; });
  }

  // Split a Line 1 into its house number and the remaining text. Leading
  // digit-like tokens are merged ("18 58", "1-858") and look-alike letters are
  // folded to digits ("185B" -> 1858, "18S8" -> 1858, "I858" -> 1858).
  function splitNumber(line1) {
    var tokens = clean(line1).split(" ").filter(Boolean);
    var raw = "";
    while (tokens.length) {
      var t = tokens[0];
      if (isDigitish(t)) { raw += t; tokens.shift(); continue; }
      // "1858W" -> "1858" + "W"
      var m = t.match(/^(\d[0-9BSILOZG]*?)([A-Z]{1,})$/);
      if (m && !raw && /\d/.test(m[1])) { raw += m[1]; tokens[0] = m[2]; }
      break;
    }
    return { rawNumber: raw, number: foldDigits(raw), rest: tokens.join(" ") };
  }

  // Parse a clean original address into USPS components.
  function parseOriginal(line1) {
    var sp = splitNumber(line1);
    var words = sp.rest.split(" ").filter(Boolean);
    var dir = "", suffix = "";
    if (words.length > 1 && DIR_LOOKUP[words[0]]) { dir = DIR_LOOKUP[words.shift()]; }
    if (words.length > 1 && SUFFIX_LOOKUP[words[words.length - 1]]) {
      suffix = SUFFIX_LOOKUP[words.pop()];
    }
    return { number: sp.number, dir: dir, name: words.join(""), nameDisplay: words.join(" "), suffix: suffix };
  }

  // Standard USPS form of a Line 1 (best effort, no reference needed).
  function standardizeLine1(line1) {
    var sp = splitNumber(line1);
    var words = sp.rest.split(" ").filter(Boolean).map(function (w, i, arr) {
      if (i === 0 && arr.length > 1 && DIR_LOOKUP[w]) return DIR_LOOKUP[w];
      if (i === arr.length - 1 && arr.length > 1 && SUFFIX_LOOKUP[w]) return SUFFIX_LOOKUP[w];
      return w;
    });
    return [sp.number].concat(words).join(" ").trim();
  }

  function standardizeLine2(line2) {
    var tokens = clean(line2).replace(/#/g, " # ").split(" ").filter(Boolean);
    var designators = [], parts = [];
    tokens.forEach(function (t) {
      if (UNIT_DESIGNATORS[t]) { designators.push(UNIT_DESIGNATORS[t]); parts.push(UNIT_DESIGNATORS[t]); }
      else { parts.push(t); }
    });
    return { text: parts.join(" "), designators: designators, recognized: designators.length > 0 };
  }

  function compareLine2(variant2, original2) {
    var v = standardizeLine2(variant2), o = standardizeLine2(original2);
    var vKey = v.text.replace(/\s/g, ""), oKey = o.text.replace(/\s/g, "");
    var status;
    if (!vKey) status = "Missing";
    else if (vKey === oKey) status = "Same unit";
    else if (oKey && vKey.indexOf(oKey) === 0) status = "Original unit + junk";
    else status = "Different unit";
    return { normalized: v.text, recognized: v.recognized, designators: v.designators, status: status };
  }

  // Score how well a variant Line 1 matches one parsed original (0-100).
  function scoreLine1(variantLine1, orig) {
    var sp = splitNumber(variantLine1);
    var notes = [], penalty = 0;

    if (sp.rawNumber !== sp.number) notes.push("look-alike digits " + sp.rawNumber + "→" + sp.number);
    var nd = editDistance(sp.number, orig.number);
    if (nd === 1) { penalty += 20; notes.push("house number off by 1 edit"); }
    else if (nd > 1) { penalty += 60; notes.push("house number mismatch"); }

    var s = sp.rest.replace(/[^A-Z0-9]/g, "");
    if (orig.dir) {
      var dirForm = DIRECTIONALS[orig.dir].filter(function (f) { return s.indexOf(f) === 0; })
        .sort(function (a, b) { return b.length - a.length; })[0];
      if (dirForm) { s = s.slice(dirForm.length); }
      else { penalty += 10; notes.push("directional missing"); }
    }

    // Try every split point between street name and suffix; keep the cheapest.
    var forms = orig.suffix ? SUFFIXES[orig.suffix] : [];
    var best = null;
    for (var k = 0; k <= Math.min(s.length, 12); k++) {
      var head = s.slice(0, s.length - k), tail = s.slice(s.length - k);
      var sufCost;
      if (!orig.suffix) sufCost = k === 0 ? 0 : 99;
      else if (k === 0) sufCost = 15;
      else {
        var dmin = Math.min.apply(null, forms.map(function (f) { return editDistance(tail, f); }));
        sufCost = dmin === 0 ? 0 : dmin === 1 ? 5 : dmin === 2 ? 10 : 99;
      }
      var nameDist = editDistance(head, orig.name);
      var cost = nameDist * 8 + sufCost;
      if (!best || cost < best.cost) best = { cost: cost, nameDist: nameDist, sufCost: sufCost };
    }
    penalty += best.cost;
    if (best.nameDist) notes.push("street name " + best.nameDist + " edit" + (best.nameDist > 1 ? "s" : ""));
    // Too many edits relative to the name's length means a different street.
    if (best.nameDist > Math.max(2, Math.ceil(orig.name.length * 0.45))) {
      penalty += 40; notes.push("likely a different street");
    }
    if (best.sufCost === 15) notes.push("suffix missing");
    else if (best.sufCost > 0 && best.sufCost < 99) notes.push("suffix misspelled");

    return { confidence: Math.max(0, 100 - penalty), notes: notes };
  }

  function prepareOriginal(o, index) {
    return {
      id: index,
      line1: o.line1, line2: o.line2 || "", city: o.city || "", state: o.state || "", zip: o.zip || "",
      parsed: parseOriginal(o.line1),
      standard: standardizeLine1(o.line1)
    };
  }

  // Route one variant to the best original. Returns the match and diagnostics.
  function route(variant, originals) {
    var prepared = originals.map(function (o, i) { return o.parsed ? o : prepareOriginal(o, i); });
    var scored = prepared.map(function (o) {
      var s = scoreLine1(variant.line1, o.parsed);
      var conf = s.confidence, notes = s.notes.slice();
      if (variant.zip && o.zip && String(variant.zip).trim() !== String(o.zip).trim()) {
        conf -= 15; notes.push("zip differs");
      }
      if (variant.city && o.city && editDistance(clean(variant.city), clean(o.city)) > 2) {
        conf -= 15; notes.push("city differs");
      }
      return { original: o, confidence: Math.max(0, conf), notes: notes };
    }).sort(function (a, b) { return b.confidence - a.confidence; });

    var top = scored[0];
    if (!top) return { status: "No originals", confidence: 0, original: null, notes: [] };

    var standardized = standardizeLine1(variant.line1);
    var status;
    if (top.confidence === 100 && clean(variant.line1) === clean(top.original.line1)) status = "Exact";
    else if (top.confidence === 100) status = "Normalized";
    else if (top.confidence >= 75) status = "Fuzzy match";
    else if (top.confidence >= 55) status = "Needs review";
    else status = "Unmatched";

    if (top.confidence === 100 && status === "Normalized") top.notes.push("formatting/suffix normalized");

    var ambiguous = scored[1] && scored[1].confidence >= 55 && top.confidence - scored[1].confidence < 10;
    if (ambiguous && status !== "Unmatched") { status = "Needs review"; top.notes.push("close to another original"); }

    return {
      status: status,
      routed: status !== "Unmatched",
      confidence: top.confidence,
      original: top.original,
      standardizedLine1: standardized,
      correctedLine1: status !== "Unmatched" ? top.original.standard : "",
      line2: compareLine2(variant.line2, top.original.line2),
      notes: top.notes
    };
  }

  var api = {
    SUFFIXES: SUFFIXES, DIRECTIONALS: DIRECTIONALS, UNIT_DESIGNATORS: UNIT_DESIGNATORS,
    editDistance: editDistance, splitNumber: splitNumber, parseOriginal: parseOriginal,
    standardizeLine1: standardizeLine1, standardizeLine2: standardizeLine2,
    compareLine2: compareLine2, prepareOriginal: prepareOriginal, route: route
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.AddressRouter = api;
})(typeof window !== "undefined" ? window : this);
