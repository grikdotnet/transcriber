# AMI EN2003a reusable audio fixture

This fixture is the two-minute interval `00:27:00.000–00:29:00.000` from the AMI Meeting Corpus recording `EN2003a.Mix-Headset.wav`. The current middleware uses `prepared.wav` as its integration input and `manifest.json` only for a non-gating diagnostic comparison. Transcript and diarization records are retained as provenance and reference data for possible later phases; the current middleware does not consume them.

The mixed-headset channel keeps all three speakers clearly represented while retaining natural conversation, short pauses, overlapping speech, coughs, breath noise, and other meeting artifacts. It replaces the earlier distant-array excerpt whose manual annotations included a turn that was acoustically inaudible on the selected channel.

## Artifact inventory

- `prepared.wav`: mono 16 kHz signed 16-bit PCM, exactly 1,920,000 samples.
- `manifest.json`: a human reference containing six historical segments; middleware checks may use it only for a non-gating diagnostic comparison, never as an acceptance oracle for FireRedVAD output.
- `segments/*.wav`: sample-exact historical reference slices for diagnosis; generated output is not required to match them.
- `transcript.json`: retained provenance/reference data containing 23 speaker-attributed AMI turns with fixture sample ranges, original meeting times, and orthographic text; it is not consumed in this delivery.
- `diarization.json`: retained provenance/reference speaker turns keyed to transcript utterance IDs; it is not consumed in this delivery, and turns may overlap.
- `source.json`: source URLs, checksums, CC BY 4.0 provenance, and exact crop bounds.

AMI's `transcriber_start` and `transcriber_end` values form a human diagnostic reference. Word timings are forced-aligned and should use an appropriate scoring collar. Differences between this reference and FireRedVAD output do not determine middleware acceptance.

## Reference-data relationships

Each transcript utterance belongs to speaker `A`, `B`, or `C` and maps one-to-one to a diarization turn. Simultaneous and overlapping human-reference turns were unioned into the activity intervals below. The historical reference segments were produced separately and may contain several utterances and speakers. They do not specify how FireRedVAD must segment the fixture.

| Fixture speaker | AMI participant | Source channel |
|---|---|---:|
| A | MEE075 | 0 |
| B | MEE076 | 1 |
| C | MEO074 | 3 |

## Human-reference activity intervals

Times are relative to `prepared.wav`; sample ends are exclusive.

| Samples | Seconds |
|---:|---:|
| 2304–296192 | 0.144–18.512 |
| 297472–332352 | 18.592–20.772 |
| 363520–488448 | 22.720–30.528 |
| 502528–620032 | 31.408–38.752 |
| 674816–804864 | 42.176–50.304 |
| 825600–1186048 | 51.600–74.128 |
| 1200224–1528576 | 75.014–95.536 |
| 1545472–1626112 | 96.592–101.632 |
| 1628528–1920000 | 101.783–120.000 |

## Historical diagnostic segmentation

These six records describe `manifest.json` and `segments/*.wav`. They are useful when a person investigates differences, but their count and boundaries are not expected FireRedVAD results and are not acceptance criteria.

| Segment | Samples | Seconds | Historical construction note |
|---:|---:|---:|---|
| 0 | 0–340352 | 0.000–21.272 | Two activity intervals merge; left padding is file-clamped |
| 1 | 355520–628032 | 22.220–39.252 | Two intervals merge across a 0.880-second pause |
| 2 | 666816–812864 | 41.676–50.804 | Full 0.5-second padding |
| 3 | 817600–1193136 | 51.100–74.571 | Kept separate from the next interval because their combined span exceeds 30 seconds |
| 4 | 1193136–1627320 | 74.571–101.7075 | Three intervals merge; boundary padding shares adjacent short gaps |
| 5 | 1627320–1920000 | 101.7075–120.000 | Short boundary gap is shared; right padding is file-clamped |

Current middleware passes `--max-segment-duration-seconds` to FireRedVAD as an advisory split target. FireRedVAD may return segments longer than that target. The middleware accepts valid, ordered intervals unchanged; it does not compare their count or boundaries with this historical table to decide success.

## Provenance and use

The AMI Consortium releases its signals and transcriptions under the Creative Commons Attribution 4.0 International license. Retain `source.json` and credit the AMI Meeting Corpus when redistributing this fixture or publishing results based on it.

## Reproducibility checksums

- `prepared.wav`: `312ed15cc214c65b302d17575cbb07594f45da9d281d8af980b7fe52ebf70d7b`
- `segment-0000.wav`: `8469776482bb39c2b1dba9228ae605f380166f828ec1fa57db2c3ff19a9bcf79`
- `segment-0001.wav`: `ed560b3f184f7cb1a2ee1eeb9c99dd8c3359924c43c81a041dca5e8c296eec83`
- `segment-0002.wav`: `90d2798b05060d3e7d1c691433251464ecae60070bbc1de9c1827ab6bbc9e40f`
- `segment-0003.wav`: `67cbe83820ae87ffa394c3460c902ea8a552eaebfeee05310090094a0ffecc0c`
- `segment-0004.wav`: `28efe945f2a1010803a77b2028dc1b4d24caff487f8fc339fe9d8d910aeb6311`
- `segment-0005.wav`: `acbdde6959c3d3e11cd85928f812fea5748c29324d4b7365023d5fab71c60575`
