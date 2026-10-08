/** Check authored TypeScript syntax only; this is not a dependency-aware type check. */
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");

/** Prefer the project compiler; a supplied NODE_PATH can support syntax-only preflight. */
function loadCompiler() {
  const fromWeb = createRequire(path.resolve(__dirname, "../apps/web/package.json"));
  try { return fromWeb("typescript"); }
  catch (error) {
    if (error.code !== "MODULE_NOT_FOUND") throw error;
    return require("typescript");
  }
}
const ts = loadCompiler();
const root = path.resolve(__dirname, "../apps/web/src");

/** Enumerate source files without walking downloaded packages or generated builds. */
function sources(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? sources(file) : /\.tsx?$/.test(file) ? [file] : [];
  });
}

const files = sources(root);
const diagnostics = [];
for (const file of files) {
  // Parse with the real compiler, but do not pretend missing React types were checked.
  const parsed = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
  for (const problem of parsed.parseDiagnostics) {
    diagnostics.push({ file: path.relative(root, file), message: ts.flattenDiagnosticMessageText(problem.messageText, "\n") });
  }
}
console.log(JSON.stringify({ compiler: ts.version, files: files.length, scope: "syntax_only", diagnostics }, null, 2));
process.exitCode = diagnostics.length ? 1 : 0;
