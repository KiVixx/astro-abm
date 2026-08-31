import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const nextBinary = path.join(
  webRoot,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "next.cmd" : "next",
);

const child = spawn(nextBinary, ["start", ...process.argv.slice(2)], {
  cwd: webRoot,
  env: { ...process.env, NEXT_DIST_DIR: ".next-build" },
  stdio: "inherit",
});

child.once("error", (error) => {
  console.error(`Unable to start Astro ABM Web: ${error.message}`);
  process.exitCode = 1;
});

child.once("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});
