# 0.66.5 (Thu Jan 30 2025)

#### 🐛 Bug Fix

- Start Zarr download as soon as first page of entries is obtained [#1569](https://github.com/dandi/dandi-cli/pull/1569) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Use Python 3.10 to build docs [#1567](https://github.com/dandi/dandi-cli/pull/1567) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Pin `dandischema` to require the latest `schema` version [#1570](https://github.com/dandi/dandi-cli/pull/1570) ([@kabilar](https://github.com/kabilar))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))

---

# 0.66.4 (Thu Jan 23 2025)

#### 🐛 Bug Fix

- Continue retrying downloads on retriable statuses [#1558](https://github.com/dandi/dandi-cli/pull/1558) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Fix typo in `dandi move` docstring [#1566](https://github.com/dandi/dandi-cli/pull/1566) ([@kabilar](https://github.com/kabilar))
- Update URL for DANDI Docs [#1561](https://github.com/dandi/dandi-cli/pull/1561) ([@kabilar](https://github.com/kabilar))

#### 🧪 Tests

- Don't use version 0.25.5 of `responses` [#1562](https://github.com/dandi/dandi-cli/pull/1562) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Support dandischema v0.11.0 [#1560](https://github.com/dandi/dandi-cli/pull/1560) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))

---

# 0.66.3 (Thu Dec 19 2024)

#### 🏠 Internal

- Update docs to generalize from `DANDI Archive` to `DANDI instance` [#1548](https://github.com/dandi/dandi-cli/pull/1548) ([@kabilar](https://github.com/kabilar))

#### Authors: 1

- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))

---

# 0.66.2 (Tue Dec 17 2024)

#### 🐛 Bug Fix

- enh: log exception info (at debug) when we catch an exception in map_to_click handler [#1552](https://github.com/dandi/dandi-cli/pull/1552) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏎 Performance

- Reduce messaging to pyout on progress of downloads [#1554](https://github.com/dandi/dandi-cli/pull/1554) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- download: provide description for an assertion error on attempts_allowed_or_not [#1550](https://github.com/dandi/dandi-cli/pull/1550) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.66.1 (Wed Dec 04 2024)

#### 🐛 Bug Fix

- BF: do allow for user to specify a proper full name for "species" in metadata [#1547](https://github.com/dandi/dandi-cli/pull/1547) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.66.0 (Mon Dec 02 2024)

#### 🚀 Enhancement

- Do fail (raise Exception, CLI has non-0 exit) download if any of downloads fail [#1536](https://github.com/dandi/dandi-cli/pull/1536) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Add Meriones unguiculatus to species list [#1546](https://github.com/dandi/dandi-cli/pull/1546) ([@kabilar](https://github.com/kabilar) [@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Test dev-deps against latest supported by us version of Python (3.12 ATM) [#1543](https://github.com/dandi/dandi-cli/pull/1543) ([@yarikoptic](https://github.com/yarikoptic))
- Add hdmf-zarr git repo into our dev build testing [#1542](https://github.com/dandi/dandi-cli/pull/1542) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.65.1 (Wed Nov 27 2024)

#### 🐛 Bug Fix

- Remove `NotImplementedError` to allow for uploading Zarr assets to embargoed Dandisets [#1540](https://github.com/dandi/dandi-cli/pull/1540) ([@kabilar](https://github.com/kabilar) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.65.0 (Tue Nov 26 2024)

#### 🚀 Enhancement

- Refactor some download code for readability + ensure that we checksum resumed downloads [#1535](https://github.com/dandi/dandi-cli/pull/1535) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Fix `PrivateAttr` usage [#1538](https://github.com/dandi/dandi-cli/pull/1538) ([@jwodder](https://github.com/jwodder))
- add one photon to metadata dict [#1532](https://github.com/dandi/dandi-cli/pull/1532) ([@bendichter](https://github.com/bendichter))

#### 🧪 Tests

- Ignore some type-checking errors under Python 3.13 [#1539](https://github.com/dandi/dandi-cli/pull/1539) ([@jwodder](https://github.com/jwodder))
- tests: update tests docker-compose with few changes from dandi-archive [#1531](https://github.com/dandi/dandi-cli/pull/1531) ([@yarikoptic](https://github.com/yarikoptic))
- Specify custom ulimit on nofiles to prevent infinite loop by billiard [#1533](https://github.com/dandi/dandi-cli/pull/1533) ([@yarikoptic](https://github.com/yarikoptic))
- Rename `file` key to codecov-action to `files` [#1530](https://github.com/dandi/dandi-cli/pull/1530) ([@jwodder](https://github.com/jwodder))
- [gh-actions](deps): Bump codecov/codecov-action from 4 to 5 [#1529](https://github.com/dandi/dandi-cli/pull/1529) ([@dependabot[bot]](https://github.com/dependabot[bot]))

#### Authors: 4

- [@dependabot[bot]](https://github.com/dependabot[bot])
- Ben Dichter ([@bendichter](https://github.com/bendichter))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.64.0 (Fri Nov 15 2024)

#### 🚀 Enhancement

- download: more consistent and exhaustive logging, new `DANDI_DEVEL_AGGRESSIVE_RETRY` mode, respect (?) Retry-After [#1509](https://github.com/dandi/dandi-cli/pull/1509) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Include LINC API as a supported instance type for DANDI CLI [#1527](https://github.com/dandi/dandi-cli/pull/1527) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))
- Enhance pynwb validation parsing to report the path within the file, fix pynwb typo [#1513](https://github.com/dandi/dandi-cli/pull/1513) ([@rly](https://github.com/rly))
- Drop claiming support and testing against EOL Python 3.8 [#1504](https://github.com/dandi/dandi-cli/pull/1504) ([@asmacdo](https://github.com/asmacdo))
- ENH: log dandischema version and ensure we log (consistently) path for log messages in download [#1499](https://github.com/dandi/dandi-cli/pull/1499) ([@yarikoptic](https://github.com/yarikoptic))
- Fixup URI scheme rendering in --help output [#1502](https://github.com/dandi/dandi-cli/pull/1502) ([@asmacdo](https://github.com/asmacdo))
- Adjust copyright year in documentation config [#1504](https://github.com/dandi/dandi-cli/pull/1504) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Use "cache_spec:False" in our copy_nwb_file helper while exporting NWB copy [#1497](https://github.com/dandi/dandi-cli/pull/1497) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- fix: replace dandi-api link with dandi-archive [#1524](https://github.com/dandi/dandi-cli/pull/1524) ([@asmacdo](https://github.com/asmacdo))

#### 🧪 Tests

- Add xfail marks for some tests: test_nwb2asset_remote_asset, test_reextract_metadata, test_IteratorWithAggregation [#1512](https://github.com/dandi/dandi-cli/pull/1512) ([@yarikoptic](https://github.com/yarikoptic))
- Switch to python 3.9 in dev-deps CI matrix run since dev deps are now beginning to drop Python 3.8 which is EOL soon [#1506](https://github.com/dandi/dandi-cli/pull/1506) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 5

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)
- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Ryan Ly ([@rly](https://github.com/rly))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.63.1 (Mon Sep 09 2024)

#### 🐛 Bug Fix

- Disallow hdmf 3.14.4, make organize to not parallelize for a single file, log information about all exceptions while reading metadata for organize [#1496](https://github.com/dandi/dandi-cli/pull/1496) ([@yarikoptic](https://github.com/yarikoptic))
- BF: use correct variable in exception upon unknown how to handle value of "species" [#1482](https://github.com/dandi/dandi-cli/pull/1482) ([@yarikoptic](https://github.com/yarikoptic))
- move: Immediately authenticate client after creation [#1480](https://github.com/dandi/dandi-cli/pull/1480) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Dump audit table to file specified by `DANDI_TESTS_AUDIT_CSV` envvar [#1486](https://github.com/dandi/dandi-cli/pull/1486) ([@jwodder](https://github.com/jwodder))
- Fix host used in minio URLs [#1487](https://github.com/dandi/dandi-cli/pull/1487) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.63.0 (Thu Aug 08 2024)

#### 🚀 Enhancement

- Add `--preserve-tree` option to `dandi download` [#1467](https://github.com/dandi/dandi-cli/pull/1467) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Fix handling of `--preserve-tree` for asset ID-only URLs [#1476](https://github.com/dandi/dandi-cli/pull/1476) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Fix one insignificant typo in CHANGELOG [#1477](https://github.com/dandi/dandi-cli/pull/1477) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Revert "Unbreak vcrpy install" [#1472](https://github.com/dandi/dandi-cli/pull/1472) ([@jwodder](https://github.com/jwodder))
- Unbreak vcrpy install [#1471](https://github.com/dandi/dandi-cli/pull/1471) ([@jwodder](https://github.com/jwodder))
- Further improvements to `docker-compose.yml` [#1470](https://github.com/dandi/dandi-cli/pull/1470) ([@jwodder](https://github.com/jwodder))
- Assorted Docker Compose improvements [#1465](https://github.com/dandi/dandi-cli/pull/1465) ([@jwodder](https://github.com/jwodder))
- Do not use mypy 1.11.0 [#1466](https://github.com/dandi/dandi-cli/pull/1466) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.62.4 (Mon Jul 15 2024)

#### 🔩 Dependency Updates

- Revert "Temporarily restrict dandischema requirement to `< 0.10.2`" [#1459](https://github.com/dandi/dandi-cli/pull/1459) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.62.3 (Fri Jul 12 2024)

#### 🔩 Dependency Updates

- Temporarily restrict dandischema requirement to `< 0.10.2` [#1458](https://github.com/dandi/dandi-cli/pull/1458) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.62.2 (Fri Jun 14 2024)

#### 🐛 Bug Fix

- Normalize path while requesting list of assets from the server [#1454](https://github.com/dandi/dandi-cli/pull/1454) ([@yarikoptic](https://github.com/yarikoptic))
- OPT+RF of zarr downloads: do not wait for full files listing + compute %done from total zarr size [#1443](https://github.com/dandi/dandi-cli/pull/1443) ([@yarikoptic](https://github.com/yarikoptic))
- Separate datetime components in logfile names with punctuation [#1445](https://github.com/dandi/dandi-cli/pull/1445) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.62.1 (Thu May 23 2024)

#### 🐛 Bug Fix

- Rewind filehandle request bodies before retrying requests [#1444](https://github.com/dandi/dandi-cli/pull/1444) ([@jwodder](https://github.com/jwodder))
- Slight tune up to formatting of examples etc to harmonize appearance/make shorter [#1439](https://github.com/dandi/dandi-cli/pull/1439) ([@yarikoptic](https://github.com/yarikoptic))
- Fix spelling of netlify and instance [#1433](https://github.com/dandi/dandi-cli/pull/1433) ([@rly](https://github.com/rly) [@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- ENH: add/use codespell-project/codespell-problem-matcher to annotate PRs on where typos added [#1429](https://github.com/dandi/dandi-cli/pull/1429) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- ENH: add timeout of 300 (5 minutes) to any test running [#1440](https://github.com/dandi/dandi-cli/pull/1440) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Ryan Ly ([@rly](https://github.com/rly))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.62.0 (Fri May 03 2024)

#### 🚀 Enhancement

- Convert DOI URLs in `related_publications` to related resources [#1417](https://github.com/dandi/dandi-cli/pull/1417) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Adjust tests for the added email requirement for contact person [#1438](https://github.com/dandi/dandi-cli/pull/1438) ([@candleindark](https://github.com/candleindark) [@yarikoptic](https://github.com/yarikoptic))
- Add DJANGO_DANDI_DEV_EMAIL env var to archive tests [#1436](https://github.com/dandi/dandi-cli/pull/1436) ([@jjnesbitt](https://github.com/jjnesbitt))
- clarify resource identifier docs [#1437](https://github.com/dandi/dandi-cli/pull/1437) ([@asmacdo](https://github.com/asmacdo))

#### 🧪 Tests

- Fix spelling of `--scheduled` option used in scheduled tests [#1428](https://github.com/dandi/dandi-cli/pull/1428) ([@jwodder](https://github.com/jwodder))
- Xfail flaky ontobee tests, unless running daily tests [#1423](https://github.com/dandi/dandi-cli/pull/1423) ([@jwodder](https://github.com/jwodder))

#### Authors: 5

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Isaac To ([@candleindark](https://github.com/candleindark))
- Jacob Nesbitt ([@jjnesbitt](https://github.com/jjnesbitt))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.61.2 (Fri Mar 22 2024)

#### 🧪 Tests

- Add missing command to `dandi-archive` docker compose fixture [#1421](https://github.com/dandi/dandi-cli/pull/1421) ([@mvandenburgh](https://github.com/mvandenburgh))

#### Authors: 1

- Mike VanDenburgh ([@mvandenburgh](https://github.com/mvandenburgh))

---

# 0.61.1 (Thu Mar 21 2024)

#### 🐛 Bug Fix

- Revert "Do not allow dandischema 0.10.1 - new schema not yet supporteed by dandi-archive" [#1420](https://github.com/dandi/dandi-cli/pull/1420) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.61.0 (Tue Mar 19 2024)

#### 🚀 Enhancement

- Add arguments for API query parameters when fetching all Dandisets; support creating embargoed Dandisets [#1414](https://github.com/dandi/dandi-cli/pull/1414) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Do not allow dandischema 0.10.1 - new schema not yet supported by dandi-archive [#1419](https://github.com/dandi/dandi-cli/pull/1419) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Clean up URL parsing in `extract_species()` [#1416](https://github.com/dandi/dandi-cli/pull/1416) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### 🔩 Dependency Updates

- Use `yarl` to clean up some code [#1415](https://github.com/dandi/dandi-cli/pull/1415) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.60.0 (Thu Feb 29 2024)

#### 🚀 Enhancement

- Report progress in deleting Zarr entries during upload [#1412](https://github.com/dandi/dandi-cli/pull/1412) ([@jwodder](https://github.com/jwodder))
- Update for Pydantic v2 [#1381](https://github.com/dandi/dandi-cli/pull/1381) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- [gh-actions](deps): Bump codecov/codecov-action from 3 to 4 [#1402](https://github.com/dandi/dandi-cli/pull/1402) ([@dependabot[bot]](https://github.com/dependabot[bot]))

#### Authors: 2

- [@dependabot[bot]](https://github.com/dependabot[bot])
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.59.1 (Fri Feb 02 2024)

#### 🏠 Internal

- Failsafe etelemetry import [#1399](https://github.com/dandi/dandi-cli/pull/1399) ([@TheChymera](https://github.com/TheChymera))

#### 📝 Documentation

- Add notes to docs about `get_metadata()` vs. `get_raw_metadata()` [#1398](https://github.com/dandi/dandi-cli/pull/1398) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Ignore irrelevant deprecation warning from pandas [#1391](https://github.com/dandi/dandi-cli/pull/1391) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Blacklist buggy nwbinspector 0.4.32 [#1401](https://github.com/dandi/dandi-cli/pull/1401) ([@yarikoptic](https://github.com/yarikoptic))
- Update zarr_checksum dependency to `~= 0.4.0` [#1393](https://github.com/dandi/dandi-cli/pull/1393) ([@jwodder](https://github.com/jwodder))
- Update zarr_checksum dependency to `~= 0.3.2` [#1392](https://github.com/dandi/dandi-cli/pull/1392) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.59.0 (Tue Jan 09 2024)

#### 🚀 Enhancement

- `dandi download dandi://…/dandiset.yaml` now downloads `dandiset.yaml` [#1384](https://github.com/dandi/dandi-cli/pull/1384) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Double-check file sizes before & after uploading [#1374](https://github.com/dandi/dandi-cli/pull/1374) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Adopt `dandischema.digests.zarr.get_checksum()` to dandi-cli: use zarr_checksum library constructs instead of copies in dandischema [#1371](https://github.com/dandi/dandi-cli/pull/1371) ([@jwodder](https://github.com/jwodder))
- [gh-actions](deps): Bump github/codeql-action from 2 to 3 [#1379](https://github.com/dandi/dandi-cli/pull/1379) ([@dependabot[bot]](https://github.com/dependabot[bot]))

#### 📝 Documentation

- Minor codespell fix in a CHANGELOG entry [#1389](https://github.com/dandi/dandi-cli/pull/1389) ([@yarikoptic](https://github.com/yarikoptic))
- Minor update to `organize` docstring [#1382](https://github.com/dandi/dandi-cli/pull/1382) ([@kabilar](https://github.com/kabilar))
- Minor docs update for `dandi validate` [#1377](https://github.com/dandi/dandi-cli/pull/1377) ([@kabilar](https://github.com/kabilar))

#### 🧪 Tests

- Fix service script tests for change in autogenerated date [#1385](https://github.com/dandi/dandi-cli/pull/1385) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- [@dependabot[bot]](https://github.com/dependabot[bot])
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.58.2 (Wed Dec 13 2023)

#### 🐛 Bug Fix

- Properly open filehandles for `RemoteReadableAsset`s [#1376](https://github.com/dandi/dandi-cli/pull/1376) ([@jwodder](https://github.com/jwodder))
- Repeatedly double-check return values of zero when spying on `super_len()` [#1370](https://github.com/dandi/dandi-cli/pull/1370) ([@jwodder](https://github.com/jwodder))
- Set 30-second connect & read timeout when downloading files [#1369](https://github.com/dandi/dandi-cli/pull/1369) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- [gh-actions](deps): Bump actions/setup-python from 4 to 5 [#1372](https://github.com/dandi/dandi-cli/pull/1372) ([@dependabot[bot]](https://github.com/dependabot[bot]))
- Remove redundant `ensure_datetime()` call [#1367](https://github.com/dandi/dandi-cli/pull/1367) ([@jwodder](https://github.com/jwodder))
- Move imports in functions to top level or annotate why they can't be moved [#1368](https://github.com/dandi/dandi-cli/pull/1368) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- [@dependabot[bot]](https://github.com/dependabot[bot])
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.58.1 (Mon Nov 27 2023)

#### 🐛 Bug Fix

- Add Python 3.12 to supported versions and test against on GitHub Actions; upgrade versioneer [#1330](https://github.com/dandi/dandi-cli/pull/1330) ([@yarikoptic](https://github.com/yarikoptic))
- Minor fix for an occasional typo in a comment introduced recently [#1357](https://github.com/dandi/dandi-cli/pull/1357) ([@yarikoptic](https://github.com/yarikoptic))
- Replace magic string arguments with enums [#1357](https://github.com/dandi/dandi-cli/pull/1357) ([@jwodder](https://github.com/jwodder))
- Merge duplicate entries in species_map [#1358](https://github.com/dandi/dandi-cli/pull/1358) ([@garrettmflynn](https://github.com/garrettmflynn))
- Sanitize spaces and ,s in organized filenames [#1351](https://github.com/dandi/dandi-cli/pull/1351) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Remove unused configuration settings [#1346](https://github.com/dandi/dandi-cli/pull/1346) ([@jwodder](https://github.com/jwodder))
- find_files: Simplify check for VCS and DataLad paths [#1355](https://github.com/dandi/dandi-cli/pull/1355) ([@jwodder](https://github.com/jwodder))
- Convert dandiarchive URL classes from pydantic models to dataclasses [#1356](https://github.com/dandi/dandi-cli/pull/1356) ([@jwodder](https://github.com/jwodder))
- Replace `_pytest` imports with modern `pytest` imports [#1347](https://github.com/dandi/dandi-cli/pull/1347) ([@jwodder](https://github.com/jwodder))
- Remove `_order_` attribute from `Severity` enum [#1348](https://github.com/dandi/dandi-cli/pull/1348) ([@jwodder](https://github.com/jwodder))
- Use dataclass instead of `auto_repr` [#1349](https://github.com/dandi/dandi-cli/pull/1349) ([@jwodder](https://github.com/jwodder))
- Run `pyupgrade --py38-plus` on source [#1350](https://github.com/dandi/dandi-cli/pull/1350) ([@jwodder](https://github.com/jwodder))
- Modernize type annotations and improve mypy config [#1343](https://github.com/dandi/dandi-cli/pull/1343) ([@jwodder](https://github.com/jwodder))
- Move words ignored by codespell from `.codespellignore` to `setup.cfg` [#1344](https://github.com/dandi/dandi-cli/pull/1344) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Install also hdmf from git in the dev-deps CI run [#1320](https://github.com/dandi/dandi-cli/pull/1320) ([@yarikoptic](https://github.com/yarikoptic))
- Fix typing error [#1359](https://github.com/dandi/dandi-cli/pull/1359) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Update for `zarr_checksum` 0.2.12 [#1365](https://github.com/dandi/dandi-cli/pull/1365) ([@jwodder](https://github.com/jwodder))
- Replace appdirs with platformdirs [#1345](https://github.com/dandi/dandi-cli/pull/1345) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- Garrett Michael Flynn ([@garrettmflynn](https://github.com/garrettmflynn))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.58.0 (Wed Nov 08 2023)

#### 🚀 Enhancement

- Expose number of jobs to organize [#1341](https://github.com/dandi/dandi-cli/pull/1341) ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))

#### 🧪 Tests

- Don't use buggy version of `responses` [#1342](https://github.com/dandi/dandi-cli/pull/1342) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Cody Baker ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.57.0 (Wed Nov 01 2023)

#### 🚀 Enhancement

- `?location` parameter in URLs can only point to a folder [#1305](https://github.com/dandi/dandi-cli/pull/1305) ([@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Add missing term in ETA calculation [#1340](https://github.com/dandi/dandi-cli/pull/1340) ([@sneakers-the-rat](https://github.com/sneakers-the-rat))

#### 🏠 Internal

- typing: Account for the fact that requests.HTTPError .response might be None now [#1336](https://github.com/dandi/dandi-cli/pull/1336) ([@yarikoptic](https://github.com/yarikoptic))
- [gh-actions](deps): Bump actions/checkout from 3 to 4 [#1326](https://github.com/dandi/dandi-cli/pull/1326) ([@dependabot[bot]](https://github.com/dependabot[bot]))
- codespell: tuneup of config and some new typos detected fixes [#1334](https://github.com/dandi/dandi-cli/pull/1334) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Minor documentation tune up [#1338](https://github.com/dandi/dandi-cli/pull/1338) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Re-record VCR tapes using newer versions of libraries [#1337](https://github.com/dandi/dandi-cli/pull/1337) ([@yarikoptic](https://github.com/yarikoptic))
- Ignore unclosed connection resource warning from VCR [#1333](https://github.com/dandi/dandi-cli/pull/1333) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 4

- [@dependabot[bot]](https://github.com/dependabot[bot])
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Jonny Saunders ([@sneakers-the-rat](https://github.com/sneakers-the-rat))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.56.2 (Fri Sep 29 2023)

#### 🐛 Bug Fix

- Fix uploading Zarr within a BIDS dataset; typing-check guided fix for handling requests exception [#1331](https://github.com/dandi/dandi-cli/pull/1331) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.56.1 (Mon Sep 11 2023)

#### 🐛 Bug Fix

- Add Macaca nemestrina to species [#1327](https://github.com/dandi/dandi-cli/pull/1327) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.56.0 (Fri Aug 11 2023)

#### 🚀 Enhancement

- ENH: Add support for _desc- entity to label different processings of a file [#1315](https://github.com/dandi/dandi-cli/pull/1315) ([@yarikoptic](https://github.com/yarikoptic))
- Accept URLs as Dandi instance specifiers [#1298](https://github.com/dandi/dandi-cli/pull/1298) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Check if URL matches the API URL so we do not hardcode wrong "False" for is_api [#1318](https://github.com/dandi/dandi-cli/pull/1318) ([@yarikoptic](https://github.com/yarikoptic))
- Fix wait_until_valid to properly wait for a publishable version [#1311](https://github.com/dandi/dandi-cli/pull/1311) ([@danlamanna](https://github.com/danlamanna))
- Update `asset_validation_errors` structure [#1303](https://github.com/dandi/dandi-cli/pull/1303) ([@jwodder](https://github.com/jwodder))
- Don't treat certain broken symlinks as absent files [#1292](https://github.com/dandi/dandi-cli/pull/1292) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Removed deprecated boilerplate for copying tree to an existing directory [#1294](https://github.com/dandi/dandi-cli/pull/1294) ([@TheChymera](https://github.com/TheChymera) [@jwodder](https://github.com/jwodder))
- Remove Python 3.7-specific code [#1296](https://github.com/dandi/dandi-cli/pull/1296) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- TST: fix and not announce xfailed test which checks /server-info - version is provided now [#1319](https://github.com/dandi/dandi-cli/pull/1319) ([@yarikoptic](https://github.com/yarikoptic))
- Fix typing errors due to keyring and cv externals changes. [#1316](https://github.com/dandi/dandi-cli/pull/1316) ([@jwodder](https://github.com/jwodder))
- Fix test for newer hdf5 [#1301](https://github.com/dandi/dandi-cli/pull/1301) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Drop dependency on importlib-metadata backport for Python 3.7 [#1299](https://github.com/dandi/dandi-cli/pull/1299) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Dan LaManna ([@danlamanna](https://github.com/danlamanna))
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.55.1 (Fri May 19 2023)

#### 🔩 Dependency Updates

- Bidsschematools 0.7.0 API usage update [#1243](https://github.com/dandi/dandi-cli/pull/1243) ([@TheChymera](https://github.com/TheChymera) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.55.0 (Thu May 18 2023)

#### 🚀 Enhancement

- Support uploading a subset of files from a BIDS dataset [#1286](https://github.com/dandi/dandi-cli/pull/1286) ([@jwodder](https://github.com/jwodder))
- Add `dandi service-scripts update-dandiset-from-doi` command [#1283](https://github.com/dandi/dandi-cli/pull/1283) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Use `inspect_nwbfile()` instead of `inspect_nwb()`; address bug in recent `ruamel.yaml` versions [#1285](https://github.com/dandi/dandi-cli/pull/1285) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Cancel any still-running tests when pushing to a branch or PR [#1287](https://github.com/dandi/dandi-cli/pull/1287) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Retry test that intermittently fails on NFS [#1290](https://github.com/dandi/dandi-cli/pull/1290) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.54.0 (Fri Apr 21 2023)

#### 🚀 Enhancement

- Support asset path globs in `dandi download` [#1278](https://github.com/dandi/dandi-cli/pull/1278) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Explicitly open h5py.File as read-only where we read it [#1282](https://github.com/dandi/dandi-cli/pull/1282) ([@yarikoptic](https://github.com/yarikoptic))
- C elegans [#1276](https://github.com/dandi/dandi-cli/pull/1276) ([@bendichter](https://github.com/bendichter) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Ben Dichter ([@bendichter](https://github.com/bendichter))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.53.0 (Mon Apr 17 2023)

#### 🚀 Enhancement

- Give `DandiAPIClient.authenticate()` a `save_to_keyring` parameter [#1268](https://github.com/dandi/dandi-cli/pull/1268) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Suppress log messages when downloading with pyout, even if no logger has been configured [#1279](https://github.com/dandi/dandi-cli/pull/1279) ([@jwodder](https://github.com/jwodder))
- Accept Other sex as o abbreviation [#1275](https://github.com/dandi/dandi-cli/pull/1275) ([@bendichter](https://github.com/bendichter))
- validate: resolved issues with relative path input [#1260](https://github.com/dandi/dandi-cli/pull/1260) ([@TheChymera](https://github.com/TheChymera))
- Log results of `requests.utils.super_len()` when `DANDI_DEVEL_INSTRUMENT_REQUESTS_SUPERLEN` is set [#1267](https://github.com/dandi/dandi-cli/pull/1267) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Add configuration for log buckets in testing [#1277](https://github.com/dandi/dandi-cli/pull/1277) ([@danlamanna](https://github.com/danlamanna))
- Make test NFS-safe [#1274](https://github.com/dandi/dandi-cli/pull/1274) ([@jwodder](https://github.com/jwodder))
- Fix `test_validate_relative_path` [#1272](https://github.com/dandi/dandi-cli/pull/1272) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Ben Dichter ([@bendichter](https://github.com/bendichter))
- Dan LaManna ([@danlamanna](https://github.com/danlamanna))
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.52.0 (Wed Apr 05 2023)

#### 🚀 Enhancement

- enh: add cellline parsing [#1254](https://github.com/dandi/dandi-cli/pull/1254) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))
- [ENH] Add severity restriction option to `dandi-validate` [#1248](https://github.com/dandi/dandi-cli/pull/1248) ([@TheChymera](https://github.com/TheChymera))

#### 🐛 Bug Fix

- Log more information about retried HTTP requests [#1264](https://github.com/dandi/dandi-cli/pull/1264) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Add an example for streaming using as_readable + reference to PyNWB examples [#1250](https://github.com/dandi/dandi-cli/pull/1250) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Add CI run testing against NFS [#1262](https://github.com/dandi/dandi-cli/pull/1262) ([@jwodder](https://github.com/jwodder))
- Creating test for file-wise NWB error output listing [#1244](https://github.com/dandi/dandi-cli/pull/1244) ([@TheChymera](https://github.com/TheChymera))

#### Authors: 4

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.51.0 (Fri Mar 10 2023)

#### 🚀 Enhancement

- `validate`: Yield error if path is not inside a Dandiset [#1237](https://github.com/dandi/dandi-cli/pull/1237) ([@jwodder](https://github.com/jwodder))
- Add service script for re-extracting remote NWB metadata [#1236](https://github.com/dandi/dandi-cli/pull/1236) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Corrected docstring [#1245](https://github.com/dandi/dandi-cli/pull/1245) ([@TheChymera](https://github.com/TheChymera))

#### 🧪 Tests

- Revert "Restrict mypy to pre-v1.1.1" [#1247](https://github.com/dandi/dandi-cli/pull/1247) ([@jwodder](https://github.com/jwodder))
- Restrict mypy to pre-v1.1.1 [#1246](https://github.com/dandi/dandi-cli/pull/1246) ([@jwodder](https://github.com/jwodder))
- Skip reextract-metadata test if fsspec is not installed [#1240](https://github.com/dandi/dandi-cli/pull/1240) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Update for dandischema 0.8.0 [#1241](https://github.com/dandi/dandi-cli/pull/1241) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.50.1 (Fri Mar 03 2023)

#### 🧪 Tests

- skip test_nwb2asset_remote_asset if no fsspec installed [#1239](https://github.com/dandi/dandi-cli/pull/1239) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.50.0 (Wed Mar 01 2023)

#### 🚀 Enhancement

- Add `--ignore ID_REGEX` option to `dandi validate` [#1234](https://github.com/dandi/dandi-cli/pull/1234) ([@jwodder](https://github.com/jwodder))
- download: support for downloading multiple URLs at once; dandiset path is now included in the report [#1231](https://github.com/dandi/dandi-cli/pull/1231) ([@jwodder](https://github.com/jwodder))
- Merging `bids_validate` into `validate`, stop validating nested BIDS. [#1203](https://github.com/dandi/dandi-cli/pull/1203) ([@TheChymera](https://github.com/TheChymera) [@jwodder](https://github.com/jwodder))
- Support re-extracting metadata from remote assets [#1214](https://github.com/dandi/dandi-cli/pull/1214) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Inform user with a warning in case of jobs > 1 but non pyout format [#1222](https://github.com/dandi/dandi-cli/pull/1222) ([@yarikoptic](https://github.com/yarikoptic))
- BF: add missing f- for a string [#1228](https://github.com/dandi/dandi-cli/pull/1228) ([@yarikoptic](https://github.com/yarikoptic))
- Don't even test for `cp --reflink` support on Windows [#1221](https://github.com/dandi/dandi-cli/pull/1221) ([@jwodder](https://github.com/jwodder))
- Filter out pyout logs from logfile by default [#1220](https://github.com/dandi/dandi-cli/pull/1220) ([@jwodder](https://github.com/jwodder))
- Metadata: add extraction of strain from nwb files [#1216](https://github.com/dandi/dandi-cli/pull/1216) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Use pathlib more in tests [#1233](https://github.com/dandi/dandi-cli/pull/1233) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Added distribution badge (sadly only one ATM) [#1224](https://github.com/dandi/dandi-cli/pull/1224) ([@TheChymera](https://github.com/TheChymera))
- List in documentation the "high level" interfaces corresponding to CLI [#1200](https://github.com/dandi/dandi-cli/pull/1200) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Update `parse_purlobourl()` test for change to rat metadata [#1227](https://github.com/dandi/dandi-cli/pull/1227) ([@jwodder](https://github.com/jwodder))
- Revert "Temporarily disable all tests which talk to obolibrary" - ontobee said to be back [#1226](https://github.com/dandi/dandi-cli/pull/1226) ([@yarikoptic](https://github.com/yarikoptic))
- Fix tests: avoid obolibrary (for now) and pynwb 2.3.0 (forever) [#1225](https://github.com/dandi/dandi-cli/pull/1225) ([@yarikoptic](https://github.com/yarikoptic))
- Test against Python 3.11 [#1143](https://github.com/dandi/dandi-cli/pull/1143) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.49.1 (Wed Feb 22 2023)

#### 🐛 Bug Fix

- Update for fix to Zarr upload procedure [#1215](https://github.com/dandi/dandi-cli/pull/1215) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Restore testing against Windows with Python 3.10 [#1213](https://github.com/dandi/dandi-cli/pull/1213) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.49.0 (Fri Feb 10 2023)

#### 🚀 Enhancement

- Update for new Zarr upload procedure; remove no longer needed `service-scripts` [#1202](https://github.com/dandi/dandi-cli/pull/1202) ([@jwodder](https://github.com/jwodder))
- BF+RF validation [#1209](https://github.com/dandi/dandi-cli/pull/1209) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Make `RemoteDandiset.get_version()` return a `VersionInfo` instance with validation error fields [#1210](https://github.com/dandi/dandi-cli/pull/1210) ([@jwodder](https://github.com/jwodder))
- Improve messages displayed when an upload fails [#1204](https://github.com/dandi/dandi-cli/pull/1204) ([@jwodder](https://github.com/jwodder))
- RF/BF: make find_parent_directory_containing operate on absolute path [#1188](https://github.com/dandi/dandi-cli/pull/1188) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Pass $USER to tox envs [#1201](https://github.com/dandi/dandi-cli/pull/1201) ([@jwodder](https://github.com/jwodder))
- boost isort in precommit to 5.12.0 to overcome issue with poetry [#1199](https://github.com/dandi/dandi-cli/pull/1199) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Move doc/design under docs/ where the rest of docs reside [#1198](https://github.com/dandi/dandi-cli/pull/1198) ([@yarikoptic](https://github.com/yarikoptic))
- Further improve README.md: point to specific sections of handbook, remove lengthy `dandi ls --help` example [#1193](https://github.com/dandi/dandi-cli/pull/1193) ([@melster1010](https://github.com/melster1010))

#### 🧪 Tests

- Fix type errors; unbound mypy [#1207](https://github.com/dandi/dandi-cli/pull/1207) ([@jwodder](https://github.com/jwodder))
- We no longer need to catch warning as hdmf has fixed the bug [#1194](https://github.com/dandi/dandi-cli/pull/1194) ([@TheChymera](https://github.com/TheChymera))
- Joint BIDS-NWB metadata extraction. [#1183](https://github.com/dandi/dandi-cli/pull/1183) ([@TheChymera](https://github.com/TheChymera))
- Fix for newer HDMF [#1191](https://github.com/dandi/dandi-cli/pull/1191) ([@TheChymera](https://github.com/TheChymera))

#### 🔩 Dependency Updates

- Blacklisting the most recent hdmf version 3.5.0 forbidding its use and breaking CI/testing. [#1190](https://github.com/dandi/dandi-cli/pull/1190) ([@TheChymera](https://github.com/TheChymera))

#### Authors: 4

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Mary Elise Dedicke ([@melster1010](https://github.com/melster1010))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.48.1 (Tue Jan 17 2023)

#### 🐛 Bug Fix

- Fail upload only for validation ERRORs and not necessarily WARNINGs or HINTs + log all errors [#1186](https://github.com/dandi/dandi-cli/pull/1186) ([@yarikoptic](https://github.com/yarikoptic))
- Don't warn on unexpected formats for "next" page URLs [#1184](https://github.com/dandi/dandi-cli/pull/1184) ([@jwodder](https://github.com/jwodder))
- Upload test to check for metadata [#1180](https://github.com/dandi/dandi-cli/pull/1180) ([@TheChymera](https://github.com/TheChymera))

#### Authors: 3

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.48.0 (Mon Dec 19 2022)

#### 🚀 Enhancement

- Update client for change in Zarr entries API [#1175](https://github.com/dandi/dandi-cli/pull/1175) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.47.0 (Mon Dec 19 2022)

#### 🚀 Enhancement

- Add validation of filepaths for non-BIDS NWB assets [#1173](https://github.com/dandi/dandi-cli/pull/1173) ([@jwodder](https://github.com/jwodder))
- Exclude special dotfiles from Zarrs [#1147](https://github.com/dandi/dandi-cli/pull/1147) ([@jwodder](https://github.com/jwodder))
- Structured validation results [#1104](https://github.com/dandi/dandi-cli/pull/1104) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic) [@TheChymera](https://github.com/TheChymera))

#### 🐛 Bug Fix

- Allow user to specify mandatory (if not empty) fields in organize [#1171](https://github.com/dandi/dandi-cli/pull/1171) ([@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))
- BF: convert str errors from checking nwb version into proper ValidationResult [#1174](https://github.com/dandi/dandi-cli/pull/1174) ([@yarikoptic](https://github.com/yarikoptic))
- Tests for `ls` reinstated, underlying function fixed, support for ZARR-BIDS files added. [#1164](https://github.com/dandi/dandi-cli/pull/1164) ([@TheChymera](https://github.com/TheChymera) [@jwodder](https://github.com/jwodder))
- Add CodeQL workflow for GitHub code scanning and fix few bugs it detected [#1165](https://github.com/dandi/dandi-cli/pull/1165) ([@lgtm-migrator](https://github.com/lgtm-migrator) [@jwodder](https://github.com/jwodder) [@lgtm-com[bot]](https://github.com/lgtm-com[bot]))
- Corrected reporting function logic to complete group message variable [#1166](https://github.com/dandi/dandi-cli/pull/1166) ([@TheChymera](https://github.com/TheChymera))
- Renamed failing test, added prospective use case for NWBI warning. [#1162](https://github.com/dandi/dandi-cli/pull/1162) ([@TheChymera](https://github.com/TheChymera))
- Use cached namespace validation [#1149](https://github.com/dandi/dandi-cli/pull/1149) ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))

#### 🏠 Internal

- Make `list_paths()` include dotfiles [#1142](https://github.com/dandi/dandi-cli/pull/1142) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- dandi-cli readme edit [#1170](https://github.com/dandi/dandi-cli/pull/1170) ([@melster1010](https://github.com/melster1010))
- Remove Parameters description from docstring used by click [#1150](https://github.com/dandi/dandi-cli/pull/1150) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- No longer mark `test_rename_type_mismatch` as xfailing [#1161](https://github.com/dandi/dandi-cli/pull/1161) ([@jwodder](https://github.com/jwodder))
- Fix typing error under mypy 0.990 [#1156](https://github.com/dandi/dandi-cli/pull/1156) ([@jwodder](https://github.com/jwodder))
- Update `test_validate_nwb_path_grouping` test [#1157](https://github.com/dandi/dandi-cli/pull/1157) ([@jwodder](https://github.com/jwodder))
- Fixed logic and commented a temporarily broken BIDS (lacking README) dataset [#1148](https://github.com/dandi/dandi-cli/pull/1148) ([@TheChymera](https://github.com/TheChymera))
- Installing hdf5 for Python 3.10 is no longer needed [#1145](https://github.com/dandi/dandi-cli/pull/1145) ([@jwodder](https://github.com/jwodder))
- Fix a typing issue involving the outdated `tmpdir_factory` [#1144](https://github.com/dandi/dandi-cli/pull/1144) ([@jwodder](https://github.com/jwodder))

#### Authors: 7

- [@lgtm-com[bot]](https://github.com/lgtm-com[bot])
- Cody Baker ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- LGTM Migrator ([@lgtm-migrator](https://github.com/lgtm-migrator))
- Mary Elise Dedicke ([@melster1010](https://github.com/melster1010))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.46.6 (Fri Oct 21 2022)

#### 🐛 Bug Fix

- Don't try to cancel failed Zarr uploads twice [#1139](https://github.com/dandi/dandi-cli/pull/1139) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- adding testing instructions [#1123](https://github.com/dandi/dandi-cli/pull/1123) ([@djarecka](https://github.com/djarecka))

#### 🧪 Tests

- Add `DANDI_TESTS_PULL_DOCKER_COMPOSE` envvar [#1141](https://github.com/dandi/dandi-cli/pull/1141) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.46.5 (Fri Oct 14 2022)

#### 🐛 Bug Fix

- ENH: lgr.debug that we are using DANDI_API_KEY provided key [#1133](https://github.com/dandi/dandi-cli/pull/1133) ([@yarikoptic](https://github.com/yarikoptic))
- add zebrafish to species list [#1129](https://github.com/dandi/dandi-cli/pull/1129) ([@satra](https://github.com/satra))
- Make `dandi ls` properly detect embargoed Dandisets [#1132](https://github.com/dandi/dandi-cli/pull/1132) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Make internal Zarr-checksumming tree types support empty Zarrs [#1138](https://github.com/dandi/dandi-cli/pull/1138) ([@jwodder](https://github.com/jwodder))
- Simplify implementations of `get_asset()` methods [#1136](https://github.com/dandi/dandi-cli/pull/1136) ([@jwodder](https://github.com/jwodder))
- Update GitHub Actions action versions [#1135](https://github.com/dandi/dandi-cli/pull/1135) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.46.4 (Thu Oct 06 2022)

#### 🏠 Internal

- Update client-side publication workflow [#1125](https://github.com/dandi/dandi-cli/pull/1125) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- increase number of trials in docker_compose_setup to 25 [#1122](https://github.com/dandi/dandi-cli/pull/1122) ([@djarecka](https://github.com/djarecka))
- Pull latest Docker images before spinning up Compose [#1121](https://github.com/dandi/dandi-cli/pull/1121) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.46.3 (Mon Sep 19 2022)

#### 🐛 Bug Fix

- Detect link type for `organize` by linking from first src dir to dest dir [#1115](https://github.com/dandi/dandi-cli/pull/1115) ([@jwodder](https://github.com/jwodder))
- Check for usage of latest NWB Inspector release [#1108](https://github.com/dandi/dandi-cli/pull/1108) ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))

#### 🧪 Tests

- Test against dev version of keyring package [#1116](https://github.com/dandi/dandi-cli/pull/1116) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Cody Baker ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.46.2 (Thu Sep 01 2022)

#### 🐛 Bug Fix

- Use upstream bidsschematools for BIDS validation [#1095](https://github.com/dandi/dandi-cli/pull/1095) ([@TheChymera](https://github.com/TheChymera))
- get_content_url(): If a HEAD fails, return the failing URL [#1107](https://github.com/dandi/dandi-cli/pull/1107) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- BF(workaround): blacklist 23.9.0 of keyring since introduced regression [#1112](https://github.com/dandi/dandi-cli/pull/1112) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.46.1 (Thu Aug 18 2022)

#### 🐛 Bug Fix

- Add support for age range [#1101](https://github.com/dandi/dandi-cli/pull/1101) ([@djarecka](https://github.com/djarecka))

#### 📝 Documentation

- DOC: minor - boost copyright years in the docs [#1106](https://github.com/dandi/dandi-cli/pull/1106) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Update test.yml to use ubuntu-latest [#1103](https://github.com/dandi/dandi-cli/pull/1103) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.46.0 (Thu Aug 18 2022)

#### 🚀 Enhancement

- Add classes for BIDS assets [#1076](https://github.com/dandi/dandi-cli/pull/1076) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- ENH: list localhost:8085 as the web UI for dandi-api-local-docker-tests [#1003](https://github.com/dandi/dandi-cli/pull/1003) ([@yarikoptic](https://github.com/yarikoptic))
- BF: guard download_generator to not propagate errors [#1008](https://github.com/dandi/dandi-cli/pull/1008) ([@yarikoptic](https://github.com/yarikoptic))
- User notification if datasets are invalid. [#1080](https://github.com/dandi/dandi-cli/pull/1080) ([@TheChymera](https://github.com/TheChymera))
- Updating BIDS validator and schema to contemporary upstream equivalent [#1050](https://github.com/dandi/dandi-cli/pull/1050) ([@TheChymera](https://github.com/TheChymera))
- Support DANDI:<ID>/draft and stop using identifiers.org for any of the DANDI: URIs [#1066](https://github.com/dandi/dandi-cli/pull/1066) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏎 Performance

- Do not traverse .ome.zarr and .ngff folders while looking for BIDS datasets [#1071](https://github.com/dandi/dandi-cli/pull/1071) ([@yarikoptic](https://github.com/yarikoptic))

#### ⚠️ Pushed to `master`

- Update README.md ([@bendichter](https://github.com/bendichter))

#### 🏠 Internal

- Factor out common fields in nwb2asset() and get_default_metadata() [#1088](https://github.com/dandi/dandi-cli/pull/1088) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Add examples to `dandi move` docs [#1098](https://github.com/dandi/dandi-cli/pull/1098) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Tell codespell to ignore "bu" strings in tests [#1102](https://github.com/dandi/dandi-cli/pull/1102) ([@jwodder](https://github.com/jwodder))
- Update video NWB fixtures for next pynwb version [#1100](https://github.com/dandi/dandi-cli/pull/1100) ([@jwodder](https://github.com/jwodder))
- Remove redirector from Docker Compose setup [#1087](https://github.com/dandi/dandi-cli/pull/1087) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Ben Dichter ([@bendichter](https://github.com/bendichter))
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.45.1 (Fri Jul 15 2022)

#### 🐛 Bug Fix

- dandi move: Fix resolution of nonexistent dests when in a subdirectory [#1063](https://github.com/dandi/dandi-cli/pull/1063) ([@jwodder](https://github.com/jwodder))
- dandi move: Include all mismatches in error messages [#1064](https://github.com/dandi/dandi-cli/pull/1064) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Mention in help text that 'draft' is not supported in DANDI:<dandiset>/<version> [#1062](https://github.com/dandi/dandi-cli/pull/1062) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.45.0 (Wed Jul 13 2022)

#### 🚀 Enhancement

- Built-in BIDS support for `dandi upload` [#1011](https://github.com/dandi/dandi-cli/pull/1011) ([@TheChymera](https://github.com/TheChymera))

#### 🐛 Bug Fix

- DOC: describe the purpose for --instance in download [#1053](https://github.com/dandi/dandi-cli/pull/1053) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Replace numpy.asscalar() with numpy.ndarray.item() [#1056](https://github.com/dandi/dandi-cli/pull/1056) ([@jwodder](https://github.com/jwodder))
- Clone entire repo in "Lint" action [#1052](https://github.com/dandi/dandi-cli/pull/1052) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.44.1 (Fri Jul 08 2022)

#### 🐛 Bug Fix

- Retry Zarr entry uploads that fail with "header ... implies functionality ... not implemented" [#1048](https://github.com/dandi/dandi-cli/pull/1048) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.44.0 (Fri Jul 08 2022)

#### 🚀 Enhancement

- Add `get_assets_by_glob()` [#981](https://github.com/dandi/dandi-cli/pull/981) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Don't ingest a Zarr if nothing changed while uploading [#1047](https://github.com/dandi/dandi-cli/pull/1047) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.43.0 (Tue Jul 05 2022)

#### 🚀 Enhancement

- Better cancellation of Zarr uploads [#1041](https://github.com/dandi/dandi-cli/pull/1041) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.42.0 (Fri Jul 01 2022)

#### 🚀 Enhancement

- Reuse "loose" Zarrs that conflict with uploaded path [#1035](https://github.com/dandi/dandi-cli/pull/1035) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Include leading text of response bodies in HTTP error messages [#1023](https://github.com/dandi/dandi-cli/pull/1023) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Properly include "data packages" in project [#1029](https://github.com/dandi/dandi-cli/pull/1029) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Make `test_move_command_too_few_paths` support `DANDI_DEVEL=1` [#1040](https://github.com/dandi/dandi-cli/pull/1040) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.41.0 (Mon Jun 27 2022)

#### 🚀 Enhancement

- Add `dandi move` command [#1024](https://github.com/dandi/dandi-cli/pull/1024) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.40.1 (Fri Jun 03 2022)

#### 🐛 Bug Fix

- Fix calculation of download paths for asset path prefix URLs [#1026](https://github.com/dandi/dandi-cli/pull/1026) ([@jwodder](https://github.com/jwodder))
- organize - sanitize ; as well within the entity value [#1009](https://github.com/dandi/dandi-cli/pull/1009) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.40.0 (Tue May 31 2022)

#### 🚀 Enhancement

- BIDS metadata read-in pilot. [#962](https://github.com/dandi/dandi-cli/pull/962) ([@TheChymera](https://github.com/TheChymera) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Corrected regex label string [#1015](https://github.com/dandi/dandi-cli/pull/1015) ([@TheChymera](https://github.com/TheChymera))
- Fix error message formatting [#1013](https://github.com/dandi/dandi-cli/pull/1013) ([@JuliaSprenger](https://github.com/JuliaSprenger))
- Removing trace from previous commit [#1010](https://github.com/dandi/dandi-cli/pull/1010) ([@TheChymera](https://github.com/TheChymera))

#### 🏎 Performance

- Fetch paginated results concurrently [#1021](https://github.com/dandi/dandi-cli/pull/1021) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Julia Sprenger ([@JuliaSprenger](https://github.com/JuliaSprenger))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.39.6 (Mon May 09 2022)

#### 🐛 Bug Fix

- Logging validation warnings and errors [#992](https://github.com/dandi/dandi-cli/pull/992) ([@TheChymera](https://github.com/TheChymera))
- ENH: delete - allow to specify --force in CLI [#1001](https://github.com/dandi/dandi-cli/pull/1001) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.39.5 (Thu May 05 2022)

#### 🐛 Bug Fix

- Setting version to min version if not available [#994](https://github.com/dandi/dandi-cli/pull/994) ([@TheChymera](https://github.com/TheChymera))
- Whitespace for string returns [#985](https://github.com/dandi/dandi-cli/pull/985) ([@TheChymera](https://github.com/TheChymera))

#### 🏠 Internal

- Upgrade dandischema to 0.7.x series [#987](https://github.com/dandi/dandi-cli/pull/987) ([@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))
- Prepend to sys.path to fix versioneer in PEP517 mode [#998](https://github.com/dandi/dandi-cli/pull/998) ([@mgorny](https://github.com/mgorny))
- minor spelling typo fix [#998](https://github.com/dandi/dandi-cli/pull/998) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 4

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Michał Górny ([@mgorny](https://github.com/mgorny))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.39.4 (Tue Apr 26 2022)

#### 🏎 Performance

- Remove size comparison check when uploading Zarr entries [#986](https://github.com/dandi/dandi-cli/pull/986) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.39.3 (Mon Apr 25 2022)

#### 🐛 Bug Fix

- Increase Zarr depth limit to 7 directories [#984](https://github.com/dandi/dandi-cli/pull/984) ([@jwodder](https://github.com/jwodder))
- keeping logs cleaner in dedicated directory [#971](https://github.com/dandi/dandi-cli/pull/971) ([@TheChymera](https://github.com/TheChymera))
- performance: do not duplicate schema loading [#982](https://github.com/dandi/dandi-cli/pull/982) ([@TheChymera](https://github.com/TheChymera))
- Strip trailing slash from URLs in `/server-info` [#972](https://github.com/dandi/dandi-cli/pull/972) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Add new API design doc [#447](https://github.com/dandi/dandi-cli/pull/447) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Removed duplicate, and simplified bids validator tests [#965](https://github.com/dandi/dandi-cli/pull/965) ([@TheChymera](https://github.com/TheChymera))
- Mark `test_server_info` as xfailing [#978](https://github.com/dandi/dandi-cli/pull/978) ([@jwodder](https://github.com/jwodder))
- Mark `test_parse_dandi_url_not_found` as xfailing [#973](https://github.com/dandi/dandi-cli/pull/973) ([@jwodder](https://github.com/jwodder))
- Update `test_parse_api_url[DANDI:000027]` [#974](https://github.com/dandi/dandi-cli/pull/974) ([@jwodder](https://github.com/jwodder))
- Update `test_follow_redirect` [#975](https://github.com/dandi/dandi-cli/pull/975) ([@jwodder](https://github.com/jwodder))
- Combine subtests of `test_publish_and_manipulate` [#964](https://github.com/dandi/dandi-cli/pull/964) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.39.2 (Tue Apr 19 2022)

#### 🐛 Bug Fix

- Validator fixes: fallback to our version, skip dotdirs on windows, etc [#955](https://github.com/dandi/dandi-cli/pull/955) ([@TheChymera](https://github.com/TheChymera))
- Better detection of empty directories when download-syncing Zarrs [#961](https://github.com/dandi/dandi-cli/pull/961) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.39.1 (Thu Apr 14 2022)

#### 🐛 Bug Fix

- Fix type in test docker-compose env var [#960](https://github.com/dandi/dandi-cli/pull/960) ([@AlmightyYakob](https://github.com/AlmightyYakob))

#### Authors: 1

- Jacob Nesbitt ([@AlmightyYakob](https://github.com/AlmightyYakob))

---

# 0.39.0 (Thu Apr 14 2022)

#### 🚀 Enhancement

- Add DANDI_JUPYTERHUB_URL to test docker-compose [#959](https://github.com/dandi/dandi-cli/pull/959) ([@AlmightyYakob](https://github.com/AlmightyYakob))
- Integrate NWBInspector with DANDI validation [#941](https://github.com/dandi/dandi-cli/pull/941) ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))

#### 🐛 Bug Fix

- Integration test config [#957](https://github.com/dandi/dandi-cli/pull/957) ([@dchiquito](https://github.com/dchiquito))
- Smaller video files [#947](https://github.com/dandi/dandi-cli/pull/947) ([@TheChymera](https://github.com/TheChymera))

#### ⚠️ Pushed to `master`

- add .mkv as a valid video extension ([@bendichter](https://github.com/bendichter))

#### 🏠 Internal

- DX: enable "released" plugin for auto [#951](https://github.com/dandi/dandi-cli/pull/951) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Fixed test_write_report() log path issue [#954](https://github.com/dandi/dandi-cli/pull/954) ([@TheChymera](https://github.com/TheChymera))
- Specify all queues in test celery worker [#953](https://github.com/dandi/dandi-cli/pull/953) ([@dchiquito](https://github.com/dchiquito))
- Work around a bug in docker-compose [#949](https://github.com/dandi/dandi-cli/pull/949) ([@jwodder](https://github.com/jwodder))

#### Authors: 7

- Ben Dichter ([@bendichter](https://github.com/bendichter))
- Cody Baker ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- Jacob Nesbitt ([@AlmightyYakob](https://github.com/AlmightyYakob))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.38.0 (Mon Apr 04 2022)

#### 🚀 Enhancement

- Adding BIDS support [#896](https://github.com/dandi/dandi-cli/pull/896) ([@yarikoptic](https://github.com/yarikoptic) [@TheChymera](https://github.com/TheChymera))

#### 🏠 Internal

- Black update [#945](https://github.com/dandi/dandi-cli/pull/945) ([@TheChymera](https://github.com/TheChymera))

#### Authors: 2

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.37.0 (Tue Mar 22 2022)

#### 🚀 Enhancement

- Recognize video files as non-generic assets [#922](https://github.com/dandi/dandi-cli/pull/922) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Update for change in Zarr checksum format [#933](https://github.com/dandi/dandi-cli/pull/933) ([@jwodder](https://github.com/jwodder))
- Trigger Zarr ingestion after performing an upload [#938](https://github.com/dandi/dandi-cli/pull/938) ([@jwodder](https://github.com/jwodder))
- check for existence of video path else assume relative path [#931](https://github.com/dandi/dandi-cli/pull/931) ([@Saksham20](https://github.com/Saksham20))
- dandi upload: Make `--jobs` default to `5:5` and document it [#940](https://github.com/dandi/dandi-cli/pull/940) ([@jwodder](https://github.com/jwodder))
- checking for duplicate video files in external_files [#928](https://github.com/dandi/dandi-cli/pull/928) ([@Saksham20](https://github.com/Saksham20))
- skip handling URLs in external files references as we do for local paths [#932](https://github.com/dandi/dandi-cli/pull/932) ([@Saksham20](https://github.com/Saksham20))
- Let `dandi delete` take paths to local Zarrs [#925](https://github.com/dandi/dandi-cli/pull/925) ([@jwodder](https://github.com/jwodder))

#### 🏎 Performance

- Minimize/optimize Zarr digestion when uploading [#923](https://github.com/dandi/dandi-cli/pull/923) ([@jwodder](https://github.com/jwodder))
- Don't repeat API requests when finding subdir files to delete before Zarr upload [#919](https://github.com/dandi/dandi-cli/pull/919) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Correct the docstring for `BasePath.parents` [#936](https://github.com/dandi/dandi-cli/pull/936) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Saksham Sharda ([@Saksham20](https://github.com/Saksham20))

---

# 0.36.0 (Thu Feb 17 2022)

#### 🚀 Enhancement

- Add zarr-checksum method to `dandi digest` [#900](https://github.com/dandi/dandi-cli/pull/900) ([@jwodder](https://github.com/jwodder))
- Move `dandi organize` code to an `organize()` function [#902](https://github.com/dandi/dandi-cli/pull/902) ([@jwodder](https://github.com/jwodder))
- Video files organize [#841](https://github.com/dandi/dandi-cli/pull/841) ([@Saksham20](https://github.com/Saksham20))
- Make use of `/assets/{asset_id}/info/` endpoint [#895](https://github.com/dandi/dandi-cli/pull/895) ([@jwodder](https://github.com/jwodder))
- Support Zarr directories [#853](https://github.com/dandi/dandi-cli/pull/853) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Make `dandi upload` look for dandiset.yaml in parents of common path [#916](https://github.com/dandi/dandi-cli/pull/916) ([@jwodder](https://github.com/jwodder))
- Mint Zarr assets at start of upload and sync Zarr contents [#907](https://github.com/dandi/dandi-cli/pull/907) ([@jwodder](https://github.com/jwodder))
- Use full asset path as name of Zarr object [#912](https://github.com/dandi/dandi-cli/pull/912) ([@jwodder](https://github.com/jwodder))
- Specify Dandiset ID when creating a Zarr [#911](https://github.com/dandi/dandi-cli/pull/911) ([@jwodder](https://github.com/jwodder))
- Cancel a Zarr upload if an error occurs partway through [#893](https://github.com/dandi/dandi-cli/pull/893) ([@jwodder](https://github.com/jwodder))
- Make `get_raw_digest()` actually default to the proper digest type for Zarrs [#894](https://github.com/dandi/dandi-cli/pull/894) ([@jwodder](https://github.com/jwodder))
- Fix neural data type to metadata extractor [#891](https://github.com/dandi/dandi-cli/pull/891) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Add dedicated HTTP404Error exception class [#908](https://github.com/dandi/dandi-cli/pull/908) ([@jwodder](https://github.com/jwodder))
- Make `paths` argument to `upload()` optional [#899](https://github.com/dandi/dandi-cli/pull/899) ([@jwodder](https://github.com/jwodder))
- Add type-annotations to various files [#887](https://github.com/dandi/dandi-cli/pull/887) ([@jwodder](https://github.com/jwodder))
- Delete functions (get_asset_metadata, find_dandi_files) obsoleted by PR #853 [#885](https://github.com/dandi/dandi-cli/pull/885) ([@jwodder](https://github.com/jwodder))
- Use a pydantic model to store a RemoteDandiset's cached data [#876](https://github.com/dandi/dandi-cli/pull/876) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- improve DandiApiClient.__init__ docstring [#909](https://github.com/dandi/dandi-cli/pull/909) ([@bendichter](https://github.com/bendichter))
- Document new `dandi organize` options in Read the Docs site [#901](https://github.com/dandi/dandi-cli/pull/901) ([@jwodder](https://github.com/jwodder))
- Organize & fine-tune dandi.dandiapi Sphinx docs [#888](https://github.com/dandi/dandi-cli/pull/888) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Pin minio image version [#898](https://github.com/dandi/dandi-cli/pull/898) ([@AlmightyYakob](https://github.com/AlmightyYakob))
- Enable type-checking [#877](https://github.com/dandi/dandi-cli/pull/877) ([@jwodder](https://github.com/jwodder))
- Add `new_dandiset` fixture [#874](https://github.com/dandi/dandi-cli/pull/874) ([@jwodder](https://github.com/jwodder))
- Mark a test with missing `skipif_no_network` marker [#886](https://github.com/dandi/dandi-cli/pull/886) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Remove unused tqdm dependency [#910](https://github.com/dandi/dandi-cli/pull/910) ([@jwodder](https://github.com/jwodder))
- Update minimum pydantic version to 1.9.0 [#905](https://github.com/dandi/dandi-cli/pull/905) ([@jwodder](https://github.com/jwodder))

#### Authors: 6

- Ben Dichter ([@bendichter](https://github.com/bendichter))
- Jacob Nesbitt ([@AlmightyYakob](https://github.com/AlmightyYakob))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Saksham Sharda ([@Saksham20](https://github.com/Saksham20))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.35.0 (Mon Jan 24 2022)

#### 🚀 Enhancement

- Make navigate() and navigate_url() auto-authenticate for embargoed Dandisets [#870](https://github.com/dandi/dandi-cli/pull/870) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- species url is case sensitive [#865](https://github.com/dandi/dandi-cli/pull/865) ([@jwodder](https://github.com/jwodder) [@satra](https://github.com/satra))

#### 🏠 Internal

- Update bad versions list in `.et` [#866](https://github.com/dandi/dandi-cli/pull/866) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))

---

# 0.34.1 (Mon Jan 17 2022)

#### 🔩 Dependency Updates

- upgrade dandischema requirement from 0.4.1 to 0.5.1 (~=) [#868](https://github.com/dandi/dandi-cli/pull/868) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.34.0 (Wed Jan 12 2022)

#### 🚀 Enhancement

- Include "dandiset" field in /uploads/initialize/ requests [#863](https://github.com/dandi/dandi-cli/pull/863) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- ENH: update species interpretation from NWB file [#857](https://github.com/dandi/dandi-cli/pull/857) ([@satra](https://github.com/satra))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))

---

# 0.33.0 (Tue Jan 11 2022)

#### 🚀 Enhancement

- Add `embargo_status` to dandiset endpoint [#855](https://github.com/dandi/dandi-cli/pull/855) ([@dchiquito](https://github.com/dchiquito))
- Remove dandi/core/ in favor of copy in dandischema [#849](https://github.com/dandi/dandi-cli/pull/849) ([@jwodder](https://github.com/jwodder))
- Error on NWB files with external links [#843](https://github.com/dandi/dandi-cli/pull/843) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Add DJANGO_DANDI_DANDISETS_EMBARGO_BUCKET_NAME setting to test docker-compose.yml [#854](https://github.com/dandi/dandi-cli/pull/854) ([@dchiquito](https://github.com/dchiquito))

#### 🏠 Internal

- Move a comment [#862](https://github.com/dandi/dandi-cli/pull/862) ([@jwodder](https://github.com/jwodder))
- Add a wrapper function for the calls to `find_files()` in tests [#860](https://github.com/dandi/dandi-cli/pull/860) ([@jwodder](https://github.com/jwodder))
- Assorted code cleanups [#859](https://github.com/dandi/dandi-cli/pull/859) ([@jwodder](https://github.com/jwodder))
- Remove generatorify.py [#850](https://github.com/dandi/dandi-cli/pull/850) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Improve CLI documentation [#851](https://github.com/dandi/dandi-cli/pull/851) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Replace the use of pyfakefs with a `tmp_home` fixture [#861](https://github.com/dandi/dandi-cli/pull/861) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.32.2 (Mon Dec 06 2021)

#### 🐛 Bug Fix

- Improve UX of failed redirects while resolving resource identifiers [#830](https://github.com/dandi/dandi-cli/pull/830) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Remove some unused functions [#846](https://github.com/dandi/dandi-cli/pull/846) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Set new environment variables required by API server [#845](https://github.com/dandi/dandi-cli/pull/845) ([@mvandenburgh](https://github.com/mvandenburgh))
- Test against Python 3.10 [#794](https://github.com/dandi/dandi-cli/pull/794) ([@jwodder](https://github.com/jwodder))
- Ignore a deprecation warning from humanize [#844](https://github.com/dandi/dandi-cli/pull/844) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Mike VanDenburgh ([@mvandenburgh](https://github.com/mvandenburgh))

---

# 0.32.1 (Mon Nov 29 2021)

#### 🐛 Bug Fix

- Convert DANDI: resource identifiers to lowercase when prepending "https://identifiers.org/" and tighten regex [#829](https://github.com/dandi/dandi-cli/pull/829) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.32.0 (Fri Nov 19 2021)

#### 🚀 Enhancement

- Support setting `--dandi-instance` via a `DANDI_INSTANCE` envvar [#822](https://github.com/dandi/dandi-cli/pull/822) ([@jwodder](https://github.com/jwodder))
- Give the resource classes `api_url` properties [#816](https://github.com/dandi/dandi-cli/pull/816) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Convert metadata 404's when downloading into an "error" status [#839](https://github.com/dandi/dandi-cli/pull/839) ([@jwodder](https://github.com/jwodder))
- Don't error when redownloading the same dandiset.yaml file [#824](https://github.com/dandi/dandi-cli/pull/824) ([@jwodder](https://github.com/jwodder))
- Make download fail immediately on nonexistent resources [#820](https://github.com/dandi/dandi-cli/pull/820) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Stop using distutils [#812](https://github.com/dandi/dandi-cli/pull/812) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Add Read the Docs badge to README [#832](https://github.com/dandi/dandi-cli/pull/832) ([@jwodder](https://github.com/jwodder))
- Improve `dandi ls --help` and `dandi download --help` output [#827](https://github.com/dandi/dandi-cli/pull/827) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.31.0 (Mon Oct 25 2021)

#### 🚀 Enhancement

- Support requesting sorted assets [#807](https://github.com/dandi/dandi-cli/pull/807) ([@jwodder](https://github.com/jwodder))
- Make logfile always contain all DEBUG or higher log messages [#813](https://github.com/dandi/dandi-cli/pull/813) ([@jwodder](https://github.com/jwodder))
- Publicly expose classmethods for constructing API resource instances [#808](https://github.com/dandi/dandi-cli/pull/808) ([@jwodder](https://github.com/jwodder))
- Make `--dandi-instance` public and add "instances" command [#804](https://github.com/dandi/dandi-cli/pull/804) ([@jwodder](https://github.com/jwodder))
- dandi.dandiapi: Convert 404 responses to NotFoundErrors [#801](https://github.com/dandi/dandi-cli/pull/801) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Fix a minor bug in a handler for a rare condition [#806](https://github.com/dandi/dandi-cli/pull/806) ([@jwodder](https://github.com/jwodder))
- Show valid instance names when given a dandi:// URL with an unknown instance [#815](https://github.com/dandi/dandi-cli/pull/815) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Stop using `setup_requires` [#811](https://github.com/dandi/dandi-cli/pull/811) ([@jwodder](https://github.com/jwodder))
- Update codecov action to v2 [#802](https://github.com/dandi/dandi-cli/pull/802) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Improve dandiarchive.py docs [#803](https://github.com/dandi/dandi-cli/pull/803) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.30.3 (Mon Oct 11 2021)

#### 🏠 Internal

- Add flake8 to pre-commit-config.yaml [#800](https://github.com/dandi/dandi-cli/pull/800) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Document & type-annotate all public values in `dandi.dandiapi` [#799](https://github.com/dandi/dandi-cli/pull/799) ([@jwodder](https://github.com/jwodder))
- Set Sphinx `default_role` to "py:obj" [#795](https://github.com/dandi/dandi-cli/pull/795) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Apply "skipif_no_network" to all relevant tests [#797](https://github.com/dandi/dandi-cli/pull/797) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.30.2 (Mon Oct 11 2021)

#### 🐛 Bug Fix

- Retry more requests; wait longer for Dandiset validity [#798](https://github.com/dandi/dandi-cli/pull/798) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.30.1 (Thu Oct 07 2021)

#### 📝 Documentation

- Change docs to use "furo" theme [#790](https://github.com/dandi/dandi-cli/pull/790) ([@jwodder](https://github.com/jwodder))
- Show more documentation [#789](https://github.com/dandi/dandi-cli/pull/789) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Register all celery queues with dandiarchive env [#787](https://github.com/dandi/dandi-cli/pull/787) ([@dchiquito](https://github.com/dchiquito))

#### Authors: 2

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.30.0 (Wed Oct 06 2021)

#### 🚀 Enhancement

- Log a message if a request succeeds after one or more failures [take 2] [#792](https://github.com/dandi/dandi-cli/pull/792) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Make CI tests dump Docker Compose logs on failure [#793](https://github.com/dandi/dandi-cli/pull/793) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.29.0 (Wed Oct 06 2021)

#### 🚀 Enhancement

- Give `RemoteAsset` a `created` attribute [#781](https://github.com/dandi/dandi-cli/pull/781) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.28.0 (Mon Oct 04 2021)

#### 🚀 Enhancement

- Give `validate` command an `--allow-any-path` option [#783](https://github.com/dandi/dandi-cli/pull/783) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Fix an AttributeError raised when a URL is used as a species [#782](https://github.com/dandi/dandi-cli/pull/782) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Remove Girder envvars from Docker Compose setup [#779](https://github.com/dandi/dandi-cli/pull/779) ([@jwodder](https://github.com/jwodder))
- Specify DJANGO_DANDI_VALIDATION_JOB_INTERVAL [#778](https://github.com/dandi/dandi-cli/pull/778) ([@dchiquito](https://github.com/dchiquito))

#### Authors: 2

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.27.3 (Tue Sep 28 2021)

#### 🐛 Bug Fix

- Fix display of Dandiset validation errors [#777](https://github.com/dandi/dandi-cli/pull/777) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Fix a test [#776](https://github.com/dandi/dandi-cli/pull/776) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Update dandischema version [#775](https://github.com/dandi/dandi-cli/pull/775) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.27.2 (Mon Sep 13 2021)

#### 🧪 Tests

- Update Docker Compose spin-up code for loss of --username option [#768](https://github.com/dandi/dandi-cli/pull/768) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.27.1 (Fri Sep 03 2021)

#### 🐛 Bug Fix

- Stop uploading a file if no metadata can be extracted [#767](https://github.com/dandi/dandi-cli/pull/767) ([@jwodder](https://github.com/jwodder))
- Retry following redirects on 400 (not 404), 502, 503, & 504 up to 5 times [#762](https://github.com/dandi/dandi-cli/pull/762) ([@jwodder](https://github.com/jwodder))
- Add dandischema into fscacher tokens for validate [#760](https://github.com/dandi/dandi-cli/pull/760) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Add module docstring to dandiapi.py [#756](https://github.com/dandi/dandi-cli/pull/756) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Use new published version of 000027 in tests [#763](https://github.com/dandi/dandi-cli/pull/763) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.27.0 (Thu Aug 26 2021)

#### 🚀 Enhancement

- Make `download_url` `RemoteAsset`-only; give `BaseRemoteAsset` `base_download_url` [#759](https://github.com/dandi/dandi-cli/pull/759) ([@jwodder](https://github.com/jwodder))
- Give API resource classes `__str__` methods [#753](https://github.com/dandi/dandi-cli/pull/753) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Map netlify addresses to gui-staging [#758](https://github.com/dandi/dandi-cli/pull/758) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Remove test against rc/2.0.0 branch of pynwb [#754](https://github.com/dandi/dandi-cli/pull/754) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.26.1 (Mon Aug 09 2021)

#### 🐛 Bug Fix

- Boost dandischema to ~= 0.3.1 as it provides dandischema 0.5.1 required by dandi-api [#749](https://github.com/dandi/dandi-cli/pull/749) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.26.0 (Wed Aug 04 2021)

#### 🚀 Enhancement

- Support `/asset/<asset id>/download/` URLs [#748](https://github.com/dandi/dandi-cli/pull/748) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Restore the rabbitmq version [#747](https://github.com/dandi/dandi-cli/pull/747) ([@dchiquito](https://github.com/dchiquito))
- Test against rc/2.0.0 branch of pynwb [#746](https://github.com/dandi/dandi-cli/pull/746) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.25.0 (Wed Jul 28 2021)

#### 🚀 Enhancement

- Add `replace_asset` parameter to `iter_upload_raw_asset()` [#743](https://github.com/dandi/dandi-cli/pull/743) ([@jwodder](https://github.com/jwodder))
- Rename get_assets_under_path() to get_assets_with_path_prefix() [#741](https://github.com/dandi/dandi-cli/pull/741) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Correctly set User-Agent for client requests [#742](https://github.com/dandi/dandi-cli/pull/742) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Pin rabbitmq version [#744](https://github.com/dandi/dandi-cli/pull/744) ([@dchiquito](https://github.com/dchiquito))
- Test RemoteDandiset.refresh() [#740](https://github.com/dandi/dandi-cli/pull/740) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.24.0 (Fri Jul 23 2021)

#### 🚀 Enhancement

- Python API rewrite, part 2 [#676](https://github.com/dandi/dandi-cli/pull/676) ([@jwodder](https://github.com/jwodder))
- RF: attempt nwb metadata extraction only on .nwb, if fails -- warning [#733](https://github.com/dandi/dandi-cli/pull/733) ([@yarikoptic](https://github.com/yarikoptic))
- Invoke etelemetry when constructing a DandiAPIClient; honor DANDI_NO_ET [#728](https://github.com/dandi/dandi-cli/pull/728) ([@jwodder](https://github.com/jwodder))
- Make upload() fail if client & server schema versions are not in sync [#724](https://github.com/dandi/dandi-cli/pull/724) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Log "error" statuses while uploading as ERROR log messages [#737](https://github.com/dandi/dandi-cli/pull/737) ([@jwodder](https://github.com/jwodder))
- Retry following redirects that return 404 [#734](https://github.com/dandi/dandi-cli/pull/734) ([@jwodder](https://github.com/jwodder))
- ENH: exit with non-0 when "bad_version" of dandi-cli is used [#725](https://github.com/dandi/dandi-cli/pull/725) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Stretch the doc to the screen width [#721](https://github.com/dandi/dandi-cli/pull/721) ([@yarikoptic](https://github.com/yarikoptic))
- Set "version" in docs/source/conf.py [#720](https://github.com/dandi/dandi-cli/pull/720) ([@jwodder](https://github.com/jwodder))
- Install "test" extras when building docs [#718](https://github.com/dandi/dandi-cli/pull/718) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.23.2 (Tue Jul 20 2021)

#### 🐛 Bug Fix

- Increase retries & wait times for API errors [#716](https://github.com/dandi/dandi-cli/pull/716) ([@jwodder](https://github.com/jwodder))
- Use timed wait in publish test [#706](https://github.com/dandi/dandi-cli/pull/706) ([@dchiquito](https://github.com/dchiquito))

#### 🏠 Internal

- Add Readthedocs config [#715](https://github.com/dandi/dandi-cli/pull/715) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- ENH: adding sphinx documentation for the dandi-cli [#712](https://github.com/dandi/dandi-cli/pull/712) ([@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- BF(TST): Allow for IteratorWithAggregation to get nothing if reraise_immediately [#707](https://github.com/dandi/dandi-cli/pull/707) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.23.1 (Thu Jul 08 2021)

#### 🧪 Tests

- Skip shell completion test entirely on Windows [#702](https://github.com/dandi/dandi-cli/pull/702) ([@jwodder](https://github.com/jwodder))
- BF+RF(TST): populate contentUrl to satisfy Asset requirement in 0.5.0 [#705](https://github.com/dandi/dandi-cli/pull/705) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.23.0 (Tue Jul 06 2021)

#### 🚀 Enhancement

- Add get_asset_metadata() function [#693](https://github.com/dandi/dandi-cli/pull/693) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- fix: raise error when unable to parse age and set session name properly [#669](https://github.com/dandi/dandi-cli/pull/669) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))
- fix: set CLI version to align with schema base version [#694](https://github.com/dandi/dandi-cli/pull/694) ([@satra](https://github.com/satra))
- adding valueReference to extract_age return PropertyValue; adding test [#689](https://github.com/dandi/dandi-cli/pull/689) ([@djarecka](https://github.com/djarecka) [@satra](https://github.com/satra))

#### Authors: 4

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.22.0 (Wed Jun 30 2021)

#### 🚀 Enhancement

- Adjust RemoteAsset.json_dict() [#691](https://github.com/dandi/dandi-cli/pull/691) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Create valid Dandiset metadata when testing; create valid asset metadata for non-NWB files; wait for validation before publishing [#683](https://github.com/dandi/dandi-cli/pull/683) ([@jwodder](https://github.com/jwodder))
- changing unitText [#686](https://github.com/dandi/dandi-cli/pull/686) ([@djarecka](https://github.com/djarecka))
- Fix a failing test on Windows on conda-forge (again) [#681](https://github.com/dandi/dandi-cli/pull/681) ([@jwodder](https://github.com/jwodder))
- Remove references to "dandi register" command [#684](https://github.com/dandi/dandi-cli/pull/684) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Use dandischema.metadata.validate() instead of _validate_*_json() [#685](https://github.com/dandi/dandi-cli/pull/685) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Increase minimum dandischema version to 0.2.9 [#687](https://github.com/dandi/dandi-cli/pull/687) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.21.0 (Thu Jun 24 2021)

#### 🚀 Enhancement

- Add RemoteAsset.get_content_url() method [#675](https://github.com/dandi/dandi-cli/pull/675) ([@jwodder](https://github.com/jwodder))
- Python API rewrite, part 1 [#660](https://github.com/dandi/dandi-cli/pull/660) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Don't pass "asset" field from upload iterator to pyout [#679](https://github.com/dandi/dandi-cli/pull/679) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Fix a failing test on Windows on conda-forge [#680](https://github.com/dandi/dandi-cli/pull/680) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.20.0 (Mon Jun 14 2021)

#### 🚀 Enhancement

- ENH: more metadata to reconstruct filename, upgrade to use dandischema 0.2.3 (schema 0.4.0) [#644](https://github.com/dandi/dandi-cli/pull/644) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- ls --schema: Calculate digest for local assets [#666](https://github.com/dandi/dandi-cli/pull/666) ([@jwodder](https://github.com/jwodder))
- updating parse age to cover more formats [#633](https://github.com/dandi/dandi-cli/pull/633) ([@djarecka](https://github.com/djarecka))
- fix: add a default name when using an unknown session id [#662](https://github.com/dandi/dandi-cli/pull/662) ([@satra](https://github.com/satra))

#### 🏠 Internal

- Run test workflow on pushes only on master [#667](https://github.com/dandi/dandi-cli/pull/667) ([@yarikoptic](https://github.com/yarikoptic))
- Address LGTM alerts [#657](https://github.com/dandi/dandi-cli/pull/657) ([@jwodder](https://github.com/jwodder))
- Update pre-commit repo versions and configure isort to properly handle "from . import" lines [#656](https://github.com/dandi/dandi-cli/pull/656) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.19.0 (Mon Jun 07 2021)

#### 🚀 Enhancement

- Reprompt or fail on attempt to use an invalid API token [#655](https://github.com/dandi/dandi-cli/pull/655) ([@jwodder](https://github.com/jwodder))
- dandi ls: Make json and json_pp formats output arrays; add json_lines for old json format [#654](https://github.com/dandi/dandi-cli/pull/654) ([@jwodder](https://github.com/jwodder))
- Change `download --existing` default to "error"; add "overwrite-different" option; handle git-annex repos [#646](https://github.com/dandi/dandi-cli/pull/646) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Set `auto` author to "DANDI Bot" [#649](https://github.com/dandi/dandi-cli/pull/649) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.18.0 (Wed May 26 2021)

#### 🚀 Enhancement

- Move schema code to dandischema [#643](https://github.com/dandi/dandi-cli/pull/643) ([@jwodder](https://github.com/jwodder))
- Add "shell-completion" command [#640](https://github.com/dandi/dandi-cli/pull/640) ([@jwodder](https://github.com/jwodder))
- REF: updated model requirements [#623](https://github.com/dandi/dandi-cli/pull/623) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Pin dandischema to compatible 0.minor version [#650](https://github.com/dandi/dandi-cli/pull/650) ([@yarikoptic](https://github.com/yarikoptic))
- Warn on ignored symlinks to directories [#647](https://github.com/dandi/dandi-cli/pull/647) ([@jwodder](https://github.com/jwodder))
- Delete name2title() [#645](https://github.com/dandi/dandi-cli/pull/645) ([@jwodder](https://github.com/jwodder))
- adding to_datacite method [#596](https://github.com/dandi/dandi-cli/pull/596) ([@djarecka](https://github.com/djarecka) [@yarikoptic](https://github.com/yarikoptic))
- Datacite tmp [#595](https://github.com/dandi/dandi-cli/pull/595) ([@djarecka](https://github.com/djarecka))

#### 🏠 Internal

- Include CHANGELOG.md and tox.ini in sdists [#648](https://github.com/dandi/dandi-cli/pull/648) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.17.0 (Wed May 12 2021)

#### 🚀 Enhancement

- Add "sync" option for upload & download [#616](https://github.com/dandi/dandi-cli/pull/616) ([@jwodder](https://github.com/jwodder))
- RF: organize - should no longer alter dandiset.yaml [#615](https://github.com/dandi/dandi-cli/pull/615) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Allow trailing slash in GUI URLs [#636](https://github.com/dandi/dandi-cli/pull/636) ([@jwodder](https://github.com/jwodder))
- Make the "#/" in GUI URLs optional [#637](https://github.com/dandi/dandi-cli/pull/637) ([@jwodder](https://github.com/jwodder))
- Add dandi-staging to known_instances [#621](https://github.com/dandi/dandi-cli/pull/621) ([@dchiquito](https://github.com/dchiquito))

#### ⚠️ Pushed to `master`

- RM: .github/workflows/test-populate-dandiset-yaml.yml ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- move test_get_metaadata to test_metadata.py [#634](https://github.com/dandi/dandi-cli/pull/634) ([@bendichter](https://github.com/bendichter))
- Error on PRs that modify existing schemata instead of creating a new version [#626](https://github.com/dandi/dandi-cli/pull/626) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- Ben Dichter ([@bendichter](https://github.com/bendichter))
- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.16.0 (Tue May 04 2021)

#### 🚀 Enhancement

- Restructure parse_dandi_url() return type [#605](https://github.com/dandi/dandi-cli/pull/605) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- DOC: Extend description for delete to point that it could be URL etc [#609](https://github.com/dandi/dandi-cli/pull/609) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Cut down on some code duplication in delete.py [#610](https://github.com/dandi/dandi-cli/pull/610) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Make test_server_info use Docker fixture if DANDI_REDIRECTOR_BASE is set [#612](https://github.com/dandi/dandi-cli/pull/612) ([@jwodder](https://github.com/jwodder))
- Add DANDI_DEVEL=1 job to GitHub Actions tests [#607](https://github.com/dandi/dandi-cli/pull/607) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.15.0 (Fri Apr 30 2021)

#### 🚀 Enhancement

- Remove unused functions (and other cleanups) [#604](https://github.com/dandi/dandi-cli/pull/604) ([@jwodder](https://github.com/jwodder))
- Remove Girder support [#588](https://github.com/dandi/dandi-cli/pull/588) ([@jwodder](https://github.com/jwodder))
- Give "delete" a --skip-missing option [#594](https://github.com/dandi/dandi-cli/pull/594) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Include list of supported URL patterns in `dandi ls --help` [#601](https://github.com/dandi/dandi-cli/pull/601) ([@jwodder](https://github.com/jwodder))
- Recognize "DANDI:<identifier>" strings as URL-likes [#602](https://github.com/dandi/dandi-cli/pull/602) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Support specifying the dandi redirector via an env var [#581](https://github.com/dandi/dandi-cli/pull/581) ([@jwodder](https://github.com/jwodder))
- a script to validate dandi-api collection listing against girder [#589](https://github.com/dandi/dandi-cli/pull/589) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Remove numpy pre-pinning in test.yml [#603](https://github.com/dandi/dandi-cli/pull/603) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.14.2 (Thu Apr 22 2021)

#### 🐛 Bug Fix

- BF: "girder" record might be there but "url" might be None [#591](https://github.com/dandi/dandi-cli/pull/591) ([@yarikoptic](https://github.com/yarikoptic))
- Retry upload requests that result in 500 responses [#585](https://github.com/dandi/dandi-cli/pull/585) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Add codespell [#582](https://github.com/dandi/dandi-cli/pull/582) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.14.1 (Fri Apr 16 2021)

#### 🐛 Bug Fix

- Update for the version /info endpoint in dandi-api [#575](https://github.com/dandi/dandi-cli/pull/575) ([@dchiquito](https://github.com/dchiquito))
- Log validation errors [#579](https://github.com/dandi/dandi-cli/pull/579) ([@jwodder](https://github.com/jwodder))
- Log 409 responses at DEBUG level [#578](https://github.com/dandi/dandi-cli/pull/578) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.14.0 (Thu Apr 15 2021)

#### 🚀 Enhancement

- Models: define id, add various additional types (genotype, etc), boost model version to 0.3.0 [#560](https://github.com/dandi/dandi-cli/pull/560) ([@satra](https://github.com/satra))
- Switch default dandi instance to dandi-api based on redirector [#565](https://github.com/dandi/dandi-cli/pull/565) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Add further tests of get_instance() and server-info [#571](https://github.com/dandi/dandi-cli/pull/571) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))

---

# 0.13.2 (Tue Apr 13 2021)

#### 🐛 Bug Fix

- BF: do not assume that service record of redirector is present/has url [#567](https://github.com/dandi/dandi-cli/pull/567) ([@yarikoptic](https://github.com/yarikoptic))
- Fix a typo in the display string for one of the known URL patterns [#564](https://github.com/dandi/dandi-cli/pull/564) ([@jwodder](https://github.com/jwodder))
- Error with a decent message when trying to delete() a path not in a Dandiset [#563](https://github.com/dandi/dandi-cli/pull/563) ([@jwodder](https://github.com/jwodder))
- Fix & test for downloading by asset ID URL [#561](https://github.com/dandi/dandi-cli/pull/561) ([@jwodder](https://github.com/jwodder))
- Strip trailing slash from API URL used by delete() [#559](https://github.com/dandi/dandi-cli/pull/559) ([@jwodder](https://github.com/jwodder))
- Refresh dandiset.yaml on download if out of date [#556](https://github.com/dandi/dandi-cli/pull/556) ([@jwodder](https://github.com/jwodder))
- Support "…/assets/?path=<path>" URLs [#555](https://github.com/dandi/dandi-cli/pull/555) ([@jwodder](https://github.com/jwodder))
- Get hdmf, pynwb, h5py versions without importing [#553](https://github.com/dandi/dandi-cli/pull/553) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.13.1 (Sat Apr 10 2021)

#### 🐛 Bug Fix

- Log dandi, hdmf, h5py, and pynwb versions to log file [#545](https://github.com/dandi/dandi-cli/pull/545) ([@jwodder](https://github.com/jwodder))
- small fix of extract_sex [#549](https://github.com/dandi/dandi-cli/pull/549) ([@djarecka](https://github.com/djarecka))
- Add and use get_module_version for cache tokens [#539](https://github.com/dandi/dandi-cli/pull/539) ([@yarikoptic](https://github.com/yarikoptic))
- Log errors in extracting metadata for upload [#546](https://github.com/dandi/dandi-cli/pull/546) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- DOC: minor tune up to README.md on installation instructions and WiP [#551](https://github.com/dandi/dandi-cli/pull/551) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.13.0 (Thu Apr 08 2021)

#### 🚀 Enhancement

- Add "delete" command [#509](https://github.com/dandi/dandi-cli/pull/509) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Update dandiarchive client to use most_recent_published_version [#537](https://github.com/dandi/dandi-cli/pull/537) ([@dchiquito](https://github.com/dchiquito) [@yarikoptic](https://github.com/yarikoptic))
- Support parsing & navigating asset download URLs [#535](https://github.com/dandi/dandi-cli/pull/535) ([@jwodder](https://github.com/jwodder))
- Give `ls` a `--metadata` option [#536](https://github.com/dandi/dandi-cli/pull/536) ([@jwodder](https://github.com/jwodder))
- Fix retrying 503's [#528](https://github.com/dandi/dandi-cli/pull/528) ([@jwodder](https://github.com/jwodder))
- Retry requests that fail with 503 [#521](https://github.com/dandi/dandi-cli/pull/521) ([@jwodder](https://github.com/jwodder))
- Better filtering of file-only log messages [#523](https://github.com/dandi/dandi-cli/pull/523) ([@jwodder](https://github.com/jwodder))
- Fix typo in setting jobs_per_file for upload command [#519](https://github.com/dandi/dandi-cli/pull/519) ([@jwodder](https://github.com/jwodder))
- fix to migrate2newschema [#515](https://github.com/dandi/dandi-cli/pull/515) ([@djarecka](https://github.com/djarecka))
- BF(workaround): get the list of entries with sizes before querying [#513](https://github.com/dandi/dandi-cli/pull/513) ([@yarikoptic](https://github.com/yarikoptic))
- fix: remove unset fields to enable schemaKey [#512](https://github.com/dandi/dandi-cli/pull/512) ([@satra](https://github.com/satra))
- Fixes conversion of existing dandiset metadata with sub-object validation [#505](https://github.com/dandi/dandi-cli/pull/505) ([@satra](https://github.com/satra))
- Upload file parts in parallel [#499](https://github.com/dandi/dandi-cli/pull/499) ([@jwodder](https://github.com/jwodder))

#### ⚠️ Pushed to `master`

- DOC: provide instructions in DEVELOPMENT.md for interaction with dandi-api instance ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- ENH: Enhancements to metadata schema and compatibility with JSONLD [#517](https://github.com/dandi/dandi-cli/pull/517) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic))
- Add --only-metadata option to migrate-dandisets.py [#511](https://github.com/dandi/dandi-cli/pull/511) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Add tests of json_dict() method [#526](https://github.com/dandi/dandi-cli/pull/526) ([@jwodder](https://github.com/jwodder))
- Store metadata test JSON in files [#525](https://github.com/dandi/dandi-cli/pull/525) ([@jwodder](https://github.com/jwodder))
- Run "provision" container in the foreground [#506](https://github.com/dandi/dandi-cli/pull/506) ([@jwodder](https://github.com/jwodder))
- Ignore warnings from ruamel.yaml caused by hdmf using deprecated functions [#507](https://github.com/dandi/dandi-cli/pull/507) ([@jwodder](https://github.com/jwodder))

#### Authors: 5

- Daniel Chiquito ([@dchiquito](https://github.com/dchiquito))
- Dorota Jarecka ([@djarecka](https://github.com/djarecka))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.12.1 (Thu Mar 25 2021)

#### 🐛 Bug Fix

- Lowercase "sha256" [#493](https://github.com/dandi/dandi-cli/pull/493) ([@jwodder](https://github.com/jwodder))
- Validate uploads before digesting [#495](https://github.com/dandi/dandi-cli/pull/495) ([@jwodder](https://github.com/jwodder))
- Check for already-uploaded blobs via /uploads/initialize/ instead of /blobs/digest/ [#496](https://github.com/dandi/dandi-cli/pull/496) ([@jwodder](https://github.com/jwodder))
- Update upload code for changes in API [#479](https://github.com/dandi/dandi-cli/pull/479) ([@jwodder](https://github.com/jwodder))
- dandi ls: Error if --schema is given with remote resource of different version [#489](https://github.com/dandi/dandi-cli/pull/489) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Add option for only running new Dandi API tests [#500](https://github.com/dandi/dandi-cli/pull/500) ([@jwodder](https://github.com/jwodder))
- Don't hardcode DANDI_SCHEMA_VERSION value in tests [#491](https://github.com/dandi/dandi-cli/pull/491) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.12.0 (Tue Mar 23 2021)

#### 🚀 Enhancement

- Add "digest" command [#480](https://github.com/dandi/dandi-cli/pull/480) ([@jwodder](https://github.com/jwodder))
- ENH: prototype for the DANDIEtag "digester" [#474](https://github.com/dandi/dandi-cli/pull/474) ([@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))
- Change BareAssetMeta.digest to a list [#460](https://github.com/dandi/dandi-cli/pull/460) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Remove "current" column from upload progress display [#486](https://github.com/dandi/dandi-cli/pull/486) ([@jwodder](https://github.com/jwodder))
- Add dandi_etag digest type to schema [#481](https://github.com/dandi/dandi-cli/pull/481) ([@jwodder](https://github.com/jwodder))
- Add --devel-debug to `dandi validate` [#476](https://github.com/dandi/dandi-cli/pull/476) ([@jwodder](https://github.com/jwodder))
- Only call logging.basicConfig() when used as a command [#468](https://github.com/dandi/dandi-cli/pull/468) ([@jwodder](https://github.com/jwodder))
- BF: Require pydantic >= 1.8.1 [#461](https://github.com/dandi/dandi-cli/pull/461) ([@yarikoptic](https://github.com/yarikoptic))
- Fix "%s: ok" log message from `dandi validate` [#462](https://github.com/dandi/dandi-cli/pull/462) ([@jwodder](https://github.com/jwodder))
- Display `dandi validate` errors using logger [#459](https://github.com/dandi/dandi-cli/pull/459) ([@jwodder](https://github.com/jwodder))
- ENH: more of lgr.debug for multipart upload [#457](https://github.com/dandi/dandi-cli/pull/457) ([@yarikoptic](https://github.com/yarikoptic))
- Rename DandiMeta to DandisetMeta [#454](https://github.com/dandi/dandi-cli/pull/454) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Script for generating S3 versioned file stats [#473](https://github.com/dandi/dandi-cli/pull/473) ([@jwodder](https://github.com/jwodder))
- Add `-vv` option to `auto shipit` [#471](https://github.com/dandi/dandi-cli/pull/471) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.11.0 (Mon Mar 08 2021)

#### 🚀 Enhancement

- Update  and simplify models to support automated editor generation [#348](https://github.com/dandi/dandi-cli/pull/348) ([@satra](https://github.com/satra) [@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))
- Use separate session for S3 requests [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- BF: no --develop-debug for download ATM [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
- RF: moved handling of dandiset identifier "deduction" into Dandiset itself [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
- BF(workaround): allow for "proper" identifier according to new schema [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
- Merge remote-tracking branch 'origin/master' into gh-320 [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
- Further fixes [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Give DandiAPIClient a dandi_authenticate() method [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Fixes [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Rename DANDI_API_KEY to DANDI_GIRDER_API_KEY [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Test of uploading & downloading via new API [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- RF+ENH: support mapping for direct API urls, and use netlify instance instead of api+ prefix [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
- Delint [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- RF: account for web UI URL changes/dropped features, remove support for girder URLs [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
- Handle uploading already-extant assets [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Use new metadata schema [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Yield more from iter_upload() [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Document upload method parameters [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- New API upload function [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Give dandi_instance a metadata_version field [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Split Docker Compose dandi_instances and fixtures in two [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))
- Add dandi-api instance record [#330](https://github.com/dandi/dandi-cli/pull/330) ([@jwodder](https://github.com/jwodder))

#### 🐛 Bug Fix

- Add dateModified to asset metadata [#452](https://github.com/dandi/dandi-cli/pull/452) ([@jwodder](https://github.com/jwodder))
- fix: change enum to const for single enums [#449](https://github.com/dandi/dandi-cli/pull/449) ([@satra](https://github.com/satra))
- Add --new-schema option to `ls` command for converting output [#445](https://github.com/dandi/dandi-cli/pull/445) ([@jwodder](https://github.com/jwodder))
- Eliminate check for session_start_time preceding date_of_birth [#440](https://github.com/dandi/dandi-cli/pull/440) ([@jwodder](https://github.com/jwodder))
- Eliminate DANDI_SCHEMA; add get_schema_version() [#442](https://github.com/dandi/dandi-cli/pull/442) ([@jwodder](https://github.com/jwodder))
- Discard empty "sex" and "species" fields on conversion [#438](https://github.com/dandi/dandi-cli/pull/438) ([@jwodder](https://github.com/jwodder))
- schema: minor spotted typo fixes [#435](https://github.com/dandi/dandi-cli/pull/435) ([@yarikoptic](https://github.com/yarikoptic))
- Retry requests on ConnectionErrors [#437](https://github.com/dandi/dandi-cli/pull/437) ([@jwodder](https://github.com/jwodder))
- Include HDMF version as well into the token [#434](https://github.com/dandi/dandi-cli/pull/434) ([@yarikoptic](https://github.com/yarikoptic))
- Error if sha256 digest is missing from asset being downloaded [#428](https://github.com/dandi/dandi-cli/pull/428) ([@jwodder](https://github.com/jwodder))
- Report dandi version in User-Agent header [#424](https://github.com/dandi/dandi-cli/pull/424) ([@jwodder](https://github.com/jwodder))
- Remove misleading log message about authenticating with new API [#425](https://github.com/dandi/dandi-cli/pull/425) ([@jwodder](https://github.com/jwodder))
- Distinguish between pre- and post-validation when uploading [#420](https://github.com/dandi/dandi-cli/pull/420) ([@jwodder](https://github.com/jwodder))
- Log failed HTTP connections; include PID and TID in logs; include asset path in upload log messages [#418](https://github.com/dandi/dandi-cli/pull/418) ([@jwodder](https://github.com/jwodder))
- Revert PR #409 (Content-MD5 header) [#419](https://github.com/dandi/dandi-cli/pull/419) ([@jwodder](https://github.com/jwodder))
- Set Content-MD5 header when uploading asset parts [#409](https://github.com/dandi/dandi-cli/pull/409) ([@jwodder](https://github.com/jwodder))
- upload(): Only yield first "validating" status to pyout [#417](https://github.com/dandi/dandi-cli/pull/417) ([@jwodder](https://github.com/jwodder))
- Add more logging when uploading & downloading [#412](https://github.com/dandi/dandi-cli/pull/412) ([@jwodder](https://github.com/jwodder))
- Sleep increasing amounts while waiting for uploaded assets to validate [#408](https://github.com/dandi/dandi-cli/pull/408) ([@jwodder](https://github.com/jwodder))
- Populate wasDerivedFrom [#386](https://github.com/dandi/dandi-cli/pull/386) ([@jwodder](https://github.com/jwodder))
- FIX: use authorized checkout for actions [#403](https://github.com/dandi/dandi-cli/pull/403) ([@satra](https://github.com/satra))
- enh: account for samples, sessions and participants [#392](https://github.com/dandi/dandi-cli/pull/392) ([@satra](https://github.com/satra) [@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- Disabling logging to stderr while using pyout [#401](https://github.com/dandi/dandi-cli/pull/401) ([@jwodder](https://github.com/jwodder))
- Cache file digests and check for change in digest when uploading [#391](https://github.com/dandi/dandi-cli/pull/391) ([@jwodder](https://github.com/jwodder))
- Make existing="refresh" a synonym for "overwrite" for new upload [#390](https://github.com/dandi/dandi-cli/pull/390) ([@jwodder](https://github.com/jwodder))
- RF/NF: Identifiable and BareAssetMeta to describe an asset anywhere [#373](https://github.com/dandi/dandi-cli/pull/373) ([@yarikoptic](https://github.com/yarikoptic) [@jwodder](https://github.com/jwodder))
- Give known_urls human-readable display strings [#384](https://github.com/dandi/dandi-cli/pull/384) ([@jwodder](https://github.com/jwodder))
- Make `dandi download -i <instance>` run in a Dandiset download that Dandiset [#383](https://github.com/dandi/dandi-cli/pull/383) ([@jwodder](https://github.com/jwodder))
- Give `validate` command a `--schema VERSION` option for validating assets and dandiset.yaml [#379](https://github.com/dandi/dandi-cli/pull/379) ([@jwodder](https://github.com/jwodder))
- Support downloading folders and latest Dandiset version [#377](https://github.com/dandi/dandi-cli/pull/377) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- Add `include_metadata=False` parameter to asset-listing DandiAPIClient methods [#378](https://github.com/dandi/dandi-cli/pull/378) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- Discard invalid asset identifiers when extracting metadata [#374](https://github.com/dandi/dandi-cli/pull/374) ([@jwodder](https://github.com/jwodder))
- Handle uploading already-present files in new API [#347](https://github.com/dandi/dandi-cli/pull/347) ([@jwodder](https://github.com/jwodder))
- Adjust license metadata conversion [#364](https://github.com/dandi/dandi-cli/pull/364) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- Give AssetMeta and DandiMeta `json_dict()` methods for better dictification [#346](https://github.com/dandi/dandi-cli/pull/346) ([@jwodder](https://github.com/jwodder))
- BF: allow to handle an item with multiple files [#342](https://github.com/dandi/dandi-cli/pull/342) ([@yarikoptic](https://github.com/yarikoptic))
- ENH: devel upload dandiset metadata [#341](https://github.com/dandi/dandi-cli/pull/341) ([@yarikoptic](https://github.com/yarikoptic))
- Try self.listFile() again on ConnectionErrors [#335](https://github.com/dandi/dandi-cli/pull/335) ([@jwodder](https://github.com/jwodder))
- Add functions for validating metadata against JSON Schema and use in tests [#338](https://github.com/dandi/dandi-cli/pull/338) ([@jwodder](https://github.com/jwodder))
- Fix `AttributeError: 'Resource' object has no attribute 'values'` [#336](https://github.com/dandi/dandi-cli/pull/336) ([@jwodder](https://github.com/jwodder))
- [DATALAD RUNCMD] Swap order of str and AnyUrl to be from specific to generic [#334](https://github.com/dandi/dandi-cli/pull/334) ([@yarikoptic](https://github.com/yarikoptic))
- cleaning up biosample and participant [#312](https://github.com/dandi/dandi-cli/pull/312) ([@satra](https://github.com/satra) [@jwodder](https://github.com/jwodder))
- Tee all logs to user log directory [#318](https://github.com/dandi/dandi-cli/pull/318) ([@jwodder](https://github.com/jwodder))
- Update for new API at https://api.dandiarchive.org/api [#283](https://github.com/dandi/dandi-cli/pull/283) ([@jwodder](https://github.com/jwodder))

#### ⚠️ Pushed to `master`

- Merge branch 'gh-320' ([@yarikoptic](https://github.com/yarikoptic))
- DOC: provide description for both DANDI_API_KEY and DANDI_GIRDER_API_KEY ([@yarikoptic](https://github.com/yarikoptic))
- ENH: log at DEBUG result.text from a failed response ([@yarikoptic](https://github.com/yarikoptic))
- ENH: allow for DeprecationWarning to come from requests_toolbelt, not our problem ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Cache the individual functions called by validate_file() [#446](https://github.com/dandi/dandi-cli/pull/446) ([@jwodder](https://github.com/jwodder))
- Simplify release workflow [#444](https://github.com/dandi/dandi-cli/pull/444) ([@jwodder](https://github.com/jwodder))
- Check out dandi/dandi-api-datasets with direct `git clone` [#443](https://github.com/dandi/dandi-cli/pull/443) ([@jwodder](https://github.com/jwodder))
- Use iter_content() instead of raw.stream() [#423](https://github.com/dandi/dandi-cli/pull/423) ([@jwodder](https://github.com/jwodder))
- Update Black [#426](https://github.com/dandi/dandi-cli/pull/426) ([@jwodder](https://github.com/jwodder))
- Assorted code cleanup [#422](https://github.com/dandi/dandi-cli/pull/422) ([@jwodder](https://github.com/jwodder))
- Use fscacher [#397](https://github.com/dandi/dandi-cli/pull/397) ([@jwodder](https://github.com/jwodder))
- Use PUT endpoint to replace pre-existing assets on upload [#394](https://github.com/dandi/dandi-cli/pull/394) ([@jwodder](https://github.com/jwodder))
- Support passing precomputed file digest to DandiAPIClient upload methods [#388](https://github.com/dandi/dandi-cli/pull/388) ([@jwodder](https://github.com/jwodder))
- Set asset path via metadata only [#382](https://github.com/dandi/dandi-cli/pull/382) ([@jwodder](https://github.com/jwodder))
- Add script for migrating Dandiset metadata [#366](https://github.com/dandi/dandi-cli/pull/366) ([@jwodder](https://github.com/jwodder))
- Add workflow for running populate_dandiset_yaml.py [#363](https://github.com/dandi/dandi-cli/pull/363) ([@jwodder](https://github.com/jwodder))
- Configure & apply isort via pre-commit [#353](https://github.com/dandi/dandi-cli/pull/353) ([@jwodder](https://github.com/jwodder))
- Sort install_requires [#351](https://github.com/dandi/dandi-cli/pull/351) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- List extra auto labels in DEVELOPMENT.md [#381](https://github.com/dandi/dandi-cli/pull/381) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Set DJANGO_DANDI_SCHEMA_VERSION in docker-compose.yml [#429](https://github.com/dandi/dandi-cli/pull/429) ([@jwodder](https://github.com/jwodder))
- Add test of upload of large file to new API [#415](https://github.com/dandi/dandi-cli/pull/415) ([@jwodder](https://github.com/jwodder))
- Capture all dandi log messages when testing [#413](https://github.com/dandi/dandi-cli/pull/413) ([@jwodder](https://github.com/jwodder))
- Add CI run with dev version of pynwb [#399](https://github.com/dandi/dandi-cli/pull/399) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- Add sample Dandiset test fixture [#380](https://github.com/dandi/dandi-cli/pull/380) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- Add DANDI_TESTS_PERSIST_DOCKER_COMPOSE envvar for reusing Docker containers across test runs [#354](https://github.com/dandi/dandi-cli/pull/354) ([@jwodder](https://github.com/jwodder))
- Fix numpy dependency issue in tests [#356](https://github.com/dandi/dandi-cli/pull/356) ([@jwodder](https://github.com/jwodder))
- Fetch Django test API token more robustly [#323](https://github.com/dandi/dandi-cli/pull/323) ([@jwodder](https://github.com/jwodder))
- Require keyring backends to be initialized before running any tests [#326](https://github.com/dandi/dandi-cli/pull/326) ([@jwodder](https://github.com/jwodder))
- Install hdf5 for Python 3.9 tests [#315](https://github.com/dandi/dandi-cli/pull/315) ([@jwodder](https://github.com/jwodder))
- Close a file in a test case [#314](https://github.com/dandi/dandi-cli/pull/314) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.10.0 (Tue Dec 08 2020)

#### 🚀 Enhancement

- Set chunk size on per-file basis; limit to 1000 chunks; upload files up to 400GB ATM [#310](https://github.com/dandi/dandi-cli/pull/310) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Autogenerate schema element titles [#304](https://github.com/dandi/dandi-cli/pull/304) ([@jwodder](https://github.com/jwodder))
- Compare uploaded file size against what download headers report [#306](https://github.com/dandi/dandi-cli/pull/306) ([@jwodder](https://github.com/jwodder))
- fix: rat to common lab rat [#307](https://github.com/dandi/dandi-cli/pull/307) ([@satra](https://github.com/satra))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.0 (Fri Dec 04 2020)

#### 🚀 Enhancement

- Function for converting NWB file to AssetMeta instance [#226](https://github.com/dandi/dandi-cli/pull/226) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic) [@satra](https://github.com/satra))

#### 🐛 Bug Fix

- Temporary workaround: prevent upload of files larger than 67108864000 [#303](https://github.com/dandi/dandi-cli/pull/303) ([@yarikoptic](https://github.com/yarikoptic))
- Add title to `Field` calls where necessary [#299](https://github.com/dandi/dandi-cli/pull/299) ([@AlmightyYakob](https://github.com/AlmightyYakob) [@satra](https://github.com/satra))
- Replace askyesno() with click.confirm() [#296](https://github.com/dandi/dandi-cli/pull/296) ([@jwodder](https://github.com/jwodder))
- Test against & support Python 3.9 [#297](https://github.com/dandi/dandi-cli/pull/297) ([@jwodder](https://github.com/jwodder))
- ls - avoid workaround, more consistent reporting of errors [#293](https://github.com/dandi/dandi-cli/pull/293) ([@yarikoptic](https://github.com/yarikoptic))
- add dandimeta migration [#295](https://github.com/dandi/dandi-cli/pull/295) ([@satra](https://github.com/satra))
- Nwb2asset [#294](https://github.com/dandi/dandi-cli/pull/294) ([@satra](https://github.com/satra))
- Some schema updates [#286](https://github.com/dandi/dandi-cli/pull/286) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic) [@dandibot](https://github.com/dandibot) auto@nil [@satra](https://github.com/satra))
- make most things optional [#234](https://github.com/dandi/dandi-cli/pull/234) ([@satra](https://github.com/satra))

#### 🏠 Internal

- Fix more of publish-schemata workflow [#292](https://github.com/dandi/dandi-cli/pull/292) ([@jwodder](https://github.com/jwodder))

#### Authors: 6

- [@dandibot](https://github.com/dandibot)
- auto (auto@nil)
- Jacob Nesbitt ([@AlmightyYakob](https://github.com/AlmightyYakob))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.8.0 (Tue Dec 01 2020)

#### 🚀 Enhancement

- Add rudimentary duecredit support using zenodo's dandi-cli DOI [#285](https://github.com/dandi/dandi-cli/pull/285) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- BF: add h5py.__version__ into the list of tokens for caching [#284](https://github.com/dandi/dandi-cli/pull/284) ([@yarikoptic](https://github.com/yarikoptic))
- change from disease to disorder [#291](https://github.com/dandi/dandi-cli/pull/291) ([@satra](https://github.com/satra))

#### 🏠 Internal

- Fix publish-schemata workflow [#290](https://github.com/dandi/dandi-cli/pull/290) ([@jwodder](https://github.com/jwodder))
- updated just models [#287](https://github.com/dandi/dandi-cli/pull/287) ([@satra](https://github.com/satra))
- Add workflow for publishing model schemata to dandi/schema [#276](https://github.com/dandi/dandi-cli/pull/276) ([@jwodder](https://github.com/jwodder))
- DOC: strip away duplicate with the handbook information [#279](https://github.com/dandi/dandi-cli/pull/279) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.7.2 (Thu Nov 19 2020)

#### 🐛 Bug Fix

- Support h5py 3.0 [#275](https://github.com/dandi/dandi-cli/pull/275) ([@jwodder](https://github.com/jwodder))
- Include item path in "Multiple files found for item" message [#271](https://github.com/dandi/dandi-cli/pull/271) ([@jwodder](https://github.com/jwodder))
- Copy files with `cp --reflink=auto` where supported [#269](https://github.com/dandi/dandi-cli/pull/269) ([@jwodder](https://github.com/jwodder))
- Make keyring lookup more flexible [#267](https://github.com/dandi/dandi-cli/pull/267) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Add healthchecks for the Postgres and minio Docker containers [#272](https://github.com/dandi/dandi-cli/pull/272) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.7.1 (Thu Nov 05 2020)

#### 🐛 Bug Fix

- Use oldest file when race condition causes multiple files per item [#265](https://github.com/dandi/dandi-cli/pull/265) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Set up workflow with auto for releasing & PyPI uploads [#257](https://github.com/dandi/dandi-cli/pull/257) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Remove unused link from CHANGELOG.md [#266](https://github.com/dandi/dandi-cli/pull/266) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# [0.7.0] - 2020-11-04

## Added
- Files are now stored in temporary directories while downloading alongside
  metadata for use in resuming interrupted downloads

## Changed
- Moved code for navigating Dandi Archive into new `dandiarchive` submodule
- YAML output now sorts keys
- `dandiset.yaml` is no longer uploaded to the archive
- Restrict h5py dependency to pre-v3.0

# [0.6.4] - 2020-09-04

Primarily a range of bugfixes to ensure correct operation with current state
of other components of DANDI, and use of the client on Windows OS.

## Added
- Initial DANDI schema files
- More tests for various code paths
- `download`: new option `--download [assets,dandiset.yaml,all]`
## Fixed
- `download` - account for changes in DANDI API (relevant only for released
  datasets, of which we do not have any "real" ones yet)
- `upload` - various Windows specific fixes

Note: [0.6.3] was released under missing some of the fixes, so overall
abandoned.

# [0.6.2] - 2020-08-19

## Fixed
- `organize` treatment of paths on window (gh-204)

# [0.6.1] - 2020-08-18

## Changed
- CLI modules RF to avoid circular imports
- `pytest` default traceback style is short and shows 10 slowest tsts
## Fixed
- `download` of draft datasets from Windows (gh-202)
- `upload` and other tests to account for new web UI

# [0.6.0] - 2020-08-12

A variety of improvements and bug fixes, with major changes toward support
of a new DANDI API, and improving DX (Development eXperience).

## Added
- Support for WiP DANDI API service.
  `download` now can download from "published" (versioned) dandisets.
- A wide range of development enhancements
  - `tox` setup
  - code linting via `tox` and on github workflows
  - testing against Python 3.8
  - testing against a local instance of the archive via `docker-compose`,
    which is used against
- Locking of the dandiset during upload to prevent multiple sessions modifying
  the same dandiset in the archive
- `upload` now adds `uploaded_by` field into the item metadata
## Changed
- `download` was refactored and new UI also uses pyout (as
  `upload` and `ls`) so there will be no tqdm progress bar indicators.
  `download` also does "on-the-fly" integrity of the data as received
  (whenever corresponding metadata provided from the archive)
- `--log-level` could be numeric or specified in lower-case
- Unified YAML operations to `ruamel.yaml`
- Avoid hardcoded URLs for dandiarchive components by querying `/server-info`
- Improved logging for interactions with girder server
## Fixed
- minor compatibility issues across OSes

# [0.5.0] - 2020-06-04

## Added
- `metadata` and `organize`: extract and use `probe_ids` metadata to
  disambiguate (if needed)
- `organize`: `--devel-debug` option to perform metadata extraction serially
- `upload`:
  - `--allow-any-path` development option to allow upload of DANDI
    not yet 'unsupported' file types/paths
  - compute 4 digests (all are checksums ATM): md5, sha1, sha256, sha512
    and upload as a part of the metadata record
- `download`:
  - use the "fastest" available digest (sha1) to validate correctness of the
    download
  - follow redirections from arbitrary redirector (e.g., bit.ly). Succeeds
    only if the final URL is known to DANDI.
## Fixed
- `upload`: a crash while issuing a record to update about deleted empty item
## Refactored
- `organize`: disambiguation process now could use a flexible list of metadata
  fields (ATM only `probe_ids` and `obj_id`)
- `download`: handling of redirection - now uses `HEAD` request instead of `GET`

# [0.4.6] - 2020-05-07

## Fixed
- invoke etelemetry only in command line (at click interface level)
- download of updated dandiset landing page url (`/dandiset` not `/dandiset-meta`)

# [0.4.5] - 2020-05-01

## Added
- support for downloading dandisets and files in the just released
  gui.dandiarchive.org UI refactor
## Fixed
- `validate` should no longer crash if loading metadata raises an exception
## Refactored
- the way URLs are mapped into girder instances. Now more regex driven

# [0.4.4] - 2020-04-14

## Added
- `validate` now will report absent `subject_id` as an error
## Fixed
- Caching of multiple functions re-using the same cache -- it could
  have resulted in our case neural data types returned where full metadata
  was requested, or vice versa
- Tolerate outdated (before 2.0.0) etelemetry


# [0.4.3] - 2020-04-14

## Added
- Ability to download (multiple) individual files (using URL from
  gui.dandiarchive.org having files selected)
## Changed
- `DANDI_CACHE_CLEAR` -> `DANDI_CACHE=(ignore|clear)` env variable.
- Sanitize and tollerate better incorrect `nwb_version` field.
## Fixed
- Test to not invoke Popen with shell=True to avoid stalling.
- Explicit `NO_ET=1` in workflows to avoid overreporting to etelemetry.


# [0.4.2] - 2020-03-18

## Added
- Use of etelemetry for informing about new (or bad) versions
## Changed
- Fixed saving into yaml so it is consistently not using a flow style
  (#59)
- All file names starting with a period are not considered (#63)

# [0.4.1] - 2020-03-16

## Changed
- `organize` -- now would add `_obj-` key with the crc32 checksum
  of the nwb file `object_id` if files could not be otherwise
  disambiguated
- variety of small tune ups and fixes
## Removed
- `organize` -- not implemented option `--format`
- `upload` -- not properly implemented option `-d|--dandiset-path`

# [0.4.0] - 2020-03-13

Provides interfaces for a full cycle of dandiset preparation,
registration, upload, and download.

## Added
- caching of read metadata and validation results for .nwb files.
  Typically those take too long and as long as dandi and pynwb
  versions do not change -- results should not change.
  Set `DANDI_DEVEL` variable to forcefully reset all the caches.
## Changed
- DEVELOPMENT.md provides more information about full local
  test setup of the dandiarchive, and description of
  environment variables which could assist in development.

# [0.3.0] - 2020-02-28

## Added
- `organize`: organize files into hierarchy using metadata.
  ATM operates only in "simulate" mode using .json files dumped by `ls`
## Changed
- various refactorings and minor improvements (docs, testing, etc).


# [0.2.0] - 2020-02-04

Improvements to `ls` and `upload` commands

## Added
- `ls`: include a list (with counts) of neural datatypes in the file
- `upload`:
  - ability to reupload files (by removing already existing ones)
  - ability to "sync" (skip if not modified) to girder based on mtime
    and size
- CI (github actions): testing on macos-latest
## Changed
- removed `hdmf !=` statement in setup.cfg to not confuse pypi.
## Fixed
- `upload` - assure string for an error message
- mitigated crashes in pynwb if neural data type schema is not cached
  in the file and requires import of the extension module.  ATM the
  known/handled only the `AIBS_ecephys` from `allensdk`
