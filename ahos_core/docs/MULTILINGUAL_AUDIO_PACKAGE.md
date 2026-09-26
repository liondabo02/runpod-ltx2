# Multilingual audio release package

`ahos.multilingual_audio_package` verifies the final audio deliverables before
episode assembly. It requires exactly one final mix and subtitle asset for each
required language, canonical voice enrollment for every speaking character in
every language, duration agreement, shared music and SFX stems, and SHA-256
provenance for every asset.

The default required set is Turkish, Kurdish (Kurmanji in the Latin script,
normalized BCP 47 tag `ku-latn`), German, Arabic, French, Spanish, and English.
Missing, duplicate, unapproved, or duration-mismatched material fails closed.
Kurdish delivery may use rights-cleared human performance; no unverified TTS
provider is treated as Kurdish-capable. The component only creates a
deterministic manifest; it performs no generation, network access, paid
execution, or publishing.

## Acceptance integration

`StudioAcceptancePreflight` requires this package as evidence. Paid execution
remains blocked when the package is absent, belongs to another episode, lacks a
required language deliverable or voice enrollment, or lacks the shared music
and SFX stems. The check is fail-closed and performs no external action.
