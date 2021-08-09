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
- RF+ENH: support mapping for direct API urls, and use netflify insstance instead of api+ prefix [#330](https://github.com/dandi/dandi-cli/pull/330) ([@yarikoptic](https://github.com/yarikoptic))
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
