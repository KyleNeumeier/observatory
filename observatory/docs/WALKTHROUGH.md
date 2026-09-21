# Two-minute portfolio walkthrough

1. **Start with the product question:** “What infrastructure is near this earthquake, and what evidence supports that view?” Open the recorded Türkiye case. Explain that the globe is built on God's Eye View and your contribution is the data/analysis workflow.
2. **Connect the data:** select an event, adjust radius from 100 to 200 km, open Connections, and follow an airport source link. Distinguish potential exposure from confirmed disruption.
3. **Show temporal reasoning:** move replay to hour zero and play forward. Explain event-time replay versus historical knowledge-time replay. Switch to Taiwan and compare the view.
4. **Demonstrate ownership:** save a region, star an airport, toggle layers, and export preferences. Show the source adapter separating live and recorded modes.
5. **Show the experiment:** open Research lab. Explain 9,367 anchors, magnitude/depth versus subsequent activity, and the sensitivity cohort. Report weak correlations honestly; explain overlapping sequences and incomplete catalog coverage.
6. **Show engineering evidence:** open API documentation, tests, the source manifest and architecture diagram. Discuss idempotent upserts, PostGIS geography, outage handling, and the model's inability to invent unsupported sentences.

## Interview prompts to practice

- Why use PostGIS rather than calculating all distances in the browser?
- Why separate observation time, provider update time, and ingestion time?
- What causes differences between spherical demo distances and spheroidal database distances?
- Why are naïve p-values misleading when earthquake sequence windows overlap?
- How would you add news evidence or a new hazard source without rewriting the globe?
- Which capabilities did you inherit, and which did you implement with AI assistance?

## Suggested resume wording

“Extended an attributed open-source Cesium application with a Python/FastAPI and PostGIS earthquake investigation backend, source-linked infrastructure analysis, and historical replay.”

“Built a reproducible analysis pipeline for 39,599 USGS records and a 9,367-event study cohort, with frozen input hashes, sensitivity analysis, and deterministic citation validation.”

Use these only after you can explain and demonstrate the implementation. Do not claim you authored the upstream globe or that correlation predicts damage.
