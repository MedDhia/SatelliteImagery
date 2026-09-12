# Oceania: 22 entities, and the antimeridian

Every UN M49 Oceanian entity GADM can support, as a single `oceania` pool.

| pool | entities | admin-1 | trends | aridity |
|---|---:|---:|---|---|
| `oceania` | 22 | 216 | [`../results/oceania_trends_by_country.csv`](../results/oceania_trends_by_country.csv) | [`../results/oceania_aridity_vs_light.csv`](../results/oceania_aridity_vs_light.csv) |

⚠️ **`dark_2022` is incomparable across pools.** Each cuts at the median
`mean_dn_2022` of its own members, and Oceania's is **0.3050** against Europe's
9.9373 and the Arab League's 6.2628. A unit called dark here would be called
lit almost anywhere else.

That cut is also an example of the parity rule this repository keeps tripping
over. With 201 measured units the median was a real observation — Samoa's
Va'a-o-Fonoti at 0.2879 — and `results.MEDIAN_TIES` named it. Australia's 11
states took the count to 212, an even number, so the median became the mean of
0.2879 and 0.3222 and stopped being any unit's value at all. Four of the 216
rows are unmeasured and do not count toward that parity; see below.

By trajectory over the VIIRS window: 6 mixed, 6 disrupted, 4 intensive
convergers, 3 extensive spreaders, 2 flat, and 1 undefined — 22 in total,
which is the check that every country is classified exactly once.

## Six M49 members are absent, and not for the usual reason

GADM provides **no ADM_1 layer at all** for Kiribati, Niue, Norfolk Island,
Christmas Island, the Cocos Islands and Pitcairn — not "no admin-2", no
subnational layer whatsoever. `prepare_level` raises for level 1.

This repository measures inequality **across units**. Every quantity it
publishes — Gini, Theil T and L, the between/within decomposition, the
per-admin-1 aridity join — needs more than one unit to compare. An entity with
no units has nothing for any of it to measure, so carrying it as rows of blanks
would be worse than saying so here.

**Kiribati is the loss that matters**, being a UN member state, and it is
doubly frustrating: it is one of the four entities whose land straddles 180°,
so the two-window machinery built partly with it in mind cannot help it. The
machinery still pays for itself on the other three.

Timor-Leste and the British Indian Ocean Territory are M49 South-eastern Asia
and Sub-Saharan Africa, so neither is here.

## The antimeridian, and why a crop was not an option

A bounding box is a flat lon/lat rectangle and knows nothing of the wrap. Four
Oceanian entities have land on both sides of 180°, and GADM's boxes for them
are absurd:

| | GADM reports | naive frame | windowed |
|---|---|---:|---:|
| Kiribati | −174.5..176.8 | 96.8 Mpx | *excluded, no ADM_1* |
| New Zealand | −178.8..179.1 | 80.8 Mpx | **7.2 Mpx** |
| US Minor Outlying Islands | −178.3..166.7 | 117.6 Mpx | **6.0 Mpx** |
| Fiji | −180..180 | 36.5 Mpx | **0.5 Mpx** |

The United States was handled earlier by cropping at 180°, which cost 2 121.9
km² of near-unlit Aleutian rock. **That answer does not transfer here.** These
entities have *inhabited* land on both sides: cropping would delete the Chatham
Islands from New Zealand, the Lau group from Fiji, and Wake — the only lit unit
UMI has — from the United States' own outlying islands.

So `analysis.country_windows` splits a country into as many non-wrapping windows
as its land needs, and the statistics span all of them. Splitting the *space*
rather than assigning each unit to a side is what keeps a straddling unit whole:
New Zealand's "Northern Islands" spans −178.83..172.17 and Fiji's "Northern" the
full range, so a per-unit split would have cut them in half. A unit appears in
every window its land touches, under the same zone id, and its pixels
accumulate.

**Checked by arithmetic, not by eye.** Each entity's zonal pixel total against
its GADM land area, which on a 1 km grid should agree:

| | pixels | km² | ratio |
|---|---:|---:|---:|
| Fiji | 18 963 | 18 963 | **1.000** |
| New Zealand | 268 643 | 268 709 | **1.000** |
| Papua New Guinea | 463 604 | 463 616 | 1.000 |
| French Polynesia | 4 066 | 4 053 | 1.003 |
| Micronesia | 776 | 775 | 1.001 |
| Palau | 484 | 484 | 1.000 |
| UMI | 55 | 47 | 1.164 |

Fiji's exact agreement is the proof that nothing is lost at the seam and nothing
counted twice. New Zealand's 66-pixel shortfall over 268 thousand is ordinary
edge rounding: a double-counted seam would read *above* 1.000, and a dropped
Chatham Islands would cost 966 km², so neither happened.

UMI's 1.164 is rasterisation rounding *up* specks of 1–5 km² on a 1 km grid,
not an error — and all nine of its units, in three windows spanning from the
Caribbean to the western Pacific, received their pixels.

*Wake is the only lit unit UMI has*: 9 pixels, 71 DN. It sits alone in the third
window at +166.6°E.

## Coverage

**216 admin-1 units and 1 175 admin-2.** Ten entities have no GADM ADM_2 layer:
Guam, the Marshall Islands, Nauru, the Northern Marianas, Palau, the US Minor
Outlying Islands, the Cook Islands, French Polynesia, Tokelau and Tuvalu.

Australia dominates: 568 of the 1 175 admin-2 units, and 7 688 058 km² of the
region's land against Papua New Guinea's 463 616 and New Zealand's 268 709.
Its 11 states and territories reproduce 7 688 047 pixels against that area, a
ratio of 1.0000, with admin-1 and admin-2 agreeing exactly with each other.
Two of them are unlit rock — Ashmore and Cartier at 17 pixels and the Coral
Sea Islands at 6 — and the Australian Capital Territory is the region's
densest unit, 33 979 DN over 2 358 pixels.

### Two level names GADM declines to give

**Australia** takes the generic admin-2 title. Its most common `ENGTYPE_2` is
"Shire" at 199 of 568 — **35%**, a plurality, the same shape as Canada's 32%
and the United Kingdom's 35%. Australian local government areas are variously
shires, cities, councils and regions, and no single word covers them.

**Samoa's** `ENGTYPE_2` is the literal string `"Unknown"` for all 43 units.
That is GADM declining, exactly as `"NA"` is, and it takes the generic title
too.

### One misspelling, corrected against GADM rather than counted

GADM spells the Marshall Islands' ADM_1 **"Atol"** — 20 times — and Tokelau's
**"Atoll"**, 3 times. The typo is the *more* common of the two, so the frequency
reading of the correction rule (Uruguay's 124 "Municipiality" against 14 370
"Municipality") does not apply. What settles it is that the correct spelling of
the word GADM is reaching for appears elsewhere in the same column. The Marshall
Islands is published as **atoll**.

### Units too small to classify

Oceania is the first region containing units the analysis cannot describe, and
they are published with blanks rather than defaults:

- **Four units have an aridity cell but no land pixel** in the light raster,
  so `mean_dn` is 0/0: the Marshall Islands' Jabat (0.8 km²), Nauru's Aiwo
  (0.9) and Yaren (1.7), and Tuvalu's Niulakita (0.8). Their `dark_2022` and
  `cell` are blank. Recorded as `False` they would have asserted that an
  unobserved island is lit.
- **Three units have light but no aridity cell at all** — Nauru's Boe (29.0 DN)
  and Uaboe (26.25), and Palau's Hatohobei (0.0). All three are smaller than
  the aridity grid's cell, so there is nothing to take a majority over. Their
  `majority_arid` and `cell` are blank, because `NaN > 0.5` evaluating to
  `False` would have asserted they are not arid. These are the only three in
  all 168 entities.

Before this was handled, one NaN poisoned `statistics.median` and the pool's
darkness cut came out `NaN`, which made `mean_dn < cut` false for **all 77
units** and published every one of them as lit. Nothing failed; the numbers
were simply wrong.

### What 22 pixels can support

**Nauru divides 22 land pixels among 14 GADM districts.** Two districts
contain zero pixels, seven contain exactly one, three contain two, and the
remaining two hold four and five. Its admin-1 Gini is 0.3452 in 2022 against
0.4729 in 1992 — a 27% "decline" that is 22 pixels rearranging. A one-pixel
district has no internal inequality by construction, so its between/within
split is nearly all "between" as an artefact of the geometry rather than a
finding.

Tokelau is smaller still, and is the smallest in all 168: **17 pixels across
3 atolls.** The seven smallest are Tokelau (17), Nauru (22), Tuvalu (47), the
US Minor Outlying Islands (55), San Marino (59), Wallis and Futuna (153) and
Liechtenstein (159) — so this is not only an Oceanian problem, and San Marino
and Liechtenstein have been in the European pool since before this region was
built. Their indices are defined and published, and should not be read as
measurements of spatial inequality.

## No exclusion scopes

Scope `all` only, as everywhere outside the Arab League.
