# Change Log

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
