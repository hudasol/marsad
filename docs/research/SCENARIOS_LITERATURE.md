# Scenario family from the literature: SIMULATED (LITERATURE)

Written on 2026-11-03 (UTC+4), before any engine run on this family. Generator: `src/marsad/sim/literature.py`.
Evaluation script: `scripts/run_literature.py`. Label for numbers from it: **SIMULATED (LITERATURE)**, and **SEALED**
for seeds 7000 to 7099.

## Why a second family

The first scenario family (`src/marsad/sim/generator.py`) was written together with the engine, so the engine may
have been fitted to the author's own picture of an attack. This family takes its parameter ranges from published
descriptions of attacks and of jammers instead. It is still simulated, and the clean vehicle, receiver and reference
come from the same generator (`generate("nominal", ...)`), so the world and the engine still share an author. What is
independent is the attack specification. The mapping from a published quantity to a receiver measurement is marked
ASSUMED wherever the source does not give it.

## Sources that were opened for this document (2026-11-03)

1. Tippenhauer, Poepper, Rasmussen, Capkun, "On the requirements for successful GPS spoofing attacks", ACM CCS 2011.
   Opened: <https://www.cs.ox.ac.uk/files/6489/gps.pdf>. Used for: required relative power (at least +2 dB over the
   authentic signals, tested from -2 dB to +8 dB); location offset range tested (0 to 450 m) with takeover in all tests;
   takeover profile (about 30 s of tracking before the attack, about 1 minute of initial phase, then an acceleration of
   0.5 m/s^2 toward the target, reached after about 3 minutes); at equal power the receiver sometimes returned to the
   true position after about 170 s; constant time offsets of up to 240 ns tested, reliable takeover up to about 120 ns,
   and a requirement of at most 75 ns (about 22.5 m). The paper reports lock loss, position jumps and instability; it
   reports no C/N0 or satellite counts.
2. University of Texas Radionavigation Laboratory, Texas Spoofing Test Battery (TEXBAT) pages, opened:
   <https://radionavlab.ae.utexas.edu/texbat> (ds7 and ds8 described as a power matched time push and a zero delay
   security code estimation and replay attack) and Humphreys, presentation of 2012,
   <https://www.gps.gov/cgsic/meetings/2012/humphreys.pdf> (six recorded attack types: dynamic matched power position
   push, dynamic overpowered time push, static matched power position push, static matched power time push, static
   overpowered time push, static switch). The pages give no push rates or power numbers.
3. A study of the impact and detection of GNSS jammers on consumer grade receivers, opened from the repository of
   Politecnico di Torino (file "Impact and detection part 1"):
   <https://iris.polito.it/retrieve/handle/11583/2646380/118549/Impact%20and%20detection%20part%201.pdf>. Used for:
   jammer power ramp (J/N0 55 to 92 dB-Hz) with an average C/N0 fall of about 15 dB at the highest power on one
   receiver; AGC counts changed strongly (the text gives no size); chirp type jammers with sweeps of 10 to 40 MHz
   every 10 microseconds or so. The text gives no C/N0 or J/S value for loss of lock.

No other source is cited. Spoofing of vehicles in the field, and attribution of any interference, are outside this
work.

## The five scenarios

All onsets are drawn uniformly from 150 to 260 s of a 600 s run. All offsets are measurement edits on simulated fixes.

| kind | what it models | parameters and source |
|---|---|---|
| `lit_switch` | the receiver loses the authentic signal for a few seconds, then relocks on the spoofer at a fixed offset | gap 2 to 6 s (ASSUMED); offset 100 to 450 m (source 1 range 0 to 450 m, the lower end removed because 0 to 100 m is a drift); power advantage 2 to 8 dB (source 1); reported C/N0 rises by the advantage (ASSUMED) |
| `lit_takeover` | 60 s tracking at matched power, then accelerating carry off to a target offset | acceleration 0.5 m/s^2 (source 1) and 0.25, 0.1, 0.05 (ASSUMED, to span slower carry offs); target offset 150 to 450 m; velocity consistent in half of the runs (ASSUMED); power advantage 2 to 6 dB |
| `lit_time_push` | a time push seen as a slow position effect | offset 20 to 72 m (72 m is 240 ns of range, source 1; the position mapping is ASSUMED), growing at 0.2 to 2 m/s; velocity not consistent; power advantage 0 to 3 dB |
| `lit_equal_power` | a takeover at equal power that falls back to the true position | as `lit_takeover` with acceleration 0.1, 0.25 or 0.5 m/s^2; offset removed 100 to 200 s after the 60 s hold (source 1, about 170 s) |
| `lit_jam_chirp` | a chirp type privacy jammer | C/N0 fall 6 to 15 dB (source 3); rise over 20 to 60 s, hold 60 to 180 s, fall over 10 to 30 s (ASSUMED); satellite count falls in proportion (ASSUMED); AGC rises by 0.05 to 0.40 on the normalised scale where higher means more RF power (ASSUMED, wider and weaker than the design family's 0.10 to 0.50); fix lost at half of the samples when the fall is above 12 dB at its peak (ASSUMED); extra position noise 2 to 10 m |

Benign kinds for false alarms: `nominal`, `benign_obstruction` and `benign_multipath` of the first family, drawn with
the dev parameters on the same seeds. They share the first family's code and author.

## Where it differs from the design family

* Offsets are larger and mostly constant after a step, or reach a target and stop. The design family carries off
  indefinitely.
* The spoofed C/N0 spread is not collapsed (none of the sources report one). The engine's spoofing power signature,
  which looks for a collapsed spread, therefore has nothing to see here except the level rise.
* The jammer's AGC rise is smaller than anything the engine was tuned on.
* One scenario (`lit_equal_power`) removes the attack again, so the interval of attack is finite.

## Seeds

* Development: seeds 0 to 29 (30 per kind). Any engine change in later packages is developed on these only.
* Sealed: seeds 7000 to 7099, for this family and for the first family (held out parameters). Not run before the end
  of the release. `scripts/run_literature.py` refuses these seeds without `--final` and refuses a second sealed run.
