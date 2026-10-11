# Professional episode delivery evidence

`EpisodeDeliveryGate` is the final cross-artifact validation layer for an episode
release candidate. It does not synthesize, render, upload, or publish media.

The gate fails closed unless all of the following agree:

- the audio package and protected acceptance preflight identify the same episode;
- the exact production language set is `tr`, `ku-latn`, `de`, `ar`, `fr`, `es`, `en`;
- every speaking character has rendered-voice QA evidence in every language;
- every language has one duration-matched final mix and one subtitle asset;
- music and SFX stems are present and package assets have SHA-256 identities;
- Kurmanji passed native terminology, pronunciation, timing, child-register, and
  Southeast regional coverage review;
- acceptance is approved for paid execution while automatic publishing remains off;
- the picture master has a canonical SHA-256 identity.

The output contains a deterministic evidence hash binding the episode, cast,
languages, picture master, multilingual package, voice report, Kurmanji report,
and individual gate results. A downstream publisher should accept only reports
where `release_candidate_ready` is `true`, then require a separate explicit
owner-controlled publication action.
