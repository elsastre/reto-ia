## Data Visualization

Create quantitative visuals that are analytically sound, immediately readable, and polished enough to ship in a report, memo, slide, dashboard, notebook, widget, or HTML artifact. Treat charts as evidence for a takeaway. Redesign charts that are visually attractive but analytically weak, and revise charts that are technically correct but hard to interpret.

---

## Chart Selection

Common surface forms should be named in the chart contract when the final surface is a report, dashboard, slide, notebook, widget, or HTML artifact.

| Data relationship | Best chart | Use it well |
| --- | --- | --- |
| **Trend over time or ordered axis** | line | Show enough points to reveal shape; use area only when filled magnitude helps, and sparkline only in dense KPI cards |
| **Composition over time** | stackedArea | Use when parts should read as one total; switch to line when comparing component trajectories matters more |
| **Comparison across categories** | bar | Sort when order is not semantic; use horizontal bars for long labels; avoid redundant legends |
| **Ranking or top-N** | leaderboard | Keep it compact and single-measure; switch to ranked bar when comparison needs more chart context |
| **Part-to-whole composition** | stacked bar | Keep the denominator explicit; use pie only for a rough read with few slices |
| **Distribution or spread** | histogram | Use numeric bins that reveal shape; switch to boxPlot when comparing groups is the point |
| **Distribution across groups** | boxPlot | Use when median and spread matter more than full shape; switch to histogram when shape needs space |
| **Relationship between two numeric variables** | scatter | Use numeric x and y at a meaningful observation grain with enough distinct points to show a pattern; retain point labels, sample/volume fields, and one useful grouping candidate when safe |
| **Dense two-dimensional pattern or cohort matrix** | heatmap | Use for matrix shape or intensity; switch to scatter when point-level variation matters |
| **Additive bridge from start to end** | waterfall | Use only when drivers sum cleanly to the end value; otherwise use ranked bar |
| **Ordered stage progression or drop-off** | funnel | Use only for ordered single-series stages; prefer stage bar when funnel geometry distorts comparison |

---

## Workflow

1. **Define:** The analytical question and one-sentence takeaway before choosing a chart. Identify the final surface, the intended comparison, and the context needed to make the visual honest.
2. **Choose:** The simplest defensible family and variant from Chart Selection. Coordinate with `$build-dashboard` or `$build-report` when the visual belongs to those artifacts, and use `$validate-data` when the supporting analysis needs validation.
3. **Contract:** Write a compact chart contract before plot code, dashboard configuration, or renderer-specific implementation work. Include:
* Analytical question and takeaway.
* Canonical family and concrete variant.
* Data sufficiency for the chosen visual: expected row count, temporal point count for trend views, scatter observation count and grain, requested date range and grain, and fallback if the first query is too sparse.
* Surface-native chart type, canonical artifact chart type, or explicit static renderer when a concrete renderer has been selected.
* Delivery-specific constraints only after the delivery surface is chosen; for MCP widgets or app artifacts, use the shared MCP specification.
* Palette policy, approved palette roots, and non-color distinction plan.
* Output footprint, final container, export paths or delivery target, and the final QA surface.



---

## Standards

### Selection Rules

* Start from the analytical question and comparison the reader needs to make, not from a favorite chart type.
* **Keep the top-level set small:**
* Tables & Scorecards
* Trend
* Comparison & Ranking
* Composition
* Distribution
* Relationship
* Uncertainty & Benchmark
* Matrix & Cohort
* Decomposition & Progression


* Use charts for shape and comparison; use tables for exact lookup. If a table would show 3-8 comparable entities with one dominant numeric measure, prefer a bar, dot, lollipop, leaderboard, or other chart unless exact row lookup is the point.
* Do not ship underpowered trend or scatter charts. Ensure sufficient data points to reveal shape (default to 8-12 points for trends; 12-20 points for scatters).

### Visual Design

* **Titles:** Default to a neutral, descriptive label (metric, comparison, dimension, or time scope). Do not infer a narrative takeaway.
* **Palette Policy:** Choose one:
* *Single-root preferred:* One non-neutral root plus shades for simple trends/ranks/distributions.
* *Hard two-root cap:* Max two non-neutral roots for binary, signed, benchmark, or waterfall.
* *Relaxed multi-category:* Up to five approved roots for category-heavy views (pie, stacked bars, etc.).


* **Style:** Prefer white backgrounds, quiet grey grid lines, and deep charcoal text. Do not rely on color alone—use tone, markers, line styles, or faceting for distinction.

### Quality Bar

* The form must match the analytical comparison, and scales must be honest and consistent.
* Every shipped chart must have a visible title and a subtitle carrying context (units, time/cohort, denominator, sample size, or volume).
* Labels, ticks, and legends must not collide, clip, or detach.
* Inspect the visual in the final artifact (report, slide, dashboard, etc.) before handoff.