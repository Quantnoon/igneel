import assert from "node:assert/strict";
import { test } from "vitest";

import { chunkCsvText, prependCsvChunk, splitCsvRecords } from "./csv-records.js";

const csvRow = (index) => `${index},"value ${index}"`;

test("splits short CSV files into one header-bearing chunk", () => {
  const chunks = chunkCsvText(`time,value\n${csvRow(1)}\n${csvRow(2)}\n`);
  assert.deepEqual(chunks, [`time,value\n${csvRow(1)}\n${csvRow(2)}`]);
});

test("splits exact multiples and remaining rows into chunks of the requested size", () => {
  const rows = Array.from({ length: 2003 }, (_, index) => csvRow(index));
  const chunks = chunkCsvText(["time,value", ...rows].join("\n"), 1000);
  assert.deepEqual(chunks.map((chunk) => splitCsvRecords(chunk).length), [1001, 1001, 4]);
  assert.equal(splitCsvRecords(chunks[0])[1], csvRow(0));
  assert.equal(splitCsvRecords(chunks[2]).at(-1), csvRow(2002));
});

test("keeps quoted newlines inside one CSV row and removes repeated headers when prepending", () => {
  const first = 'time,value\n1,"line one\nline two"\n2,old';
  const second = 'time,value\n3,new\n4,newest';
  assert.equal(splitCsvRecords(first).length, 3);
  assert.equal(prependCsvChunk(first, second), 'time,value\n1,"line one\nline two"\n2,old\n3,new\n4,newest');
});
