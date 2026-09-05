# Africa: 55 countries, and light that climate does not explain

Every African state at the same detail as the rest of the repository, and a
comparison pool of its own.

Africa and the Arab League **overlap by ten countries** — Algeria, Egypt,
Libya, Morocco, Tunisia, Sudan, Somalia, Djibouti, Comoros and Mauritania —
so the two are separate pools rather than one list. Each owns its own tables:

| pool | trends | aridity |
|---|---|---|
| `arab-league` | [`../results/trends_by_country.csv`](../results/trends_by_country.csv) | [`../results/aridity_vs_light.csv`](../results/aridity_vs_light.csv) |
| `africa` | [`../results/africa_trends_by_country.csv`](../results/africa_trends_by_country.csv) | [`../results/africa_aridity_vs_light.csv`](../results/africa_aridity_vs_light.csv) |

⚠️ **`dark_2022` is not comparable between the two aridity files.** Each cuts
at the median `mean_dn_2022` **of its own pool**, and those medians are far
apart: **6.2628** for the Arab League against **0.4948** for Africa. A unit in
one of the ten shared countries can be dark in one file and lit in the other.
That is not an inconsistency — "dark for this continent" and "dark for the Arab
world" are different questions — but the two columns must never be pooled.

Trends rates are fitted per country and never pooled, so a country in both
files carries identical rates in each.

```bash
satimg trends           --country all --pool africa
satimg aridity vs-light --pool africa
```

## Coverage

54 UN member states plus Western Sahara, which appears on the same footing as
Palestine elsewhere here: GADM's coding of the boundary set in use, not a
position on status. GADM's `MAR` excludes it, so omitting it would leave a hole
in the continent.

**854 admin-1 units** and **6 475 admin-2 units**. Seven countries have no GADM
ADM_2 layer — Cabo Verde, Comoros, Western Sahara, Lesotho, Libya, Mauritius,
Seychelles — and stop at admin-1 with no nested decomposition. Nothing
downstream invents one.

Level names come from GADM's own `ENGTYPE` by majority. Where GADM declines to
give one word the generic title is used instead: `"NA"` for Madagascar at both
levels and for Djibouti and São Tomé at admin-2, and alternations like Angola's
`"Municpality|City Council"`, whose misspelling is GADM's and is not printed as
the country's own word.

## Falling inequality is almost never convergence

**42 of 55 African countries are extensive spreaders** — total inequality falls
only because light reaches ground that had none, while inequality *among
already-lit places rises*. The same rule puts 9 of 22 Arab League countries in
that class.

| typology | Africa | Arab League |
|---|---:|---:|
| extensive spreader | **42** | 9 |
| mixed | 7 | 5 |
| flat | 5 | 1 |
| intensive converger | **1** | 6 |
| disrupted | 0 | 1 |

The single African intensive converger is **Mauritius**. Six Arab League
countries qualify, and all of them — Bahrain, Qatar, Palestine, Lebanon, the
UAE, Kuwait — were already near-fully lit in 1992. Africa has almost no
countries in that position, so it has almost no genuine convergence to show.

**The intensive margin rises in 47 of 55.** The extensive margin has a median
of **+4.92 %/yr** and reaches **+12.76**. Rwanda falls fastest overall at
−2.74 %/yr, yet its lit-only inequality rises **+2.14 %/yr** — the steepest
apparent convergence on the continent is among the clearest cases of nothing
converging.

No African country's total genuinely rises. Libya's fit is +0.01 %/yr at
R² 0.0004, which is a flat series rather than a rising one; the Arab League's
sole riser, Syria, is not an African state.

Eight countries fall below the R² threshold and are described as having a
direction rather than a pace: Central African Republic, Comoros, Eritrea,
Gabon, Guinea-Bissau, Libya, Seychelles and Zimbabwe.

**40 of 55 decline faster after the 2014 sensor handover**, the same instrument
signature as 18 of 22 in the Arab League. The two eras are fitted separately
and must not be compared.

## Aridity predicts nothing here, and that is the finding

In the Arab world, aridity is a weak predictor of light: Spearman(`desert_share`,
`mean_dn_2022`) = −0.146, and the relationship is one step at "not arid at all".

Across Africa it is **+0.024** — indistinguishable from zero, and if anything
the wrong sign. The band medians say why:

| band | units | median mean DN, 2022 |
|---|---:|---:|
| fully arid (`desert_share` = 1) | 126 | **1.16** |
| partly arid (0 < share < 1) | 150 | **0.37** |
| not arid at all (share = 0) | 578 | **0.49** |

**The fully-arid band is the brightest.** That inverts the Arab result, and the
reason is not climatic: Africa's arid north contains its more urbanised
economies, while the humid centre and the Sahel's southern margin contain its
poorest. Aridity and darkness are confounded by income on this continent, in
the opposite direction to the Arab one, and the two effects roughly cancel.

The four cells fall out accordingly, inverting the Arab world's:

| | arid | not arid |
|---|---|---|
| **dark** | 98 | **329** |
| **lit** | 107 | 320 |

Against the Arab League's 135 / 23 / 95 / 64. **Most dark African units are not
desert** — 329 of them, the largest cell — where in the Arab world the largest
cell was desert-and-dark. The base rate carries it: **24%** of African admin-1
units are majority-arid, against **73%** of Arab ones.

That also sharpens the light-derived exclusion rule rather than weakening it.
Of the 41 units it excludes across Africa, **37 (90%) are majority-arid against
that 24% base — a lift of 3.75**, where the same rule on the Arab League gives
1.29. On a continent that is mostly not arid, a rule cut purely from observed
darkness still lands on arid ground nine times in ten. That is the strongest
evidence so far that the rule finds climate and not merely darkness.

The units it does *not* explain are concentrated: Uganda contributes 45
non-arid dark units, DR Congo 24, Tanzania 19, Malawi 17, Central African
Republic 16, Liberia 13. **Twenty African admin-1 units have no lit pixels at
all in 2022** — whole provinces, among them five in DR Congo, Central African
Republic's Lobaye, and three Guinea-Bissau regions.

## Caveats

Everything in [`lrcc-dvnl.md`](lrcc-dvnl.md) applies. Three bite harder here.

- **A falling total is partly imposed.** A lit pixel in this series never dims,
  it goes out, so as lit area grows the zeros-included index falls almost by
  construction. On a continent where the extensive margin moves at a median
  +4.92 %/yr, that mechanism is doing more work than anywhere else in this
  repository — which is exactly why the lit-only rate is published beside the
  total rather than under it.
- **Twenty units are entirely unlit and many more are near it.** A Gini or
  Theil over a distribution that is almost all zeros is defined but fragile,
  and the 2014 handover changes what "unlit" means. Treat any pre/post-2014
  comparison in the darkest countries as an instrument artefact first.
- **No exclusion scopes.** African countries outside the Arab League ship with
  scope `all` only. The low-light rule's published rationales read its break as
  desert or conflict; the aridity result above shows why neither reading
  transfers to this continent, so deriving scopes here would need a rule
  justified on African terms rather than borrowed.

## Reproducing

```bash
ISOS=$(python -c "from satimg.regions import AFRICA as A; print(*A)")
for ISO in $ISOS; do
  satimg lrcc-dvnl extract    --country "$ISO" --levels 0,1,2
  satimg lrcc-dvnl choropleth --country "$ISO" --levels 1,2
  satimg lrcc-dvnl inequality --country "$ISO"
  satimg aridity units        --country "$ISO"
done
satimg aridity vs-light --pool africa
satimg trends --country all --pool africa
satimg figures build && satimg results build
```

Countries in `regions.LEVELS_AVAILABLE` take `--levels 0,1` instead.
