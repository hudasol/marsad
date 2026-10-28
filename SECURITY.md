# Security and responsible use

Marsad is a **defensive, advisory** tool. It scores positions and recommends fallback modes; it never
commands a vehicle. The simulator is **measurement-level only**: it contains no RF, waveform, SDR or
signal-synthesis code and cannot be used to interfere with any receiver. Contributions that add
signal generation or attack tooling will not be accepted.

* Marsad does not attribute interference to any actor.
* On the loopback address the service needs no key. On any other address it refuses to start unless `MARSAD_API_KEY`
  is set (or `--insecure` is given for a closed network). The container binds 0.0.0.0, so it needs the key:
  `docker run -p 8000:8000 -e MARSAD_API_KEY=... marsad`. Put it behind TLS before exposing it. The key is accepted as
  `X-API-Key` or `Authorization: Bearer`; the stream endpoint also takes `?api_key=` because EventSource cannot set
  headers, so keep the service off shared proxies that log query strings.
* Report vulnerabilities privately through GitHub's "Report a vulnerability" (Security tab).
