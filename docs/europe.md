# Europe: 43 countries, and the brightest pool in the collection

Every European state GADM codes, at the same detail as the rest of the
repository, as a single `europe` pool.

| pool | countries | admin-1 | trends | aridity |
|---|---:|---:|---|---|
| `europe` | 43 | 688 | [`../results/europe_trends_by_country.csv`](../results/europe_trends_by_country.csv) | [`../results/europe_aridity_vs_light.csv`](../results/europe_aridity_vs_light.csv) |

⚠️ **`dark_2022` is now incomparable across five pools.** Each of
`arab-league`, `africa`, `north-america`, `south-america` and `europe` cuts at
the median `mean_dn_2022` of its own members, and Europe's is far above every
other. Trends rates are fitted per country and never pooled.

**Europe is the first pool that overlaps no other.** Africa and the Arab League
share ten members; the two American pools were split precisely so they would
not share one. Europe as GADM codes it touches neither, and a test asserts it.

## Three absences, of two different kinds

**Monaco and the Vatican are not in GADM 4.1 at all** — there is no `MCO` or
`VAT` feature at any level. That is a gap in the source, not a choice here, and
it means two UN member states cannot be analysed rather than were declined.

**Russia is excluded deliberately.** Roughly three quarters of its area is
Asian, so it would dominate a European median while being mostly not in Europe.
It also wraps the antimeridian, exactly as GADM's `USA` does — but the American
remedy does not transfer. Cropping the United States at 180° costs 2 121.9 km²
of near-unlit Aleutian rock, 0.141% of Alaska. Cropping Russia there would cost
**114 686 km² of Chukotka** — larger than Iceland, and about 15% of that federal
subject. Including Russia would have meant either that loss or a two-window
stitch, and neither is worth it for a country barely in the region.

Kosovo appears as GADM's `XKO`, on the same footing as Palestine and Western
Sahara elsewhere here: GADM's coding of the boundary set in use, not a position
on status.

## Coverage

**688 admin-1 units** and **8 917 admin-2 in GADM**, of which **5 978 are
analysed**. Two subtractions, and they mean different things:

- **Seven countries have no GADM ADM_2 layer** and stop at admin-1 with no
  nested decomposition: Andorra, Cyprus, Liechtenstein, Moldova, Montenegro,
  North Macedonia and San Marino.
- **Romania's 2 939 communes are not analysed, by choice** — the same decision
  as Brazil's municipalities, recorded in `regions.LEVELS_NOT_ANALYSED` rather
  than in `LEVELS_AVAILABLE`, because GADM does provide them.

The largest admin-2 sets that *are* analysed: Ukraine 629, Croatia 560, Norway
438, Germany 403, Poland 380, the Netherlands 355.

### The whole continent is smaller than Chile

All 43 European frames together come to **19.7 megapixels** — less than Chile's
21.3 on its own, because GADM's `CHL` reaches Easter Island. Europe is
geographically compact and carries no memory risk anywhere; its cost is admin-2
unit counts in the choropleths, not frame size. The largest single European
frame is Spain at 3.74 Mpx and Portugal at 2.99, and in both cases the reason is
offshore: the Canaries and the Azores.

### Six countries have no name for their admin-2 level

Level names come from GADM's own `ENGTYPE` by majority — **more than half**, not
merely the most common. Europe exercises every branch of that rule without
needing a change to it, which is the best evidence that the rule Canada forced
into being was the right one.

**Two are genuine no-majority cases.** The United Kingdom's most common
`ENGTYPE_2` is "Unitary Authority" at **35% of 183** — a smaller plurality than
Canada's 32%, and for the same reason: the UK has no single word covering
English unitary authorities, Scottish council areas, Welsh principal areas and
Northern Irish districts at once. Belgium's is "Province" at 45% of 11.

**Four are cases where GADM itself declined.** Albania's `ENGTYPE_2` is
literally `"NA"` for all 37 units. Serbia's is the alternation
`"Town|Municipal"` for all 161, Slovenia's `"Commune|Municipality"`, Kosovo's
`"Town|Municipal"`. An alternation is not a word a country uses for itself, so
printing it would be inventing a name GADM was careful not to give.

All six take the generic title, the same treatment Madagascar, Angola and
Canada already get.

## No exclusion scopes

As with Africa, Thailand and the Americas, European countries ship with scope
`all` only. The low-light rule's published rationales read its break as desert
or conflict, and neither reading transfers to this continent.

## The brightest pool, and the only one where light is going out

Europe's darkness cut is **9.5926** — the highest of the five by a wide margin:

| pool | units | darkness cut |
|---|---:|---:|
| **europe** | 688 | **9.5926** |
| north-america | 379 | 6.3990 |
| arab-league | 317 | 6.2628 |
| south-america | 241 | 1.8081 |
| africa | 854 | 0.4948 |

That number moved a long way as the pool filled — 18.0275 at eight countries,
9.2630 at forty, 9.5926 at forty-three — because the countries analysed first
were the small bright ones. The early reading was an artefact of *which*
countries had been analysed, not a finding, and is recorded here so nobody
mistakes a partial pool for a result.

**688 is even**, so no European unit sits exactly on the median and the strict
`<` is not load-bearing here. All five pools now follow the same parity rule
without exception: the three odd-count pools each have a unit on the median and
name it, the two even-count pools have none. Europe briefly had one at 631
units and lost it when the last three countries landed.

### Five countries are losing lit area

Everywhere else in this repository, lit area grows. In Europe it does not:

| country | lit area, %/yr | total inequality, %/yr |
|---|---:|---:|
| Ukraine | **−1.32** | +1.30 |
| Slovakia | −0.43 | +1.27 |
| Moldova | −0.22 | +1.17 |
| United Kingdom | −0.09 | +0.04 |
| Netherlands | −0.04 | — |

These are also **the only four European countries whose total inequality
rises**, and the typology classifies all four as `disrupted` for the same
stated reason: lit area shrinking. Europe has more disrupted countries than
any other pool — four, against one each for the Arab League and North America
and none at all for Africa or South America.

**Two very different things are being pooled under that one label, and the
document should not pretend otherwise.**

Ukraine is the clearest case with a substantive reading available: lit area
falling 1.32 %/yr while inequality among still-lit places rises 1.79 %/yr, and
its total rising fastest in the pool. But the fit is poor — R² 0.49, and the
series is explicitly non-monotone — so this is a direction, not a pace, and a
single slope across 1992–2022 describes it badly.

The United Kingdom is almost certainly *not* disruption at all. Its total rate
is **+0.045 %/yr at R² 0.009** — indistinguishable from flat, and the direction
column says `flat` — and its lit-area change is −0.09 %/yr. The rule fired on a
sign, not on a magnitude.

### The caveat that matters most in Europe

A falling lit area in a wealthy, fully-electrified country is more likely an
**instrument artefact than a blackout**. European street lighting converted to
LEDs across the VIIRS era, and LEDs emit far less in the day/night band's
sensitive range than the sodium lamps they replaced. The same street records
as less light. This series cannot distinguish "fewer lit places" from "the same
places, lit differently", and Europe is where that ambiguity bites hardest
because it is where the conversion went furthest.

Nothing here should be read as European towns going dark. What the data
supports is that *measured* radiance fell in those five countries; the cause is
outside what this instrument can settle.

## Aridity is meaningless here, and the numbers say so plainly

Europe is the least arid pool in the collection by an enormous margin:

| pool | majority-arid share | Spearman(`desert_share`, `mean_dn_2022`) |
|---|---:|---:|
| arab-league | 73% | −0.1456 |
| africa | 24% | +0.0237 |
| south-america | 9% | −0.0329 |
| north-america | 2% | −0.2032 |
| **europe** | **0.1%** | **+0.0856** |

**One European admin-1 unit out of 688 is majority-arid**, and the median
`dryland_share` across the whole pool is **0.0000**. The bands are not a
gradient so much as a rounding error:

| band | units | median mean DN, 2022 |
|---|---:|---:|
| partly arid (0 < share < 1) | 8 | **19.1341** |
| not arid at all (share = 0) | 680 | **9.3115** |

No European unit is fully arid. The eight partly-arid ones are **twice as
bright** as the rest, which inverts the Arab-world result exactly as Africa's
did — and on a base of eight units, that is not a finding about climate, it is
eight Mediterranean and Atlantic units that happen to be developed.

The single majority-arid unit is **Spain's Islas Canarias** (`desert_share`
0.6351, mean DN 19.80) — and it is the pool's only `lit_desert`. Europe's only
desert is an Atlantic archipelago off the African coast, and it is brighter
than the European median. There are **no** `desert_dark` units at all.

The honest summary is that the aridity × darkness framework, which carries real
signal in the Arab world and real *counter*-signal in Africa, simply has
nothing to work with in Europe. The join is published for consistency across
pools, not because it says anything.

## Convergence, and the slowest extensive margin anywhere

| pool | median extensive margin |
|---|---:|
| Africa | +4.92 %/yr |
| south-america | +3.81 %/yr |
| arab-league | +2.25 %/yr |
| north-america | +1.31 %/yr |
| **europe** | **+0.91 %/yr** |

Europe lights new ground more slowly than any other pool — a fifth of Africa's
rate — because it had very little unlit ground left in 1992. Its median
intensive margin is **−0.01 %/yr**, essentially zero: inequality among lit
places is neither converging nor diverging across the continent as a whole.

| typology | count |
|---|---:|
| extensive spreader | 17 |
| mixed | 12 |
| intensive converger | 8 |
| disrupted | 4 |
| flat | 2 |

Median total inequality falls **−1.28 %/yr**. Kosovo falls fastest at −2.97
%/yr; Iceland has the fastest-growing lit area at +6.01 %/yr, which for a
country of that size and latitude is worth treating cautiously.

## Caveats

Everything in [`lrcc-dvnl.md`](lrcc-dvnl.md) applies. Three bite hardest here.

- **The LED transition.** Discussed above, and the single largest threat to any
  European reading of this series. A falling radiance in a rich country is more
  plausibly a change in what is emitted than a change in what is lit.
- **The 2014 handover.** DMSP and VIIRS rates are fitted separately and must
  never be compared, and Europe's LED conversion overlaps the VIIRS era, so the
  two artefacts are entangled precisely where the data is densest.
- **Aridity says nothing.** With one majority-arid unit in 688 and a median
  `dryland_share` of zero, no European aridity statistic in `results/` should
  be given weight, whatever its sign.

## Reproducing

```bash
ISOS=$(python -c "from satimg.regions import EUROPE as E; print(*E)")
for ISO in $ISOS; do
  satimg lrcc-dvnl extract    --country "$ISO" --levels 0,1,2
  satimg lrcc-dvnl choropleth --country "$ISO" --levels 1,2
  satimg lrcc-dvnl inequality --country "$ISO"
  satimg aridity units        --country "$ISO"
done
satimg aridity vs-light --pool europe
satimg trends --country all --pool europe
satimg figures build && satimg results build
```

The seven countries in `regions.LEVELS_AVAILABLE` take `--levels 0,1` because
GADM has no deeper layer; Romania takes `--levels 0,1` because
`LEVELS_NOT_ANALYSED` says so. `regions.available_levels(iso3)` answers for
both without the caller needing to know which reason applies.
