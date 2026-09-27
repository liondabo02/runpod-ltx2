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

## OpenVoice execution guard

`ahos.voice_audio_quality` adds an earlier machine gate at provider execution
time. Approved OpenVoice references are checked for PCM format, sample rate,
signal level, clipping and silence. A valid reference shorter than eight seconds
is extended deterministically by repeating only its own approved samples; the
system never substitutes another speaker. Returned speech is checked again
before it is written to the episode directory, and the measurements plus whether
the reference was extended are recorded in `tts-evidence.json`.

Provider or signal failures remain fail-closed. The studio executor owns the
bounded stage retry count, while every paid attempt still requires the existing
owner, execution and paid-provider gates.
