from ahos.release_manifest import ReleaseAsset, ReleaseManifestBuilder


def _asset(path, kind, language=None):
    return ReleaseAsset(path=path, sha256="a" * 64, size_bytes=100, kind=kind, language=language)


def test_release_manifest_is_signed_and_verifiable():
    builder = ReleaseManifestBuilder()
    manifest = builder.build(
        episode_id="S01E001",
        commit_sha="abc",
        assets=(
            _asset("master.mkv", "master"),
            _asset("tr.wav", "audio", "tr"),
            _asset("ku.wav", "audio", "ku-latn"),
        ),
        delivery_evidence_hash="b" * 64,
        execution_ledger_hash="c" * 64,
        owner_release_hash="d" * 64,
        signing_key=b"x" * 32,
    )
    assert manifest.signature_algorithm == "HMAC-SHA256"
    assert builder.verify_signature(manifest, signing_key=b"x" * 32) is True


def test_release_manifest_can_be_built_unsigned_but_marks_that_state():
    manifest = ReleaseManifestBuilder().build(
        episode_id="S01E001",
        commit_sha="abc",
        assets=(_asset("master.mkv", "master"),),
        delivery_evidence_hash="b" * 64,
        execution_ledger_hash="c" * 64,
        owner_release_hash="d" * 64,
    )
    assert manifest.signature is None
    assert manifest.signature_algorithm is None
