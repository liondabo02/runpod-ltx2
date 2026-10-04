# Coding builder exact edits

The OpenRouter builder requests JSON `edits` for existing files and `files` for new files. Each exact edit contains `path`, a nonempty `search` string matching exactly once, and `replace`. Multiple edits to a file run in order. Existing full-file responses remain supported.

All JSON edits are prepared before writing. Scope, resolved paths, Python syntax, public definitions and unchanged existing test definitions are checked. In Git worktrees, definition/test evidence comes from HEAD, so an already damaged retry candidate cannot redefine the baseline. Validation errors return to the model repair loop with their diagnostic. New tests can be added in separate files or appended without rewriting existing definitions. Git diff responses retain the existing patch and worker gates.

These checks do not prove behavioral correctness. The worker still runs approved tests and requires owner approval before integration. No feature scope, owner, payment or publishing gate is relaxed.
