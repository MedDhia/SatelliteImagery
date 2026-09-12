# The Americas: 35 countries in two pools

Every state of North and South America at the same detail as the rest of the
repository, split into **two comparison pools rather than one**.

## Why two pools and not one

A single "Americas" pool would put Saint Kitts and Nevis in the same median as
the United States. The aridity join cuts `dark_2022` at the median of *its own
pool*, so one pool would set the darkness threshold largely from the giants and
call much of the Caribbean lit by comparison.

The measured medians settle it: **10.1136** north against **1.8032** south, a
3.5-fold gap. A single pooled median would have sat between them and
misclassified both ends.

| pool | countries | admin-1 | trends | aridity |
|---|---:|---:|---|---|
| `north-america` | 23 | 379 | [`../results/north-america_trends_by_country.csv`](../results/north-america_trends_by_country.csv) | [`../results/north-america_aridity_vs_light.csv`](../results/north-america_aridity_vs_light.csv) |
| `south-america` | 12 | 241 | [`../results/south-america_trends_by_country.csv`](../results/south-america_trends_by_country.csv) | [`../results/south-america_aridity_vs_light.csv`](../results/south-america_aridity_vs_light.csv) |

⚠️ **`dark_2022` is now incomparable across four pools**, not two. Each of
`arab-league`, `africa`, `north-america` and `south-america` cuts at its own
median, and the four answer different questions. Trends rates are fitted per
country and never pooled, so a country in two pools carries identical rates in
each — though no country appears in more than one of these four.

```bash
satimg trends           --country all --pool north-america
satimg aridity vs-light --pool south-america
```

## Coverage

**620 admin-1 units** and **16 133 admin-2 units in GADM**, of which **10 561
are analysed**. Two subtractions explain the gap, and they are different kinds
of thing:

- **Eleven countries have no GADM ADM_2 layer** and stop at admin-1 with no
  nested decomposition: Belize, Antigua and Barbuda, the Bahamas, Barbados,
  Dominica, Grenada, Jamaica, Saint Kitts and Nevis, Saint Lucia, Saint Vincent
  and the Grenadines, Trinidad and Tobago.
- **Brazil's 5 572 municipalities are not analysed, by choice.** GADM has them;
  this repository does not use them. See below.

### Brazil stops at the state

Brazil's municipality layer is the largest ADM_2 set here by a wide margin —
sixteen times Chile's 346 and nearly four times Algeria's 1 504, which was the
previous ceiling. Burning 5 572 polygons onto Brazil's 21-megapixel frame, for
each of 31 years, for each of four choropleth variants, ran for over half an
hour on a single variant without emitting a file. The level was dropped.

That is recorded in `regions.LEVELS_NOT_ANALYSED`, deliberately apart from
`LEVELS_AVAILABLE`. The latter means *GADM has no such layer*, which would be
false here and would put a false statement about the source data into a table
other people read. Two functions now answer the two questions: `gadm_levels()`
for what the source provides, `available_levels()` for what is analysed.

**Brazil is consequently the only large country here with no nested three-way
decomposition.** Its state-level series, decomposition and aridity join are
complete, and the decomposition residual is 2.9 × 10⁻¹³. Deleting the entry and
re-running restores the municipality layer.

### Level names, and the country that has none

Level names come from GADM's own `ENGTYPE` by majority — **more than half**, not
merely the most common. The Americas are what forced that rule to be stated
precisely, because **Canada breaks it**. Canada's most common `ENGTYPE_2` is
Quebec's "Regional County Municipality" at 93 of 293 units — **32%**, a
plurality, and not a word the country uses for itself. Canada therefore takes
the generic title while keeping all 293 admin-2 units: it has the level, it
simply has no single name for it.

Uruguay is the other instructive case. Its `ENGTYPE_2` reads "Municipiality"
124 times, where the same GADM column spells "Municipality" 14 370 times
elsewhere. That is GADM's typo, not Uruguay's word, so the corrected spelling
is published — reconciled against GADM itself rather than against our
assumption.

### Frames wider than their countries

GADM codes offshore territory with the mainland, and three frames are mostly
ocean as a result. The same cause produced a cosmetic problem in two cases and
a fatal one in the third.

**Chile's raster is 4 911 km wide for a country 350 km across**, because GADM's
`CHL` reaches Easter Island 3 500 km out; Ecuador's reaches the Galápagos. Both
mainlands stay legible and the offshore territory renders as the faint dot it
is, so the extent is left honest rather than cropped to flatter the map.

**The United States is analysed over two windows, because there the same thing
was fatal.** GADM's `USA` carries Alaskan vertices at both −179.15° and
+179.77°, since the Aleutians run past 180° into the eastern hemisphere. A
bounding box is a flat lon/lat rectangle and knows nothing of the wrap, so
`total_bounds` spanned the globe: **29 188 km, a 159-megapixel frame** where the
largest country otherwise analysed here is 21. That is not a slow render but an
out-of-memory crash, and because `zonal.window_for` derived its window the same
way, it would have taken the statistics down with the pictures.

The country is instead split into as many non-wrapping windows as its land
needs — here two, **9 666 × 5 449 px for the mainland and 729 × 165 for the
Aleutian tail, 52.8 Mpx together**. `analysis.country_windows` derives them and
the statistics span all of them, so **nothing is dropped**: a unit's pixels
accumulate across windows under the same zone id.

This replaced an earlier crop to the western hemisphere, which reached the same
52.6 Mpx by discarding the Aleutian tail east of 180° — 2 121.9 km² (Attu,
Agattu, Kiska, Amchitka, Semisopochnoi), 0.141% of Alaska. Restoring it added
**2 127 pixels, 2 121.86 km² and 338 DN of light** to Alaska, and changed
exactly one of the 51 units. Those islands were described as near-unlit, and
that 338 is why the distinction was worth keeping: near-unlit is not unlit.

The *pictures* still show one window, the largest — the mainland at 52.7 Mpx —
because a figure spanning both would be mostly empty Pacific. `extract` says on
stderr when a country's land spans more than one window, so a map's omissions
are stated rather than left to be noticed.

### No exclusion scopes

As with Africa and Thailand, American countries ship with scope `all` only. The
low-light rule's published rationales read its break as desert or conflict, and
neither reading transfers here — the Atacama would look like it fits, which is
exactly the trap.

## North and South are near-opposites

The typology splits the hemisphere almost cleanly in two.

| typology | north-america | south-america | Africa | Arab League |
|---|---:|---:|---:|---:|
| extensive spreader | 4 | **11** | 42 | 9 |
| mixed | 9 | 1 | 7 | 5 |
| intensive converger | **7** | 0 | 1 | 6 |
| flat | 2 | 0 | 5 | 1 |
| disrupted | 1 | 0 | 0 | 1 |

**South America is 11 of 12 extensive spreaders**: falling total inequality
almost everywhere, driven by light reaching ground that had none, while
inequality among already-lit places rises. Not one South American country is an
intensive converger.

**North America has no such unanimity** — 7 intensive convergers against 4
extensive spreaders, with 9 mixed. It is the only pool where genuine
convergence among lit places is the largest single class.

The extensive margin says why, and it is a clean ordering across all four pools:

| pool | median extensive margin |
|---|---:|
| Africa | +4.92 %/yr |
| south-america | **+3.81 %/yr** |
| arab-league | +2.25 %/yr |
| north-america | **+1.31 %/yr** |

North America is three times slower than South America at lighting new ground.
Its lit area was already largely lit in 1992, so its falling inequality has to
come from convergence rather than from expansion — which is what the typology
reports. South America is still in the expansion phase.

Only one country in North America has a *negative* extensive margin (−0.13
%/yr); the pool's fastest is +5.74 %/yr, against South America's floor of
+1.10 %/yr. Even the slowest-expanding South American country outpaces the
North American median.

## Aridity: the strongest signal in the repository, in the least arid pool

Across the four pools the aridity–light relationship now reads:

| pool | Spearman(`desert_share`, `mean_dn_2022`) | majority-arid share |
|---|---:|---:|
| north-america | **−0.2032** | **2%** |
| arab-league | −0.1456 | 73% |
| south-america | −0.0329 | 9% |
| africa | +0.0237 | 24% |

**North America has the strongest negative correlation of any pool while being
by far the least arid** — 7 of 379 units are majority-arid. The relationship is
not weakened by the small arid base; it is sharpened, because in a pool where
almost nothing is arid, the few arid units are unusually dark against a bright
surround:

| band | units | median mean DN, 2022 |
|---|---:|---:|
| partly arid (0 < share < 1) | 28 | **2.5850** |
| not arid at all (share = 0) | 351 | **6.8929** |

No North American admin-1 unit is fully arid. And **not one is a lit desert**:

| | arid | not arid |
|---|---|---|
| **dark** | 7 | 182 |
| **lit** | 0 | 190 |

Every majority-arid unit in North America is dark. That is the cleanest version
of the pattern anywhere in this repository — and the reason to distrust reading
it as climate. With 7 units in the arid column, the cell is too small to carry
the claim, and the Spearman is being driven by the 351 non-arid units, not by
the 7 arid ones.

**South America is the only pool where the gradient is monotone** in the
expected direction:

| band | units | median mean DN, 2022 |
|---|---:|---:|
| fully arid (share = 1) | 3 | **0.9665** |
| partly arid | 43 | **1.7885** |
| not arid at all | 195 | **1.9867** |

Fully arid darker than partly arid darker than humid, in order — which neither
the Arab League (one step at "not arid at all") nor Africa (inverted) manages.
But the correlation is −0.0329, indistinguishable from zero, because the steps
are small: 0.97 to 1.99 across the whole range, against North America's 2.59 to
6.89. The ordering is right and the effect is negligible, which is a more honest
summary than either number alone.

**Four North American units have no lit pixels at all in 2022** — Redonda
(Antigua and Barbuda), and Ragged Island, Rum Cay and Spanish Wells (the
Bahamas). All are tiny Caribbean islands, and a Gini or Theil over an all-zero
distribution is defined but fragile. South America has none.

## Which unit sits on the median

Both American pools hold an odd number of units, so `statistics.median` returns
a real observation rather than the average of two — and a unit therefore sits
*exactly* on the darkness cut, where the strict `<` decides whether it is dark
or lit:

| pool | units | | median | on the median |
|---|---:|---|---:|---|
| arab-league | 317 | odd | 6.2628 | Iraq's Ninawa |
| north-america | 519 | odd | 10.1136 | Guatemala's Chimaltenango |
| south-america | 243 | odd | 1.8032 | Bolivia's Cochabamba |
| africa | 878 | even | 0.5467 | *none* |

"Washington State" rather than GADM's bare "Washington", because the pool holds
both that and the District of Columbia.

This is parity, not luck, and it is checked: `tests/test_results.py` recomputes
each pool's median from its committed CSV and requires that a named unit really
ties and that a pool with no entry really has none.

## Caveats

Everything in [`lrcc-dvnl.md`](lrcc-dvnl.md) applies. Four bite harder here.

- **The United States is complete, but its maps are not.** Every pixel is in
  the statistics, across two windows. The published *figures* show only the
  larger window, so the Aleutians west of 180° appear in no American map even
  though they are in every American number.
- **Brazil has no municipality layer here.** It is the only large country in
  that position, and any comparison of its between/within split against another
  large country is comparing two levels against three.
- **A falling total is partly imposed.** A lit pixel in this series never dims,
  it goes out, so as lit area grows the zeros-included index falls almost by
  construction. At South America's median +3.81 %/yr extensive margin that
  mechanism is doing real work, which is why the lit-only rate is published
  beside the total rather than under it.
- **The arid cells are small.** North America's 7 majority-arid units and South
  America's 3 fully-arid ones cannot carry a claim about climate, however clean
  the resulting table looks.

## Reproducing

```bash
ISOS=$(python -c "from satimg.regions import NORTH_AMERICA as N, SOUTH_AMERICA as S; print(*N, *S)")
for ISO in $ISOS; do
  satimg lrcc-dvnl extract    --country "$ISO" --levels 0,1,2
  satimg lrcc-dvnl choropleth --country "$ISO" --levels 1,2
  satimg lrcc-dvnl inequality --country "$ISO"
  satimg aridity units        --country "$ISO"
done
satimg aridity vs-light --pool north-america
satimg aridity vs-light --pool south-america
satimg trends --country all --pool north-america
satimg trends --country all --pool south-america
satimg figures build && satimg results build
```

Countries in `regions.LEVELS_AVAILABLE` take `--levels 0,1` because GADM has no
deeper layer; Brazil takes `--levels 0,1` because `LEVELS_NOT_ANALYSED` says so.
`regions.available_levels(iso3)` gives the right answer for both without caring
which reason applies.
