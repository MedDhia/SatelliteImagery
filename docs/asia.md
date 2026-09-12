# Asia: 49 entities, and what a shared column can hide

Every UN M49 Asian entity GADM can support, plus Russia, as a single `asia`
pool.

| pool | entities | admin-1 | admin-2 | trends | aridity |
|---|---:|---:|---:|---|---|
| `asia` | 58 | 1 047 | 14 263 | [`../results/asia_trends_by_country.csv`](../results/asia_trends_by_country.csv) | [`../results/asia_aridity_vs_light.csv`](../results/asia_aridity_vs_light.csv) |

Fourteen of the 49 were already analysed under other pools — the twelve Arab
League members of Western Asia, Cyprus from Europe, and Thailand, which had
been outside every pool until now. **35 are new.** A country in two pools is
the design working, not duplication: each pool cuts `dark_2022` at the median
of its own members.

⚠️ **`dark_2022` is incomparable across the seven pools**, and Asia makes the
point sharply. Its cut is **5.4200**; Europe's is 9.9373 and Oceania's 0.3050.
A unit called *lit* in Asia would be called dark in Europe and lit eighteen
times over in Oceania.

| pool | measured units | cut |
|---|---:|---:|
| `north-america` | 519 | 10.1136 |
| `europe` | 728 | 9.9373 |
| `arab-league` | 317 | 6.2628 |
| `asia` | 1 047 | 5.4200 |
| `south-america` | 243 | 1.8032 |
| `africa` | 878 | 0.5467 |
| `oceania` | 212 | 0.3050 |

## Three countries GADM cannot support, and two it supports invisibly

**The Maldives has an ADM_0 but no ADM_1**, so it has no units to compare —
the Kiribati case from Oceania. This repository measures inequality *across*
units, and an entity with none has nothing for any of it to measure.

**Hong Kong and Macao are measured, inside China.** They have no ADM_0 of
their own, which is easy to mistake for absence — an earlier draft of this
work said exactly that, and was wrong. GADM carries them as two of China's 33
admin-1 units under the non-numeric ids `CHN.HKG` and `CHN.MAC`, with 18 Hong
Kong districts and 2 Macau ones beneath them. Hong Kong reports 1 136 pixels
at mean DN 50.46 and Macau 33 pixels at 60.87, against a ceiling of 63. They
get no country row, and their light counts toward China's.

**Taiwan is not among China's units**, so carrying `TWN` as its own row
double-counts nothing. That was worth confirming before running China rather
than after.

### A trap in China's published table

Every Chinese admin-2 gid looks like `CHN.1.1_1` — except the SARs', which
look like `HKG.1_1` and `MAC.1_1`, with no country prefix at all. Filtering
China's 364 admin-2 units by `gid.startswith("CHN.")` silently drops 20 of
them, including some of the brightest land per pixel in the dataset. Nothing
here filters that way, so no published number is affected, but a reader
slicing the tables should know. My own first check made this exact mistake and
reported zero admin-2 units for both SARs; the census taken before any country
ran said 18 and 2, and that disagreement is what sent me to look at the gids.

## The antimeridian, once more, for Russia

Russia is in this pool because it is now analysable, which it was not when
Europe was built. `EUROPE` excludes it on two grounds: three quarters of its
area is Asian, and an antimeridian crop at Chukotka would have cost 114 686
km² — larger than Iceland. The first still holds. The second stopped being a
cost when `analysis.country_windows` arrived for Fiji and New Zealand.

| | naive frame | windowed |
|---|---:|---:|
| Russia | 80.9 Mpx | **37.4 Mpx** |

That is below the United States' working 52.8, and nothing is cropped:
Chukotka reports **719 684 pixels against 719 675 km²**, a ratio of 1.000, so
the seam is clean.

Turkey, Armenia, Azerbaijan, Georgia and Kazakhstan needed no windowing at
all — Kazakhstan is the largest landlocked country on earth and fits in 5.0
megapixels. They were left out of Europe on scope, not cost.

## The grid stops at 75°N

Russia is the first country in 203 whose pixel total does **not** match its
GADM land area. It comes to **0.9871**, where every other country sits at
1.000 give or take a thousandth.

The windows are not the reason. The 217 702 km² deficit sits in three units —
Arkhangel'sk at 89.3% covered, Krasnoyarsk at 93.6%, Sakha at 99.2% — which
hold Franz Josef Land, Novaya Zemlya, Severnaya Zemlya, northern Taymyr and
the New Siberian Islands. All lie above 75°N, where the LRCC-DVNL grid ends.

**Canada has the same gap and has had it since the Americas rollout**: 393 568
km² missing, ratio 0.9605, with Nunavut only 83.3% covered. These two are the
only countries of 203 materially affected. The eight others below 0.995 are
island states where a 2–12 km² shortfall is sub-pixel rounding. Together
**611 270 km² of Arctic land has no coverage in this dataset.**

What it touches: `area_km2` comes from the GADM polygon and `pixels` from the
raster, so for these units the two disagree, and `density_sol_per_km2` —
which divides by the polygon — treats unmeasured Arctic land as though it were
dark. `mean_dn` is unaffected, being total over pixels with both from the
raster.

The effect on these two is small enough to state precisely. Recomputing
admin-1 Gini with covered area as the denominator instead of polygon area
moves **Canada from 0.5790 to 0.5789** and **Russia from 0.5635 to 0.5634**:
the uncovered land is a few per cent of each, and the units holding it are
among the darkest either way, so their exact density barely moves the curve.

**That is not a general result, and Greenland shows why.** Added with the
rest of the world, it is 60.8% covered — not 96% or 99% — and the shortfall
is concentrated rather than spread: the Northeast Greenland National Park is
36.3% covered and Qaasuitsup 51.8%, while the three southern communes are
whole. Their densities are understated 2.75× and 1.93× as a result, and
Greenland's admin-1 Gini reads 0.4672 where covered-area denominators give
0.4143 — **a difference of +0.0529, five hundred times Canada's**.

Nothing published is corrected by any of this. It is a limit of the source
grid, and a reader deriving density for an Arctic unit should know both that
it exists and that its size depends entirely on how much of the country lies
beyond 75°N.

## Coverage

**1 047 admin-1 units and 14 263 admin-2** — more than twice Africa's 6 475.
Seven entities have no GADM ADM_2 layer: Singapore, Armenia, Israel, Bahrain,
Cyprus, Kuwait and Qatar.

Three countries sit above the ~1 500 admin-2 line that declined Romania, and
all three were run in full: Russia at 2 445 districts, Japan at 1 811, the
Philippines at 1 647. The cost is time rather than correctness — every
choropleth frame draws that many polygons.

### The admin-2 column spans two orders of magnitude

| | admin-2 units | km² each |
|---|---:|---:|
| Philippines | 1 647 | **180** |
| Japan | 1 811 | 206 |
| … | | |
| Pakistan | 30 | **26 413** |

GADM gives Pakistan 6 admin-1 and 30 admin-2 units for 792 382 km², the
fourth-coarsest layer among countries over 100 000 km² behind Canada, Niger
and Madagascar. Its published between/within split is therefore between six
provinces and thirty divisions, not the districts Pakistan administers. The
indices are correct for the units GADM supplies. They are not a fine-grained
picture of Pakistan, and comparing its nested split to Japan's compares two
different things.

### Level names GADM declines, misspells, or has outgrown

**Four take the generic word.** Japan's `ENGTYPE_2` is "Town" at 851 of 1 811
(47%), South Korea's "County" at 82 of 229 (36%), and Tajikistan's admin-1
"Region" at 2 of 5 (40%) — pluralities, where the rule is majority. Myanmar's
admin-1 is a genuine **7–7 tie** between "Division" and "State" out of 15, the
first exact tie in the collection.

**Bangladesh is published as *district*.** GADM writes `Distict` for all 64 of
its admin-2 units — a misspelling appearing nowhere else in that column,
against 10 359 correct "District" across 63 other countries. Unlike the
Marshall Islands' "Atol", where the typo was the *more* common spelling and
only the second test decided it, this one is settled twice over.

**Nepal and India carry administrations that no longer exist.** GADM gives
Nepal 5 "development regions" and 14 "administrative zones", both abolished by
the 2015 constitution; it gives India 35 admin-1 units including Daman and Diu,
which merged with Dadra and Nagar Haveli in January 2020, and predating the
2019 reorganisation of Jammu and Kashmir. India today has 28 states and 8 union
territories. The repository publishes GADM's coding, as it does for Western
Sahara, Palestine and Kosovo, rather than silently modernising a boundary set
mid-analysis.

## Pace

By trajectory over the VIIRS window: **26 extensive spreaders**, 10 intensive
convergers, 8 mixed, 3 flat and 2 disrupted — 49 in total, which is the check
that every country is classified exactly once.

Asia is the most lopsided region in the collection on this measure. More than
half its countries are extensive spreaders: total inequality falls because
light is reaching ground that had none, not because lit places are converging.

## No exclusion scopes

Scope `all` only, as everywhere outside the Arab League.
