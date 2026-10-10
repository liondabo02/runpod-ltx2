# Department research handoff

Department runtime reads optional saved research artifacts from `research-results`
next to its department runtime directory. No network request occurs during draft
production. Save Vane search output there with `ahos.vane_research search --output`
or successful public-search bridge output there with the bridge's `--output`.

Only `ahos.vane-research.v1` and successful `ahos.upstream-result.v1` public-search
records with matching canonical content hashes are included. Installation doctor
reports, failed searches, unknown schemas, oversized files, symlinks and junctions
are excluded. Reads are limited to 128 directory entries, five accepted artifacts,
128 KiB total bytes and 12,000 JSON prompt characters. Public source excerpts are
truncated to fit; the original owner objective is unchanged.

The prompt labels this evidence as untrusted data, not instructions or verified
claims. Draft artifacts record the supplied research hashes for provenance. Hashes
detect content changes, not publisher identity or correctness. Existing draft,
owner approval and execution gates remain in place. Missing research is optional
and does not block department drafts.
