# Audio post-production planning

`ahos.audio_postproduction` provides the deterministic, local-only planning
stage between localized dialogue renders and episode assembly.

It produces:

- frame-independent subtitle timing and UTF-8 SRT files;
- per-line dub-length decisions with conservative fitting bounds;
- a fail-closed rewrite/rerecord decision for unsafe duration mismatches;
- a child-voice rule that forbids automatic time stretching;
- dialogue, music, SFX, and master loudness/peak/ducking instructions;
- deterministic package hashes and explicit QA results.

The planner performs no synthesis, rendering, network access, paid API call,
or publishing. A package is ready only when every timeline, subtitle, dub-fit,
child-voice, and mix-target check passes. Human speaker-similarity approval and
canonical voice enrollment remain separate required gates.
