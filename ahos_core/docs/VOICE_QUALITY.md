# Professional rendered-voice quality gate

`ahos.voice_quality` validates the actual WAV bytes delivered for an episode.
It measures sample rate, sample depth, duration, peak level, RMS level, clipping,
silence, DC offset, and SHA-256 provenance without network calls or paid work.

Objective signal analysis does not pretend to replace creative listening. Every
clip also requires explicit transcript verification, native-language listening,
age/character-fit approval, and canonical speaker-similarity approval. Missing
character/language coverage or any failed check blocks studio acceptance.

The gate accepts PCM WAV only, requires at least 24 kHz/16-bit audio, and uses
conservative dialogue thresholds. It never repairs, normalizes, approves,
synthesizes, uploads, or publishes audio automatically.
