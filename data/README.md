# Data directory

The framework does **not** ship orbital-element data. The default experiments use a
synthetic Walker-delta constellation (`constellation.type: walker_delta`) that is
generated from its design parameters and propagated with SGP4, so nothing has to be
downloaded.

## Using real constellations (TLE / OMM)

General-perturbation (GP) element sets of operational constellations can be
downloaded from CelesTrak, e.g.

```text
https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=csv
https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=json
https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle
```

Save the file under `data/` (e.g. `data/starlink.csv`) and point a configuration at it:

```yaml
constellation:
  type: file
  file: data/starlink.csv       # .csv / .json (OMM) or .tle / .txt / .3le (TLE)
  name_filter: STARLINK         # optional substring filter on the object name
  max_sats: null                # optional truncation for quick tests
```

Notes

* CelesTrak asks users to download a given data set **at most once per update
  cycle** (about every two hours) and returns HTTP 403 otherwise; keep a local copy
  and commit it to your own fork if you need reproducibility.
* The TLE format cannot represent catalogue numbers with more than five digits;
  prefer the OMM CSV/JSON formats for new objects.
* With `type: file` the simulation start time defaults to the median epoch of the
  loaded element sets (plus the per-seed random offset), which keeps SGP4
  propagation errors small. Elements older than a few days are not representative
  for Starlink satellites that manoeuvre frequently.
* `data/cache/` holds compressed geometry traces (`.npz`) that are regenerated
  automatically and ignored by git.
