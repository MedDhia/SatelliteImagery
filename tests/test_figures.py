"""Gallery tests: the set catalogue, the size policy and the generated index.

Synthetic PNGs throughout, so these run without GADM, without rasters and
without having rendered anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

from satimg import figures as F  # noqa: E402


def make_png(path: Path, size=(40, 20), color=(10, 20, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (*color, 255)).save(path)
    return path


# --------------------------------------------------------------------------- #
# the catalogue
# --------------------------------------------------------------------------- #
def test_every_set_has_a_unique_key_and_destination():
    keys = [s.key for s in F.FIGURE_SETS]
    dests = [s.dest for s in F.FIGURE_SETS]
    assert len(set(keys)) == len(keys)
    assert len(set(dests)) == len(dests)


def test_every_set_files_under_a_known_group():
    assert {s.group for s in F.FIGURE_SETS} <= set(F.GROUP_ORDER)


def test_only_summary_figures_keep_native_pixels():
    # The per-year series is what the size cap exists for; if a browsing set
    # ever turns full_res the gallery quietly grows by hundreds of megabytes.
    for figure_set in F.FIGURE_SETS:
        assert figure_set.full_res == (figure_set.group == F.GROUP_SUMMARY)


def test_default_palette_runs_map_to_unsuffixed_directories():
    # The renderer wrote "png" and "absolute" for its default palette; the
    # gallery has to name those inferno and ylorrd explicitly.
    assert F.set_by_key("tun-raster-inferno-adm1").source.startswith("regions/TUN/png/")
    assert F.set_by_key("panel-choropleth-ylorrd").source == (
        "regions/TUN/choropleth/panel/*.png"
    )
    assert "-magma" in F.set_by_key("tun-raster-magma-adm1").source
    assert "-cividis" in F.set_by_key("tun-choropleth-cividis-adm1-absolute").source


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        F.set_by_key("no-such-set")


def test_palette_appears_in_the_destination_path():
    # Three raster runs write the same filenames; only the directory tells them
    # apart, so a missing palette level would silently overwrite.
    dests = {F.set_by_key(f"tun-raster-{p}-adm2").dest for p, _ in F.RASTER_PALETTES}
    assert len(dests) == len(F.RASTER_PALETTES)


# --------------------------------------------------------------------------- #
# size policy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "size,max_px,expected",
    [
        ((3832, 2046), 1200, (1200, 641)),  # wide: width binds
        ((1600, 4066), 1200, (472, 1200)),  # tall: height binds
        ((800, 600), 1200, (800, 600)),  # already small: untouched
        ((800, 600), None, (800, 600)),  # no cap
        ((800, 600), 0, (800, 600)),  # --max-px 0
        ((10, 4000), 100, (1, 100)),  # never rounds a side to zero
    ],
)
def test_web_size(size, max_px, expected):
    assert F.web_size(size, max_px) == expected


def test_web_size_never_upscales():
    assert F.web_size((300, 200), 4000) == (300, 200)


def test_convert_png_downscales_and_palettizes(tmp_path):
    src = make_png(tmp_path / "src.png", size=(2400, 1200))
    out = F.convert_png(src, tmp_path / "out" / "src.png", max_px=600)
    with Image.open(out) as img:
        assert img.size == (600, 300)
        assert img.mode == "P"  # 256-colour palette, not 24-bit RGBA


def test_convert_png_keeps_native_size_without_a_cap(tmp_path):
    src = make_png(tmp_path / "src.png", size=(2400, 1200))
    out = F.convert_png(src, tmp_path / "out.png", max_px=None)
    with Image.open(out) as img:
        assert img.size == (2400, 1200)


def test_convert_png_preserves_flat_colour_exactly(tmp_path):
    # Quantization is only acceptable because these renders use few distinct
    # colours; a flat fill must come back bit-identical, not merely close.
    src = make_png(tmp_path / "src.png", size=(64, 64), color=(203, 24, 29))
    out = F.convert_png(src, tmp_path / "out.png", max_px=None)
    with Image.open(out) as img:
        assert img.convert("RGB").getpixel((10, 10)) == (203, 24, 29)


# --------------------------------------------------------------------------- #
# planning and building
# --------------------------------------------------------------------------- #
@pytest.fixture
def source(tmp_path):
    """A miniature rendered tree: two years of one set, plus a panel."""
    root = tmp_path / "data"
    for year in (1992, 1993):
        make_png(root / "regions/TUN/png/adm1" / f"LACC_{year}_TUN_adm1.png")
    make_png(root / "regions/TUN/panel/TUN_adm1_1992-1993.png", size=(500, 400))
    return root


def test_plan_maps_sources_into_the_gallery(source, tmp_path):
    planned = F.plan(source, tmp_path / "figures")
    assert len(planned) == 3
    dests = {p.dest.relative_to(tmp_path / "figures").as_posix() for p in planned}
    assert dests == {
        "tunisia/raster/inferno/adm1/LACC_1992_TUN_adm1.png",
        "tunisia/raster/inferno/adm1/LACC_1993_TUN_adm1.png",
        "panels/raster/inferno/TUN_adm1_1992-1993.png",
    }


def test_plan_is_empty_rather_than_failing_on_a_bare_tree(tmp_path):
    assert F.plan(tmp_path / "nothing", tmp_path / "figures") == []


def test_plan_never_collides_two_sources_on_one_destination(source, tmp_path):
    planned = F.plan(source, tmp_path / "figures")
    assert len({p.dest for p in planned}) == len(planned)


def test_planned_max_px_follows_full_res(source, tmp_path):
    by_name = {p.dest.name: p for p in F.plan(source, tmp_path / "figures")}
    assert by_name["LACC_1992_TUN_adm1.png"].max_px == F.WEB_MAX_PX
    assert by_name["TUN_adm1_1992-1993.png"].max_px is None


def test_build_writes_then_skips(source, tmp_path):
    dest = tmp_path / "figures"
    first = F.build(source, dest)
    assert len(first.written) == 3 and not first.skipped
    assert all(p.exists() for p in first.written)

    second = F.build(source, dest)
    assert not second.written and len(second.skipped) == 3

    third = F.build(source, dest, overwrite=True)
    assert len(third.written) == 3


def test_build_reports_progress_per_file(source, tmp_path):
    seen = []
    F.build(
        source, tmp_path / "figures", on_file=lambda item, fresh: seen.append(fresh)
    )
    assert seen == [True, True, True]


def test_build_groups_by_set(source, tmp_path):
    result = F.build(source, tmp_path / "figures")
    assert len(result.by_set["tun-raster-inferno-adm1"]) == 2
    assert len(result.by_set["panel-raster-inferno"]) == 1
    assert result.total_bytes > 0


# --------------------------------------------------------------------------- #
# the index
# --------------------------------------------------------------------------- #
def test_index_lists_only_sets_that_produced_files(source, tmp_path):
    dest = tmp_path / "figures"
    index = F.write_index(F.build(source, dest), dest)
    text = index.read_text(encoding="utf-8")

    assert index.name == "README.md"
    assert "tunisia/raster/inferno/adm1/LACC_1992_TUN_adm1.png" in text
    # Nothing was rendered for these, so they must not appear as dead links.
    assert "global/adm0" not in text
    assert "cividis" not in text


def test_index_links_resolve_to_files_on_disk(source, tmp_path):
    import re

    dest = tmp_path / "figures"
    index = F.write_index(F.build(source, dest), dest)
    targets = re.findall(r"\]\(([^)]+\.png)\)", index.read_text(encoding="utf-8"))
    assert targets
    for target in targets:
        assert (dest / target).exists(), target


def test_index_carries_the_licence_warning(source, tmp_path):
    dest = tmp_path / "figures"
    text = F.write_index(F.build(source, dest), dest).read_text(encoding="utf-8")
    assert "GADM" in text
    assert "non-commercial" in text
    assert "MIT" in text


def test_index_labels_year_series_by_year(source, tmp_path):
    dest = tmp_path / "figures"
    text = F.write_index(F.build(source, dest), dest).read_text(encoding="utf-8")
    assert "[1992](tunisia/raster/inferno/adm1/LACC_1992_TUN_adm1.png)" in text


def test_year_of_falls_back_to_the_stem():
    assert F._year_of("LACC_1992_TUN_adm1.png") == "1992"
    assert F._year_of("TUN_inequality_series.png") is None


def test_hero_paths_belong_to_declared_sets():
    dests = {s.dest for s in F.FIGURE_SETS}
    for rel, caption in F.HERO:
        assert Path(rel).parent.as_posix() in dests, rel
        assert caption.strip()


def test_human_bytes():
    assert F._human_bytes(0) == "0 B"
    assert F._human_bytes(2048) == "2.0 KB"
    assert F._human_bytes(49 * 1024 * 1024) == "49.0 MB"
