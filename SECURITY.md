# Security and responsible use

Marsad is a **defensive, advisory** tool. It scores positions and recommends fallback modes; it never
commands a vehicle. The simulator is **measurement-level only**: it contains no RF, waveform, SDR or
signal-synthesis code and cannot be used to interfere with any receiver. Contributions that add
signal generation or attack tooling will not be accepted.

* Marsad does not attribute interference to any actor.
* The service has no authentication by default and binds to 127.0.0.1. Set `MARSAD_API_KEY` and put it
  behind TLS before exposing it. Do not expose it to untrusted networks.
* Report vulnerabilities privately through GitHub's "Report a vulnerability" (Security tab).
