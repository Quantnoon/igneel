export async function fetchText(path, signal) {
  const separator = path.includes("?") ? "&" : "?";
  const response = await fetch(`${path}${separator}t=${Date.now()}`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    const error = new Error(`${path} returned HTTP ${response.status}.`);
    error.status = response.status;
    throw error;
  }
  return response.text();
}
