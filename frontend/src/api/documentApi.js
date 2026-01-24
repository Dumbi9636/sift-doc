import API_BASE from "./client";

export async function uploadDocument({ file, model, mode, maxChars, numPredict }) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("model", model);
  fd.append("mode", mode);
  fd.append("max_chars", String(maxChars));
  fd.append("num_predict", String(numPredict));
  // api 확장 시
  // fd.append("top_p", "0.9");
  // fd.append("temperature", "0.0");
  // fd.append("truncate_extract", "true");
  // fd.append("include_text", "false");

  const res = await fetch(`${API_BASE}/api/pipeline/txt`, {
    method: "POST",
    body: fd,
  });

  const json = await res.json();
  if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
  return json;
}