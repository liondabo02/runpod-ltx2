# Multilingual audio release package

`ahos.multilingual_audio_package` verifies the final audio deliverables before
episode assembly. It requires exactly one final mix and subtitle asset for each
required language, canonical voice enrollment for every speaking character in
every language, duration agreement, shared music and SFX stems, and SHA-256
provenance for every asset.

The default required set is Turkish, German, Arabic, French, Spanish, and
English. Missing, duplicate, unapproved, or duration-mismatched material fails
closed. The component only creates a deterministic manifest; it performs no
generation, network access, paid execution, or publishing.
