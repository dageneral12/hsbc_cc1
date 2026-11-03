// Helper for run_rpa_tests.py --cleanup. c8ctl has no "delete process-definition" command, so this
// reuses c8ctl's own bundled SDK client (same profile and credentials). Deletes every ACTIVE version
// of one processDefinitionId. Usage: node delete_definitions.mjs <c8ctl-package-root> <profile> <processDefinitionId>
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const [root, profile, pid] = process.argv.slice(2);
const { createClient } = await import(pathToFileURL(join(root, "dist/core/client.js")).href);
const c = createClient(profile);
const res = await c.searchProcessDefinitions({ filter: { processDefinitionId: pid }, page: { limit: 100 } }, { consistency: { waitUpToMs: 10000 } });
const live = (res.items ?? []).filter((d) => (d.state ?? "ACTIVE") === "ACTIVE");
let ok = 0, fail = 0;
for (const d of live) {
  try { await c.deleteResource({ resourceKey: String(d.processDefinitionKey) }); ok++; console.log(`deleted ${pid} v${d.version}`); }
  catch (e) { fail++; console.log(`FAILED ${pid} v${d.version}: ${String(e?.message ?? e).slice(0, 120)}`); }
}
console.log(`${pid}: ${live.length} live version(s), deleted ${ok}, failed ${fail}`);
process.exit(fail ? 1 : 0);
