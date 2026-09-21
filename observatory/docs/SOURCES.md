# Attribution and source inventory

| Source | Use | Terms / attribution |
|---|---|---|
| [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) | Application foundation and earthquake renderer | MIT source code; copyright Bilawal Sidhu. Starting commit `0dbde1e36c0177b7664b47702d77ba50f11ddadc`. Preserve root LICENSE. |
| [USGS](https://earthquake.usgs.gov/fdsnws/event/1/) | Live observations, historical catalog and event URLs | Credit U.S. Geological Survey. Frozen request URLs, retrieval dates, and SHA-256 hashes in `public/data/manifest.json`. Revisions can differ from future downloads. |
| [OurAirports](https://ourairports.com/data/) | Airport reference points | Public-domain dataset; credit OurAirports contributors. Large and medium airports only. Source CSV preserved in frozen-input archive. |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) / [Open Infrastructure Map](https://openinframap.org/) | 704 upstream dam features | ODbL 1.0. © OpenStreetMap contributors; source credit Open Infrastructure Map. Derived dam records retain ODbL; do not describe the entire data bundle as MIT. Exact source geometry remains in the upstream JSONL. |
| [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) | Country outlines and Cesium packaged base imagery | Public domain; Made with Natural Earth. Country outlines are 1:110m reference cartography, not authoritative boundaries. |
| [CesiumJS](https://github.com/CesiumGS/cesium) | 3D rendering | Apache-2.0. Preserve packaged copyright notices and visual attribution. |

World Monitor, OSIRIS, Skopia and Aleph were research references. No code from those applications was copied. The original upstream repository contains additional third-party assets with separate terms; see its LICENSE, DATA_SOURCES.md and model-specific notices. The Observatory static build does not copy the upstream public asset directory, submarine cable dataset, camera feeds, or third-party 3D models.

Dam representative points use the mean of source geometry coordinates. This is an approximate map location; distance is not distance to an entire dam footprint. Negative source OSM IDs are represented as relation URLs, positive IDs as way URLs; source geometry and IDs are retained upstream for verification. Dataset coverage and original collection dates are not inferred from retrieval time.
