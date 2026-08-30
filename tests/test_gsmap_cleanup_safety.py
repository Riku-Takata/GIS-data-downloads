from pathlib import Path

import pytest

from scripts.verify_and_cleanup_gsmap_sources import _assert_safe_target


def test_cleanup_target_accepts_only_product_standard_tree(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    target = downloads / "gsmap" / "standard"
    target.mkdir(parents=True)

    assert _assert_safe_target(target, downloads) == target.resolve()


@pytest.mark.parametrize(
    "relative",
    [".", "gsmap", "gsmap/other", "gsmap/standard/child", "../outside/standard"],
)
def test_cleanup_target_rejects_broad_or_unexpected_paths(
    tmp_path: Path, relative: str
) -> None:
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    with pytest.raises(ValueError, match="unsafe cleanup target"):
        _assert_safe_target(downloads / relative, downloads)
