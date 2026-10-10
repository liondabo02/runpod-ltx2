# Local Ollama coding worker

This adapter uses the official Ollama `/api/chat` JSON API on fixed loopback
`http://127.0.0.1:11434`. It sends no OpenRouter key, ignores HTTP proxy settings,
rejects redirects and permits only the explicitly selected local
`qwen2.5-coder:7b` tag. It does not install dependencies or download models.
Official protocol: https://docs.ollama.com/api/chat

It receives the existing AHOS worker prompt on stdin and reads bounded repository
context. Exact JSON edits are checked with the existing scoped edit validator
before any file is written. Invalid edits get at most two repair attempts by
default. Incomplete output fails without writes. The coding supervisor still
performs the task's approved test commands, retains prior test failure feedback,
and produces an owner-review patch. The builder never commits or pushes.

## Windows verification after model download

Run from an existing core checkout:

```powershell
$core = 'C:\actions-runner\_work\runpod-ltx2\ahos-final-fix\ahos_core'
$python = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\.venv\Scripts\python.exe'
Set-Location $core
& $python -m ahos.ollama_coding_builder --status
```

`model_available: true` only proves installation/service availability; it does
not prove successful coding. A real scoped task must pass tests and produce an
owner-review patch before claiming coding works.

## Existing company-service integration

In the existing service JSON's `coding_supervisor` object set `builder_command`
to an argv array containing the Python executable, the **absolute path** to
`ahos_core/ahos/ollama_coding_builder.py`, and optional generation flags:

```json
["C:\\actions-runner\\_work\\runpod-ltx2\\runpod-ltx2\\control_plane_v2\\.venv\\Scripts\\python.exe",
 "C:\\actions-runner\\_work\\runpod-ltx2\\ahos-final-fix\\ahos_core\\ahos\\ollama_coding_builder.py",
 "--timeout-seconds", "600", "--context-chars", "16000"]
```

Preserve all other configuration, queue and test allowlists. Restart the existing
company service once to load this coding builder: its coding configuration is
read at startup. Do not run a second supervisor concurrently on the same queue.
Existing provider cooldowns remain in effect; changing a builder does not erase
queued task evidence or reset cooldowns automatically.

## Limits and acceptance

CPU speed, RAM usage and real model edit quality have not been measured on the
owner's computer. Local request timeout defaults to 600 seconds per generation;
two generations may take 1200 seconds plus tests. Context is bounded to 16000
characters, generation to 4096 tokens and model context to 8192 tokens; these are
initial resource settings, not a reduction of task requirements. Broad tasks may
need better context selection or another suitable model later. No automatic
cloud fallback exists. This adapter does not add a dashboard indicator or
activate other departments. Continuous work still requires the actual company
service to be running on an awake computer.

### Failed validation diagnostics

Failed local generations now report a bounded gate category (scope, exact-search,
missing-file, Python syntax, existing tests, public definitions, or response format).
Model-provided paths and repository contents are not included in that diagnostic.
Syntax errors enter the same bounded repair loop; all edits still validate before writes.
A diagnostic identifies a rejected attempt, not successful coding execution. Do not
blindly retry an exhausted task before reviewing its reported gate.

### Exact-search repair context

When an exact edit fails, the local repair request receives bounded excerpts from the actual allowed target files, including targets omitted from the initial context budget. Similarity only selects a useful excerpt; writes still require an exact unique match and all existing validation gates. Out-of-scope and symlink targets are not read. The repair returns the complete corrected edit result before any write.

### Repository path inventory

Initial local requests include a bounded inventory of existing tracked files within allowed paths, excluding symlinks, missing targets and untracked data. Missing-file repairs receive this inventory again with explicit repository-root path and new-file instructions. No nonexistent edit is silently converted to a new file; the model must return a valid complete result and all validation gates remain in force. An inventory read failure stops the builder.
