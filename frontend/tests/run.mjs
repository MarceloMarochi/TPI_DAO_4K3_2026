// Compila las pruebas con TypeScript y usa el runner de Node, sin dependencias nuevas.
import ts from "typescript"
import { mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { spawnSync } from "node:child_process"

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)))
const output = mkdtempSync(path.join(root, ".test-build-"))
try {
  const tests = readdirSync(path.join(root, "tests")).filter((f) => f.endsWith(".test.ts"))
  const program = ts.createProgram(tests.map((f) => path.join(root, "tests", f)), {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
    moduleResolution: ts.ModuleResolutionKind.Node10, rootDir: root, outDir: output,
    strict: true, esModuleInterop: true, skipLibCheck: true, noEmitOnError: true,
  })
  const result = program.emit()
  const diagnostics = ts.getPreEmitDiagnostics(program).concat(result.diagnostics)
  if (diagnostics.length) {
    process.stderr.write(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCanonicalFileName: (f) => f, getCurrentDirectory: () => root, getNewLine: () => "\n",
    }))
    process.exitCode = 1
  } else {
    writeFileSync(path.join(output, "package.json"), JSON.stringify({ type: "commonjs" }))
    const run = spawnSync(process.execPath, ["--test", ...tests.map((f) =>
      path.join(output, "tests", f.replace(/\.ts$/, ".js")))], { stdio: "inherit", cwd: root })
    if (run.error) throw run.error
    process.exitCode = run.status ?? 1
  }
} finally {
  // Sólo se elimina la carpeta temporal creada por esta ejecución dentro del frontend.
  if (path.dirname(output) !== root || !path.basename(output).startsWith(".test-build-")) {
    throw new Error("Ruta temporal fuera del proyecto")
  }
  rmSync(output, { recursive: true, force: true })
}
