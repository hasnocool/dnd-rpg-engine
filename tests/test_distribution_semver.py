from dnd_rpg_engine.distribution.packages import ContentDistributionIndex, PackageRelease, SemanticVersion


def test_stable_semver_outranks_prerelease_and_numeric_identifiers_order_correctly() -> None:
    assert SemanticVersion.parse("1.0.0-alpha.2") < SemanticVersion.parse("1.0.0-alpha.10")
    assert SemanticVersion.parse("1.0.0-alpha.10") < SemanticVersion.parse("1.0.0-beta")
    assert SemanticVersion.parse("1.0.0-rc.1") < SemanticVersion.parse("1.0.0")

    index = ContentDistributionIndex()
    index.publish(PackageRelease(package_id="demo", version="1.0.0-rc.1", content_hash="a" * 64))
    index.publish(PackageRelease(package_id="demo", version="1.0.0", content_hash="b" * 64))
    assert index.latest("demo").version == "1.0.0"
    assert index.versions("demo") == ["1.0.0", "1.0.0-rc.1"]
