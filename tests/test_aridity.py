"""Aridity tests: the class boundaries, true cell area, and the nodata traps.

Synthetic and offline - no 646 MB download, no GADM. Every case here guards a
failure mode that produces a plausible-looking wrong number rather than a crash.
"""

from __future__ import annotations

import math
import pathlib

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")
from affine import Affine  # noqa: E402

from satimg import aridity as A  # noqa: E402

PIXEL = A.RESOLUTION_DEG


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw,expected",
    [
        (0, 1),  # AI 0 is a real hyper-arid value, not nodata
        (127, 1),  # the value that the old read_window fallback would have eaten
        (299, 1),
        (300, 2),  # boundaries are half-open [lower, upper)
        (1999, 2),
        (2000, 3),
        (4999, 3),
        (5000, 4),
        (6499, 4),
        (6500, 5),
        (64999, 5),
        (A.UNDEFINED, 0),
    ],
)
def test_classify_boundaries(raw, expected):
    assert int(A.classify(np.array([[raw]]))[0, 0]) == expected


def test_zero_is_hyper_arid_on_land_and_nodata_at_sea():
    # The whole ocean/desert ambiguity in one assertion: identical AI values,
    # opposite meanings, resolved only by the land mask.
    raw = np.array([[0, 0]])
    land = np.array([[True, False]])
    assert list(A.classify(raw, land_mask=land)[0]) == [1, A.NODATA_CODE]


def test_classes_tile_the_range_without_gap_or_overlap():
    edges = [(c.lower_raw, c.upper_raw) for c in A.CLASSES]
    assert edges[0][0] == 0 and edges[-1][1] is None
    for (_, upper), (lower, _) in zip(edges, edges[1:]):
        assert upper == lower


def test_class_codes_never_collide_with_nodata():
    assert A.NODATA_CODE not in {c.code for c in A.CLASSES}


# --------------------------------------------------------------------------- #
# true cell area
# --------------------------------------------------------------------------- #
def test_row_areas_integrate_to_the_whole_ellipsoid():
    transform = Affine(PIXEL, 0, -180.0, 0, -PIXEL, 90.0)
    total = A.row_areas_km2(transform, 21600).sum() * 43200
    assert abs(total - 510_065_600) / 510_065_600 < 1e-6


def test_cell_area_shrinks_poleward():
    def cell(lat):
        return A.row_areas_km2(Affine(PIXEL, 0, 0, 0, -PIXEL, lat), 1)[0]

    assert cell(0) > cell(20) > cell(37) > cell(60)


def test_cell_area_is_symmetric_about_the_equator():
    # Comoros sits at 11.7 S. A cos() clamped to the northern hemisphere, or an
    # abs() in the wrong place, would silently mis-weight the only humid control.
    north = A.row_areas_km2(Affine(PIXEL, 0, 0, 0, -PIXEL, 11.7 + PIXEL), 1)[0]
    south = A.row_areas_km2(Affine(PIXEL, 0, 0, 0, -PIXEL, -11.7), 1)[0]
    assert math.isclose(north, south, rel_tol=1e-12)


def test_row_areas_are_all_positive():
    transform = Affine(PIXEL, 0, -180.0, 0, -PIXEL, 90.0)
    assert (A.row_areas_km2(transform, 21600) > 0).all()


# --------------------------------------------------------------------------- #
# shares
# --------------------------------------------------------------------------- #
def test_shares_sum_to_one_accepts_nan_for_an_empty_unit():
    row = {f"{c.key}_share": float("nan") for c in A.CLASSES}
    assert A.shares_sum_to_one(row)


def test_shares_sum_to_one_rejects_a_short_denominator():
    row = {f"{c.key}_share": 0.0 for c in A.CLASSES}
    row["arid_share"] = 0.9  # sums to 0.9, e.g. a dropped nodata class
    assert not A.shares_sum_to_one(row)


# --------------------------------------------------------------------------- #
# warping onto the analysis grid
# --------------------------------------------------------------------------- #
def _write(path, array, *, crs, transform, nodata=0, dtype=None):
    profile = dict(
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=dtype or array.dtype.name,
        crs=crs,
        transform=transform,
        nodata=nodata,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
    return path


def test_warp_matches_the_reference_grid_exactly(tmp_path):
    from satimg.raster import warp_to_grid
    from satimg.zonal import grids_compatible

    ref = _write(
        tmp_path / "ref.tif",
        np.ones((6, 5), dtype="int16"),
        crs=rasterio.crs.CRS.from_epsg(8857),
        transform=Affine(1000.0, 0, 0.0, 0, -1000.0, 10_000.0),
        nodata=127,
    )
    src = _write(
        tmp_path / "src.tif",
        np.full((40, 40), 2, dtype="uint8"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
    )
    out = warp_to_grid(src, ref, tmp_path / "out.tif")
    with rasterio.open(out) as got, rasterio.open(ref) as want:
        assert grids_compatible(
            (got.width, got.height, got.transform),
            (want.width, want.height, want.transform),
        )
        assert got.nodata == 0


def test_untouched_destination_cells_are_nodata_not_zero_class(tmp_path):
    """GDAL's default fill is 0. For a class raster 0 must mean 'no data',
    never a class - otherwise every ocean cell becomes real-looking output."""
    from satimg.raster import warp_to_grid

    ref = _write(
        tmp_path / "ref.tif",
        np.ones((8, 8), dtype="int16"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 50.0, 0, -PIXEL, 50.0),
        nodata=127,
    )
    # Source sits far away, so it covers none of the destination.
    src = _write(
        tmp_path / "src.tif",
        np.full((4, 4), 3, dtype="uint8"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, -170.0, 0, -PIXEL, -40.0),
    )
    out = warp_to_grid(src, ref, tmp_path / "out.tif")
    with rasterio.open(out) as got:
        assert (got.read(1) == A.NODATA_CODE).all()


def test_warp_invents_no_class_absent_from_the_source(tmp_path):
    from satimg.raster import warp_to_grid

    ref = _write(
        tmp_path / "ref.tif",
        np.ones((10, 10), dtype="int16"),
        crs=rasterio.crs.CRS.from_epsg(8857),
        transform=Affine(1000.0, 0, 0.0, 0, -1000.0, 10_000.0),
        nodata=127,
    )
    values = np.random.default_rng(0).choice([1, 5], size=(60, 60)).astype("uint8")
    src = _write(
        tmp_path / "src.tif",
        values,
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
    )
    out = warp_to_grid(src, ref, tmp_path / "out.tif")
    with rasterio.open(out) as got:
        present = set(np.unique(got.read(1)).tolist())
    assert present <= {A.NODATA_CODE, 1, 5}


# --------------------------------------------------------------------------- #
# the read_window trap this work closed
# --------------------------------------------------------------------------- #
def test_read_window_refuses_to_guess_a_missing_nodata(tmp_path):
    from satimg.zonal import read_window

    path = _write(
        tmp_path / "no_nodata.tif",
        np.full((4, 4), 127, dtype="uint16"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
        nodata=None,
    )
    with pytest.raises(ValueError, match="declares no nodata"):
        read_window(path, rasterio.windows.Window(0, 0, 4, 4))


def test_read_window_keeps_127_when_told_there_is_no_fill(tmp_path):
    from satimg.zonal import read_window

    path = _write(
        tmp_path / "ai.tif",
        np.full((4, 4), 127, dtype="uint16"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
        nodata=None,
    )
    data, _ = read_window(path, rasterio.windows.Window(0, 0, 4, 4), nodata=None)
    assert not np.isnan(data).any()
    assert (data == 127).all()


def test_build_zone_grid_refuses_a_geographic_crs(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    from satimg.zonal import build_zone_grid

    path = _write(
        tmp_path / "r.tif",
        np.ones((4, 4), dtype="uint8"),
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=Affine(PIXEL, 0, 0.0, 0, -PIXEL, 0.1),
    )
    frame = gpd.GeoDataFrame(
        {"GID_1": ["A"]}, geometry=[box(0, 0, 0.02, 0.02)], crs="EPSG:4326"
    )
    with pytest.raises(ValueError, match="projected CRS"):
        build_zone_grid(path, frame, id_field="GID_1")


# --------------------------------------------------------------------------- #
# aridity against light
# --------------------------------------------------------------------------- #
REPO = pathlib.Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"


def write_country(root, iso3, units, years):
    """A minimal per-country pair: an aridity table and a zonal table."""
    import csv as _csv

    folder = root / iso3
    folder.mkdir(parents=True, exist_ok=True)

    with open(folder / f"{iso3}_adm1_aridity.csv", "w", newline="") as handle:
        writer = _csv.DictWriter(
            handle,
            fieldnames=[
                "gid",
                "name",
                "area_km2",
                "pixels_classified",
                "desert_share",
                "dryland_share",
                "humid_share",
            ],
        )
        writer.writeheader()
        for unit in units:
            writer.writerow(unit)

    with open(folder / f"{iso3}_adm1_zonal.csv", "w", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=["year", "gid", "mean_dn"])
        writer.writeheader()
        for year, by_gid in years.items():
            for gid, mean_dn in by_gid.items():
                writer.writerow({"year": year, "gid": gid, "mean_dn": mean_dn})


def unit(gid, name, desert):
    return {
        "gid": gid,
        "name": name,
        "area_km2": 100.0,
        "pixels_classified": 100,
        "desert_share": desert,
        "dryland_share": 1.0,
        "humid_share": 0.0,
    }


def test_cell_is_exactly_the_two_by_two_of_its_inputs():
    assert A.cell_of(True, True) == A.CELL_DESERT_DARK
    assert A.cell_of(True, False) == A.CELL_LIT_DESERT
    assert A.cell_of(False, True) == A.CELL_ANOMALOUS
    assert A.cell_of(False, False) == A.CELL_ORDINARY


def test_the_darkness_cut_is_a_strict_comparison_against_the_median(tmp_path):
    """A unit sitting exactly on the median is NOT dark.

    Iraq's Ninawa does exactly this in the real data, so the convention decides
    a published number and cannot be left to whichever operator a rewrite picks.
    """
    units = [unit(f"X.{i}_1", f"u{i}", 0.0) for i in range(5)]
    write_country(
        tmp_path,
        "XXX",
        units,
        {
            1992: {u["gid"]: 1.0 for u in units},
            2022: {u["gid"]: v for u, v in zip(units, [1.0, 2.0, 3.0, 4.0, 5.0])},
        },
    )
    rows = A.vs_light(tmp_path, ["XXX"])
    assert A.dark_cut([r["mean_dn_2022"] for r in rows]) == 3.0
    on_the_cut = next(r for r in rows if r["mean_dn_2022"] == 3.0)
    assert on_the_cut["dark_2022"] is False
    assert sum(1 for r in rows if r["dark_2022"]) == 2


def test_a_unit_missing_from_the_zonal_side_is_dropped_whole(tmp_path):
    """Half a row is worse than no row: the join must not emit one."""
    units = [unit("X.1_1", "kept", 0.0), unit("X.2_1", "orphan", 0.0)]
    write_country(
        tmp_path,
        "XXX",
        units,
        {1992: {"X.1_1": 1.0, "X.2_1": 1.0}, 2022: {"X.1_1": 2.0}},
    )
    rows = A.vs_light(tmp_path, ["XXX"])
    assert [r["gid"] for r in rows] == ["X.1_1"]


def test_a_unit_missing_one_year_is_dropped_too(tmp_path):
    units = [unit("X.1_1", "only-2022", 0.0)]
    write_country(tmp_path, "XXX", units, {1992: {}, 2022: {"X.1_1": 2.0}})
    assert A.vs_light(tmp_path, ["XXX"]) == []


def test_majority_arid_is_strictly_above_half(tmp_path):
    """Exactly half desert is not a desert unit; the boundary is stated."""
    units = [unit("X.1_1", "half", 0.5), unit("X.2_1", "just-over", 0.5001)]
    write_country(
        tmp_path,
        "XXX",
        units,
        {1992: {u["gid"]: 1.0 for u in units}, 2022: {u["gid"]: 1.0 for u in units}},
    )
    rows = {r["gid"]: r for r in A.vs_light(tmp_path, ["XXX"])}
    assert rows["X.1_1"]["majority_arid"] is False
    assert rows["X.2_1"]["majority_arid"] is True


def test_a_missing_country_is_skipped_rather_than_crashing(tmp_path):
    assert A.vs_light(tmp_path, ["ZZZ"]) == []


def test_mean_dn_columns_are_not_named_density():
    """`density_sol_per_km2` is a different quantity published in the same tree.

    The columns shipped briefly under `density_*`, which made one word mean two
    things across two committed tables.
    """
    import csv as _csv

    path = RESULTS / A.VS_LIGHT_TABLE
    if not path.exists():
        pytest.skip("results/ not present")
    with open(path, encoding="utf-8") as handle:
        header = next(_csv.reader(handle))
    assert "mean_dn_1992" in header and "mean_dn_2022" in header
    assert not [name for name in header if name.startswith("density")]


# --------------------------------------------------------------------------- #
# against the committed table
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def published():
    import csv as _csv

    path = RESULTS / A.VS_LIGHT_TABLE
    if not path.exists():
        pytest.skip("results/ not present")
    with open(path, newline="", encoding="utf-8") as handle:
        return list(_csv.DictReader(handle))


def test_the_committed_table_matches_a_fresh_join(published):
    """`results/aridity_vs_light.csv` must not drift from the module."""
    fresh = A.vs_light(RESULTS)
    if not fresh:
        pytest.skip("per-country tables not present")
    assert len(fresh) == len(published)
    for got, want in zip(fresh, published):
        for key, value in got.items():
            if isinstance(value, float):
                assert value == pytest.approx(float(want[key])), (got["gid"], key)
            else:
                assert str(value) == want[key], (got["gid"], key)


def test_the_light_scopes_column_reconstructs_from_regions(published):
    """The join key between the light rule and the climate table."""
    for row in published:
        assert A.light_scopes_for(row["iso3"], row["gid"]) == row["light_scopes"]


def test_the_anomalous_sets_are_strictly_nested(published):
    """6 / 13 / 23 - a hard core softening outward, not a churning set."""
    values = [float(r["mean_dn_2022"]) for r in published]
    sets = []
    for quantile in A.DARK_QUANTILES:
        cut = A.dark_cut(values, quantile)
        sets.append(
            {
                r["gid"]
                for r in published
                if r["majority_arid"] == "False" and float(r["mean_dn_2022"]) < cut
            }
        )
    assert [len(s) for s in sets] == [6, 13, 23]
    assert sets[0] < sets[1] < sets[2]


def test_aridity_is_a_step_not_a_slope(published):
    """The finding the figure is shaped around; a regression guard on it."""
    import statistics

    def median_for(predicate):
        return statistics.median(
            float(r["mean_dn_2022"])
            for r in published
            if predicate(float(r["desert_share"]))
        )

    fully = median_for(lambda s: s == 1.0)
    partly = median_for(lambda s: 0.0 < s < 1.0)
    none = median_for(lambda s: s == 0.0)
    assert fully == pytest.approx(3.70, abs=0.01)
    assert partly == pytest.approx(3.78, abs=0.01)
    assert none == pytest.approx(14.09, abs=0.01)
    # The two arid bands are indistinguishable; the step is at "not arid".
    assert abs(fully - partly) < 0.2
    assert none > 3 * partly


def test_the_pooled_join_covers_the_pool_only(published):
    """Thailand is analysed but must not enter the cross-country join.

    This is the behavioural half of the pool/analysed split. It bites once
    `results/THA/` exists on disk: a fresh join that picked up Thailand would
    move the median `mean_dn_2022` and rewrite `dark_2022`, `cell` and the
    6/13/23 nesting for every unit already published.
    """
    from satimg import regions as R

    fresh = A.vs_light(RESULTS)
    if not fresh:
        pytest.skip("per-country tables not present")

    seen = {row["iso3"] for row in fresh}
    assert seen <= set(R.ARAB_LEAGUE)
    assert seen == {row["iso3"] for row in published}

    analysed_only = set(R.COUNTRIES) - set(R.ARAB_LEAGUE)
    for iso3 in analysed_only:
        if (RESULTS / iso3 / f"{iso3}_adm1_aridity.csv").exists():
            assert iso3 not in seen, (
                f"{iso3} has an aridity table on disk and leaked into the "
                "pooled join, which moves the darkness median"
            )


def test_an_analysed_country_outside_the_pool_can_still_be_joined_explicitly():
    """Excluded by default, not unreachable: `vs_light` still takes a list."""
    from satimg import regions as R

    analysed_only = sorted(set(R.COUNTRIES) - set(R.ARAB_LEAGUE))
    assert analysed_only, "the split is pointless if nothing sits outside it"
    for iso3 in analysed_only:
        if not (RESULTS / iso3 / f"{iso3}_adm1_aridity.csv").exists():
            continue
        rows = A.vs_light(RESULTS, [iso3])
        assert rows and {r["iso3"] for r in rows} == {iso3}


# --------------------------------------------------------------------------- #
# dryland is every class below humid
# --------------------------------------------------------------------------- #
def test_dryland_keys_are_every_class_below_the_humid_threshold():
    """Derived from CLASSES, not hand-listed.

    Hand-listing is how dry sub-humid came to be left out of the sum: the
    original expression was `desert_share + semi_arid_share`, which understated
    the share for 60 of the first 317 units published - Beirut, wholly dry
    sub-humid, was reported as 0% dryland.
    """
    assert A.DRYLAND_KEYS == ("hyper_arid", "arid", "semi_arid", "dry_subhumid")
    assert "humid" not in A.DRYLAND_KEYS
    assert set(A.DESERT_KEYS) < set(A.DRYLAND_KEYS)
    # Every class but humid, and humid is the only one left out.
    assert set(A.DRYLAND_KEYS) | {"humid"} == {c.key for c in A.CLASSES}


@pytest.mark.parametrize(
    "shares,dryland",
    [
        ({"dry_subhumid": 1.0}, 1.0),
        ({"humid": 1.0}, 0.0),
        ({"hyper_arid": 1.0}, 1.0),
        ({"semi_arid": 0.5, "humid": 0.5}, 0.5),
        ({"arid": 0.25, "dry_subhumid": 0.25, "humid": 0.5}, 0.5),
    ],
)
def test_dryland_share_is_one_minus_humid(shares, dryland):
    row = {f"{c.key}_share": shares.get(c.key, 0.0) for c in A.CLASSES}
    assert sum(row[f"{c.key}_share"] for c in A.CLASSES) == pytest.approx(1.0)
    got = sum(row[f"{key}_share"] for key in A.DRYLAND_KEYS)
    assert got == pytest.approx(dryland)
    assert got == pytest.approx(1.0 - row["humid_share"])


def test_every_published_dryland_share_is_one_minus_humid():
    """A regression guard on the whole published set, not just the arithmetic."""
    import csv as _csv

    from satimg import regions as R

    checked = 0
    for iso3 in R.COUNTRIES:
        path = RESULTS / iso3 / f"{iso3}_adm1_aridity.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as handle:
            for row in _csv.DictReader(handle):
                assert float(row["dryland_share"]) == pytest.approx(
                    1.0 - float(row["humid_share"]), abs=1e-9
                ), (iso3, row["name"])
                checked += 1
    if not checked:
        pytest.skip("results/ not present")


def test_the_cross_country_table_agrees_with_the_per_country_ones(published):
    import csv as _csv

    per_country = {}
    for iso3 in {row["iso3"] for row in published}:
        path = RESULTS / iso3 / f"{iso3}_adm1_aridity.csv"
        if not path.exists():
            pytest.skip("per-country tables not present")
        with open(path, encoding="utf-8") as handle:
            for row in _csv.DictReader(handle):
                per_country[(iso3, row["gid"])] = row
    # The cross-country table is published to ROUND_DP decimals while the
    # per-country tables carry full precision, so agreement is asserted at the
    # published rounding, not exactly.
    tolerance = 0.5 * 10**-A.ROUND_DP
    for row in published:
        want = per_country[(row["iso3"], row["gid"])]
        for column in ("desert_share", "dryland_share", "humid_share"):
            assert float(row[column]) == pytest.approx(
                float(want[column]), abs=tolerance
            ), (row["iso3"], row["gid"], column)
