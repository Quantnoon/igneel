/** Split CSV text into records while keeping quoted newlines inside their record. */
export function splitCsvRecords(text) {
  const records = [];
  let start = 0;
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === "\n" && !quoted) {
      records.push(text.slice(start, index));
      start = index + 1;
    }
  }

  if (start < text.length) records.push(text.slice(start));
  if (records.length > 0 && records.at(-1) === "") records.pop();
  if (quoted) throw new Error("CSV contains an unterminated quoted field.");
  return records;
}

export function chunkCsvText(text, chunkSize = 1000) {
  if (!Number.isInteger(chunkSize) || chunkSize < 1) {
    throw new Error("CSV chunk size must be a positive integer.");
  }
  const [header, ...rows] = splitCsvRecords(text);
  if (header === undefined) return [];
  const chunks = [];
  for (let offset = 0; offset < rows.length || (rows.length === 0 && offset === 0); offset += chunkSize) {
    chunks.push([header, ...rows.slice(offset, offset + chunkSize)].join("\n"));
    if (rows.length === 0) break;
  }
  return chunks;
}

export function prependCsvChunk(olderCsv, newerCsv) {
  const olderRecords = splitCsvRecords(olderCsv);
  const newerRecords = splitCsvRecords(newerCsv);
  if (olderRecords.length === 0) return newerCsv;
  if (newerRecords.length === 0) return olderCsv;
  if (olderRecords[0].replace(/^\uFEFF/, "") !== newerRecords[0].replace(/^\uFEFF/, "")) {
    throw new Error("CSV chunks have incompatible headers.");
  }
  return [...olderRecords, ...newerRecords.slice(1)].join("\n");
}
