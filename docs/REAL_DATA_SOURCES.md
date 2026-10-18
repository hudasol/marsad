# Real data sources (survey, 2026-10-18)

Free, public sources of real GNSS interference or spoofing data that could be used offline. Every link below was
opened while writing this page; details not shown on the page that was opened are marked "not stated". Nothing was
downloaded. No source here needs payment; one needs a free account and one needs a subscription (excluded).

None of these sources has been used by Marsad yet. A result on any of them would need its own honesty label, defined
before the run, because the existing labels do not cover a real receiver under real interference: REAL LOG means an
unmodified flight with no attack.

## Usable now with Marsad's adapters (vehicle logs)

### 1. UAV Attack Dataset (IEEE DataPort)

* **Link:** https://ieee-dataport.org/open-access/uav-attack-dataset (DOI 10.21227/00dg-0d12; Ontario Tech
  University and University of Tabuk).
* **Content:** PX4 v1.11.3 flight logs (Pixhawk 4, Holybro S500), each set a benign flight and an attack flight. A
  simulated set (GPS spoofing injected into Gazebo, MAVLink ping flood) and a live set recorded in an RF denied
  facility: GPS spoofing transmitted with a software defined radio and a GPS signal simulator, and jamming with white
  Gaussian noise.
* **Format and size:** ULog files plus CSV conversions; one archive of 683.88 MB (above this survey's 200 MB download
  limit, so not downloaded).
* **Licence and access:** licence not stated. Listed as open access for logged in users with a free IEEE account,
  but the same page also says a DataPort subscription is required. Confirm free access before relying on it.
* **Adapter:** yes in principle. `marsad.adapters.ulog` reads `vehicle_gps_position`, the PX4 v1.11 topic name. Not
  tested on these files.
* **What it would let us claim:** detection of real GNSS spoofing and jamming by a real receiver on a real flight
  controller, in a laboratory RF environment, with a known attack onset. The reference velocity would be the EKF
  output, so the carry off check is weakened; jumps, jamming and receiver flag agreement could be measured. The
  simulated set adds nothing beyond Marsad's own SIH + INJECTED tests.

### 2. PX4 Flight Review public logs

* **Link:** https://review.px4.io/browse ("Browse public Log Files"); download script
  https://github.com/PX4/flight_review/blob/main/app/download_logs.py.
* **Content:** public PX4 flight logs from many vehicles and versions. The browse page shows type, airframe,
  hardware, software and flight modes; it has no column or filter for GNSS jamming or spoofing.
* **Format and size:** ULog; size per log varies (the two used here are 38 MB and 190 MB).
* **Licence and access:** CC BY, no account. The script lists logs from `https://review.px4.io/dbinfo` and fetches
  one with `https://review.px4.io/download?log=<log_id>`. Its filters are `--mav-type`, `--airframe-name`,
  `--airframe-type`, `--vehicle-name`, `--uuid`, `--git-hash`, `--flight-modes`, `--error-labels`, `--rating`,
  `--source`, `--log-id` and `--latest-per-vehicle`.
* **Adapter:** yes; two such logs are already the REAL LOG results.
* **What it would let us claim:** false alarm rate over many more real flights, and agreement with the receiver's own
  `jamming_state` and `spoofing_state` flags.
* **Finding a log with `jamming_state` of 2 or 3:** there is no index for it. The method is to list candidates with
  `download_logs.py` (for example by `--mav-type`), download them under the size limit, and run `marsad inspect <log>` (reports whether the
  log has the PX4 jamming and spoofing fields) and `marsad replay <log>` (reports when the receiver flag, state 2 or
  higher, was first raised and for how long; 774 s for `flight1.ulg`, `docs/results/real_logs.txt`). `flight1.ulg` is already one such log: its
  receiver reported `jamming_state` 2 (warning) on 7,739 of 9,109 rows (VALIDATION.md). Its Flight Review identifier
  was not recorded; it could be found again with `download_logs.py --uuid <uuid>`, using the `sys_uuid` in the
  header of one's own copy. No log identifier is given here because none was verified.

## Usable only after a software receiver (raw I/Q recordings)

Marsad reads receiver outputs (position, velocity, C/N0, flags), not radio samples. These recordings would first
have to be processed by an open software defined receiver into such outputs. That is reception and analysis of
recorded signals; Marsad would still contain no RF generation.

### 3. FGI GNSS Jamming and Spoofing Dataset Repository (National Land Survey of Finland)

* **Link:** https://www.maanmittauslaitos.fi/en/node/17698 (datasets hosted on the Etsin research data service).
* **Content:** raw I/Q recordings: spoofing (synchronous, asynchronous, meaconing), Galileo OSNMA data including a
  Jammertest 2023 spoofing scenario, live Jammertest 2023 recordings from Andøya (one high power jamming and two
  spoofing scenarios), and simulated recordings for a LEO PNT study. Analysis with the open FGI-GSRx receiver is
  supported.
* **Format and size:** raw I/Q; sizes not stated on the page opened.
* **Licence:** not stated on the page opened (see each Etsin record).
* **Adapter:** no. Would need FGI-GSRx output converted to `NavSample`.
* **What it would let us claim:** behaviour of Marsad's signal level evidence on real spoofing signals at the
  receiver. Without an independent motion reference recorded alongside, the carry off check could not be tested.

### 4. LINKS Foundation GNSS L1 jammed signal recordings (Zenodo)

* **Link:** https://zenodo.org/records/14850872 (one record of a series in the ATLANTIS community).
* **Content:** I/Q dumps of a jammed GPS L1 signal, "linear narrow" jammer at five power levels; other records in the
  series cover other jammer types.
* **Format and size:** complex int8 at 10 MHz, gzipped; five files of about 9.1 to 9.7 GB, 47.3 GB in total.
* **Licence and access:** CC BY 4.0, open.
* **Adapter:** no; jamming only.
* **What it would let us claim:** at most the jamming side of the signal detector after software receiver processing.

### 5. TEXBAT, Texas Spoofing Test Battery (University of Texas at Austin)

* **Link:** https://radionavlab.ae.utexas.edu/research/public-datasets-and-code/
* **Content, format, size, licence:** the page opened only lists TEXBAT with a link; none of these is stated there.
* **Adapter:** no (raw recordings, by its description elsewhere; not verified here).
* **What it would let us claim:** the standard spoofing scenarios used in the literature, after software receiver
  processing. Details must be checked on the dataset's own page before use.

### 6. OAKBAT, Oak Ridge Spoofing and Interference Test Battery (Oak Ridge National Laboratory)

* **Link:** https://doi.ccs.ornl.gov/dataset/d21dfe58-3af9-5ed8-9c97-693c12045aee (DOI 10.13139/ORNLNCCS/1664429).
* **Content:** RF recordings for the GPS L1 C/A OAKBAT scenarios (spoofing and interference); configuration and
  procedures at github.com/oakbat.
* **Format and size:** binary; size not stated. Download through Globus.
* **Licence and access:** terms linked but not shown; whether registration is needed is not stated on the page.
* **Adapter:** no.
* **What it would let us claim:** as for TEXBAT.

## Supporting, not vehicle data

### 7. Stanford GPS Lab GNSS interference data (ADS-B derived)

* **Link:** https://rfi.stanford.edu/resources (downloader linked from the page as a GitHub gist).
* **Content:** jamming and spoofing detections derived from aircraft ADS-B reports, with heatmap and event views.
* **Format:** JSON, by date range and type (jamming, spoofing, dashboard).
* **Licence:** CC BY-NC 4.0 (non commercial; credit "Source: Stanford GPS Lab, rfi.stanford.edu"). No account mentioned.
* **Adapter:** no; these are regional aggregates, not vehicle streams.
* **What it would let us claim:** independent context for where and when interference occurred, for example to check
  that the interference map module highlights the same regions. Not a detection result.

### 8. Jammertest test plans (NPRA)

* **Link:** https://github.com/NPRA/jammertest-plan
* **Content:** official Jammertest test catalogue and daily transmission plans (PDF and JSON, 2025 and 2026), MIT
  licence. Plans, not measurements.
* **What it would let us claim:** ground truth timing for any measurement dataset recorded at Jammertest.

## Excluded

* **SimulaMet Jammertest 2025 NMEA derived dataset** (https://ieee-dataport.org/documents/simulamet-jammertest-2025-nmea-derived-dataset):
  real receivers (Sierra Wireless, Quectel, u-blox) under jamming, meaconing and time spoofing, CSV and JSON. The page
  states that an IEEE DataPort subscription is required, so it is outside the free data rule.

## Recommended next step

Source 1 (UAV Attack Dataset), if free access is confirmed, is the only source found that Marsad can read directly
and that contains real attacks on a real receiver. Before using it: define its label, preregister predictions for
its benign and attack flights, and record its checksum in DATA.md. Source 2 is the cheapest way to widen the false
alarm evidence and to look for receiver jamming flags in the wild.
