# Music and SFX supervision

`ahos.music_sfx_supervision` creates a deterministic production cue sheet and
rights manifest. It does not generate, download, upload, publish, or purchase
media.

Every sound asset records a content hash, private production URI, evidence URI,
license identifier, rights holder, commercial-use confirmation, attribution,
and AI-generator identity when applicable. Every cue records its scene, exact
timeline range, creative purpose, dialogue ducking, child-safety review, and
creative review.

The package fails closed for invalid timing, missing assets, kind mismatches,
overlapping music, unsafe ducking values, missing commercial rights, missing
human review, or absent music/SFX. `package_hash` makes the approved plan
traceable and reproducible.
