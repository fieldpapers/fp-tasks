# Change Log

## v0.6.0 - 6/11/15

* Upgrade fieldpapers/paper to v0.2.0

## v0.5.3 - 5/29/15

* If a subdomain placeholder is present, replace it with `a` rather than
  stripping it

## v0.5.2 - 5/28/15

* `page_url` is now correctly snake\_case

## v0.5.1 - 5/28/15

* Improve logging when callbacks return 500s

## v0.5.0 - 5/28/15

* Propagate zoom

## v0.4.0 - 5/27/15

* Upload atlases into `atlases/`
* Replace "walking" with "field" in GeoTIFF output filenames

## v0.3.2 - 5/27/15

* Fix typo in render index task

## v0.3.1 - 5/27/15

* Pass GeoTIFF URLs through `decodeURIComponent` before returning them to the
  app
* Strip extraneous commas from provider URLs
* Clean npm's cache

## v0.3.0 - 5/26/15

* Additional ModestMaps shimming
* Propagate atlas text

## v0.2.2 - 5/26/15

* Shim around ModestMaps warts

## v0.2.1 - 5/26/15

* Work around `rlimit-nproc` limitations when running without user namespaces

## v0.2.0 - 5/26/15

* Add `libnss-mdns` and run `avahi-daemon` in the background to support mDNS
  resolution

## v0.1.0 - 5/22/15

* Initial version
