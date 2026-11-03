// Fetches the OpenAPI schema from a running backend and stores it next to the
// typed client. The contract test then verifies the two stay aligned.
import { writeFile } from "node:fs/promises";

const BASE = process.env.RELAY_API_URL ?? "http://127.0.0.1:8000";
const response = await fetch(`${BASE}/openapi.json`);
if (!response.ok) {
  console.error(`sync-openapi: ${BASE}/openapi.json returned ${response.status}`);
  console.error("Start the backend first (make backend-dev from the repo root).");
  process.exit(1);
}
const schema = await response.json();
await writeFile(
  new URL("../src/features/review/openapi.json", import.meta.url),
  JSON.stringify(schema, null, 2) + "\n",
  "utf8",
);
console.log(`sync-openapi: wrote schema for ${schema.info?.title ?? "API"} ${schema.info?.version ?? ""}`);
