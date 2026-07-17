import { spawn } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const generatedConfigPaths = ["next-env.d.ts", "tsconfig.json"];
const originalConfigs = new Map(
  await Promise.all(
    generatedConfigPaths.map(async (relativePath) => [
      relativePath,
      await readFile(path.join(webRoot, relativePath), "utf8"),
    ]),
  ),
);

const nextBinary = path.join(
  webRoot,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "next.cmd" : "next",
);

let exitCode = 1;
try {
  exitCode = await new Promise((resolve, reject) => {
    const child = spawn(nextBinary, ["build"], {
      cwd: webRoot,
      env: { ...process.env, NEXT_DIST_DIR: ".next-build" },
      stdio: "inherit",
    });
    child.once("error", reject);
    child.once("exit", (code) => resolve(code ?? 1));
  });
} finally {
  await Promise.all(
    [...originalConfigs].map(([relativePath, content]) =>
      writeFile(path.join(webRoot, relativePath), content, "utf8"),
    ),
  );
}

process.exitCode = exitCode;
