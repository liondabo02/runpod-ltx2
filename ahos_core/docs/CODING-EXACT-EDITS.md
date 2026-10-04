# Coding builder exact edits

The OpenRouter builder requests JSON `edits` for existing files and `files` for new files. Each exact edit contains `path`, a nonempty `search` string matching exactly once, and `replace`. Multiple edits to a file run in order. Existing full-file responses remain supported.

All JSON edits are prepared before writing. Scope, resolved paths, Python syntax, public definitions and unchanged existing test definitions are checked. In Git worktrees, definition/test evidence comes from HEAD, so an already damaged retry candidate cannot redefine the baseline. Validation errors return to the model repair loop with their diagnostic. New tests can be added in separate files or appended without rewriting existing definitions. Git diff responses retain the existing patch and worker gates.

These checks do not prove behavioral correctness. The worker still runs approved tests and requires owner approval before integration. No feature scope, owner, payment or publishing gate is relaxed.

## Invalid provider response diagnostics

The coding builder writes `<attempt-worktree-name>.coding-diagnostics.json` beside the isolated
attempt worktree (outside candidate source files) when response parsing or edit validation fails. It keeps at
most eight failed response records from the current request, each with at most
2,000 characters of response text. Records show the selected model, attempt
number, exception type, original content length, empty-content indicator,
whitelisted finish reason, and whether reasoning was present. Reasoning text,
repository prompts, authorization headers and HTTP error bodies are not saved.
Known credential environment values, bearer tokens, common API token prefixes,
credential assignments and URL passwords are redacted before truncation.
The artifact is local diagnostic evidence, never candidate source code or an
owner approval. Diagnostic write failure does not bypass validation or change
retry behavior. A failed response still fails the same deterministic gates;
this instrumentation does not itself fix the System Health implementation.
