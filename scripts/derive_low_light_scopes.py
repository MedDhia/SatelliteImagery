#!/usr/bin/env python3
"""Derive the low-light exclusion scopes from the rasters, and print them as code.

The scopes are **frozen into** ``satimg/regions.py`` rather than computed at
run time, for the same reason the dataset manifest is committed: a scope that
silently re-derives itself is a scope no reviewer ever sees change. Run this
when the reference year or the boundary version moves, and commit the diff.

The rule: sort a country's admin-1 units by lit share in the reference year,
look at every gap in the lower half of that ranking, and cut at the largest
relative gap that still leaves ``MIN_KEEP`` units standing. ``dark`` is that
cut; ``dark_wide`` is the largest remaining gap above it.

This finds a *discontinuity in observed light*, which is not the same thing as
a desert. On Tunisia it lands exactly on the three Saharan governorates that
were hand-picked for :data:`satimg.regions.TUNISIA_DESERT_SCOPES`, which is the
check that the rule is measuring something real. On Libya's second break it also
catches populated Nafusa Mountain districts. Read the printed table before
trusting a scope.

    python scripts/derive_low_light_scopes.py --year 2022
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

#: Leave at least this many units, or an inequality index over the survivors
#: stops meaning anything. Mauritania binds against this: one region holds
#: essentially all of the country's light.
MIN_KEEP = 8


def lit_shares(iso3: str, raster: Path, root: Path) -> List[Tuple[str, str, float]]:
    """(gid, name, lit share) per admin-1 unit, ascending."""
    import numpy as np

    from satimg import regions as R
    from satimg import zonal as Z

    layer = R.country_layer(iso3, 1, root=root)
    units = R.load_units(layer)
    grid = Z.build_zone_grid(raster, units, id_field="GID_1", name_field="NAME_1")
    values, _ = Z.read_window(raster, grid.window)

    out = []
    for index in range(1, grid.count + 1):
        inside = grid.ids == index
        sample = values[inside]
        sample = sample[~np.isnan(sample)]
        if sample.size == 0:
            continue
        out.append(
            (grid.gids[index - 1], grid.names[index - 1], float((sample > 0).mean()))
        )
    return sorted(out, key=lambda row: row[2])


def gaps(shares: Sequence[float]) -> List[Tuple[int, float]]:
    """(cut, ratio) for every gap in the lower half, largest ratio first."""
    total = len(shares)
    found = []
    for cut in range(1, total // 2 + 1):
        below, above = shares[cut - 1], shares[cut]
        if below <= 0:
            continue  # a zero-lit unit makes the ratio meaningless, not infinite
        found.append((cut, above / below))
    return sorted(found, key=lambda item: -item[1])


def scopes_for(rows: Sequence[Tuple[str, str, float]]) -> Dict[str, dict]:
    """The ``dark`` and ``dark_wide`` cuts, or fewer if the guard binds."""
    shares = [row[2] for row in rows]
    total = len(rows)
    usable = [(c, r) for c, r in gaps(shares) if total - c >= MIN_KEEP]
    if not usable:
        return {}

    first_cut, first_ratio = usable[0]
    out = {"dark": {"cut": first_cut, "ratio": first_ratio}}
    above = [(c, r) for c, r in usable if c > first_cut]
    if above:
        cut, ratio = max(above, key=lambda item: item[1])
        out["dark_wide"] = {"cut": cut, "ratio": ratio}
    for spec in out.values():
        spec["units"] = rows[: spec["cut"]]
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2022)
    parser.add_argument(
        "--countries", default="TUN,MAR,DZA,LBY,MRT", help="comma-separated ISO3"
    )
    parser.add_argument("--raster-root", type=Path, default=Path("data/raw/lrcc-dvnl"))
    parser.add_argument("--boundaries-root", type=Path, default=Path("data/boundaries"))
    args = parser.parse_args(argv)

    raster = args.raster_root / "lrcc-dvnl" / f"LACC_{args.year}.tif"
    if not raster.exists():
        parser.error(f"{raster} not found; run `satimg lrcc-dvnl download` first")

    print(f"# Derived from LACC_{args.year}, GADM 4.1, MIN_KEEP={MIN_KEEP}\n")
    for iso3 in [c.strip().upper() for c in args.countries.split(",") if c.strip()]:
        rows = lit_shares(iso3, raster, args.boundaries_root)
        derived = scopes_for(rows)
        print(f"# --- {iso3}: {len(rows)} admin-1 units " + "-" * 30)
        if not derived:
            print(f"#   no usable split: fewer than {MIN_KEEP} units would remain\n")
            continue
        for key, spec in derived.items():
            names = ", ".join(name for _, name, _ in spec["units"])
            share = spec["units"][-1][2]
            print(
                f"#   {key}: {spec['cut']} unit(s) below a x{spec['ratio']:.2f} break "
                f"at lit share {share:.3f}; {len(rows) - spec['cut']} kept"
            )
            print(f"#     {names}")
            gids = ", ".join(f'"{gid}"' for gid, _, _ in spec["units"])
            print(f"#     gid1=frozenset({{{gids}}})")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
