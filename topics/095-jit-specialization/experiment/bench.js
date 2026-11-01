"use strict";
const assert = require("node:assert/strict");
const workload = process.argv[2] || "stable";
assert(["stable", "shift", "mixed"].includes(workload));
const n = 8192, warmups = 128, repeats = 256;
function makeA(i) { return {x: i & 255, y: 1}; }
function makeB(i) { return {y: 1, x: i & 255}; }
const stable = Array.from({length: n}, (_, i) => makeA(i));
const other = Array.from({length: n}, (_, i) =>
  workload === "mixed" && i % 2 === 0 ? makeA(i) : makeB(i));
const train = workload === "mixed" ? other : stable;
const rows = workload === "stable" ? stable : other;
function sumRows(a) {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += a[i].x;
  return sum;
}
const expected = n / 256 * (255 * 256 / 2);
let start = process.hrtime.bigint();
let cold = sumRows(train);
const coldNs = Number(process.hrtime.bigint() - start);
assert.equal(cold, expected);
for (let i = 0; i < warmups; i++) assert.equal(sumRows(train), expected);
start = process.hrtime.bigint();
const transition = sumRows(rows);
const transitionNs = Number(process.hrtime.bigint() - start);
assert.equal(transition, expected);
let checksum = 0;
start = process.hrtime.bigint();
for (let i = 0; i < repeats; i++) checksum += sumRows(rows);
const steadyNs = Number(process.hrtime.bigint() - start);
assert.equal(checksum, expected * repeats);
console.log(JSON.stringify({workload, n, warmups, repeats, coldNs,
  transitionNs, steadyNs, checksum, node: process.version, v8: process.versions.v8}));
