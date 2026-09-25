// Run with: node qa/address-variants/address-router.test.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const R = require("./address-router.js");

const originals = [
  { line1: "1858 W Berteau Avenue", line2: "Apt GDN", city: "Chicago", state: "IL", zip: "60613" },
  { line1: "1860 W Belmont Ave", line2: "", city: "Chicago", state: "IL", zip: "60657" }
];

// Every generated variant routes back to 1858 W Berteau Avenue.
const rows = fs.readFileSync(path.join(__dirname, "variants_1858_W_Berteau.tsv"), "utf8")
  .trim().split("\n").slice(1).map((l) => l.split("\t"));
assert.strictEqual(rows.length, 25);
for (const [n, line1, line2, city, zip] of rows) {
  const r = R.route({ line1, line2, city, zip }, originals);
  assert.ok(r.routed, `variant ${n} (${line1}) was not routed: ${r.status}`);
  assert.strictEqual(r.original.line1, "1858 W Berteau Avenue", `variant ${n} routed to ${r.original.line1}`);
  assert.strictEqual(r.correctedLine1, "1858 W BERTEAU AVE");
}

// Unrelated addresses must not be routed.
for (const line1 of ["2200 N Clark St", "4 Privet Dr", "990 W Berteau Ave", "1858 W Belmont Ave"]) {
  const r = R.route({ line1, city: "Chicago", zip: "60613" }, originals);
  assert.ok(!r.routed || r.confidence < 75, `${line1} should not route confidently (${r.confidence})`);
}

assert.strictEqual(R.splitNumber("185B W Berteau").number, "1858");
assert.strictEqual(R.splitNumber("18 58 W Berteau").number, "1858");
assert.strictEqual(R.splitNumber("1858W Berteau").rest, "W BERTEAU");
assert.strictEqual(R.standardizeLine1("1858 West Berteau Avenue"), "1858 W BERTEAU AVE");
assert.strictEqual(R.standardizeLine2("Apartment gdn-12").text, "APT GDN 12");
assert.strictEqual(R.compareLine2("APT GDN-7", "Apt GDN").status, "Original unit + junk");

console.log("address-router: all tests passed");
