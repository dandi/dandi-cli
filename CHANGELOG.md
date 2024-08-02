# 0.10.0 (Fri Jul 19 2024)

#### 🚀 Enhancement

- Update readme [#50](https://github.com/lincbrain/linc-cli/pull/50) ([@kabilar](https://github.com/kabilar))
- Attempt to resolve versioneer compatibility issues [#51](https://github.com/lincbrain/linc-cli/pull/51) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### 🐛 Bug Fix

- Update readme links and fix spelling [#46](https://github.com/lincbrain/linc-cli/pull/46) ([@kabilar](https://github.com/kabilar))
- Pin dandischema to 0.10.1 to resolve API /info schema version match [#49](https://github.com/lincbrain/linc-cli/pull/49) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))
- Include logic to properly authenticate a user upon the move command, pin dandischema to 0.10.0 [#42](https://github.com/lincbrain/linc-cli/pull/42) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 3

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)
- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))

---

# 0.9.0 (Wed Mar 13 2024)

#### 🚀 Enhancement

- Include new token for PyPI push [#40](https://github.com/lincbrain/linc-cli/pull/40) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)

---

# 0.8.0 (Wed Mar 13 2024)

#### 🚀 Enhancement

- Refresh permissions on pypi [#39](https://github.com/lincbrain/linc-cli/pull/39) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)

---

# 0.7.0 (Wed Mar 13 2024)

#### 🚀 Enhancement

- Trivial change to bump linc-cli to include pydantic 2 updates [#38](https://github.com/lincbrain/linc-cli/pull/38) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### ⚠️ Pushed to `master`

- Merge upstream changes from dandi-cli for pydantic 2.0 (aaronkanzer@Aarons-MacBook-Pro.local)
- Add tests for `is_same_url()` ([@jwodder](https://github.com/jwodder))
- [DATALAD RUNCMD] Rename SPECIES_URI_TEMPLATE into NCBITAXON_URI_TEMPLATE ([@yarikoptic](https://github.com/yarikoptic))
- Clean up URL parsing in `extract_species()` ([@jwodder](https://github.com/jwodder))
- Use yarl in `is_same_url()` ([@jwodder](https://github.com/jwodder))
- Replace most uses of urllib with yarl ([@jwodder](https://github.com/jwodder))
- Add tests ([@jwodder](https://github.com/jwodder))
- Add `embargo` option to `create_dandiset()` ([@jwodder](https://github.com/jwodder))
- Add arguments for API query parameters when fetching all Dandisets ([@jwodder](https://github.com/jwodder))
- Report progress in deleting Zarr entries during upload ([@jwodder](https://github.com/jwodder))
- upload: Rename "upload" pyout column to "progress" ([@jwodder](https://github.com/jwodder))
- Adjust joinurl() docs ([@jwodder](https://github.com/jwodder))
- Accept both dandischema 0.9.x and 0.10.x ([@jwodder](https://github.com/jwodder))
- Update for Pydantic v2 ([@jwodder](https://github.com/jwodder))
- Update pydantic requirement to ~= 2.0 ([@jwodder](https://github.com/jwodder))
- Use dandischema 0.9 ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.6.1 (Wed Feb 14 2024)

#### 🐛 Bug Fix

- Change naming conventions in CLI tool to match LINC [#37](https://github.com/lincbrain/linc-cli/pull/37) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)

---

# 0.6.0 (Wed Feb 14 2024)

#### 🚀 Enhancement

- Trivial change to update LINC release from dandi-0.59-1 [#36](https://github.com/lincbrain/linc-cli/pull/36) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))
- Merge 0.59.1 of dandi-cli into linc-cli [#36](https://github.com/lincbrain/linc-cli/pull/36) (aaronkanzer@Aarons-MacBook-Pro.local)

#### ⚠️ Pushed to `master`

- [gh-actions](deps): Bump codecov/codecov-action from 3 to 4 ([@dependabot[bot]](https://github.com/dependabot[bot]))
- blacklist buggy nwbinspector 0.4.32 ([@yarikoptic](https://github.com/yarikoptic))
- Failsafe etelemetry import ([@TheChymera](https://github.com/TheChymera))
- Remove note from error messages ([@jwodder](https://github.com/jwodder))
- Add notes to error messages & docs about `get_metadata()` vs. `get_raw_metadata()` ([@jwodder](https://github.com/jwodder))
- Update zarr_checksum dependency to `~= 0.4.0` ([@jwodder](https://github.com/jwodder))
- Update zarr_checksum dependency to `~= 0.3.2` ([@jwodder](https://github.com/jwodder))
- Ignore irrelevant deprecation warning from pandas ([@jwodder](https://github.com/jwodder))
- Minor codespell fix ([@yarikoptic](https://github.com/yarikoptic))
- Fix service script tests for change in autogenerated date ([@jwodder](https://github.com/jwodder))
- `dandi download dandi://…/dandiset.yaml` now downloads `dandiset.yaml` ([@jwodder](https://github.com/jwodder))
- Update readme ([@kabilar](https://github.com/kabilar))
- Update docstring ([@kabilar](https://github.com/kabilar))
- [gh-actions](deps): Bump github/codeql-action from 2 to 3 ([@dependabot[bot]](https://github.com/dependabot[bot]))
- Add tests of post_upload_size_check() ([@jwodder](https://github.com/jwodder))
- Update README.md ([@kabilar](https://github.com/kabilar))
- Update docs/source/cmdline/validate.rst ([@kabilar](https://github.com/kabilar))
- Update dandi/cli/cmd_validate.py ([@kabilar](https://github.com/kabilar))
- Add test ([@jwodder](https://github.com/jwodder))
- Update docs ([@kabilar](https://github.com/kabilar))
- Update gitignore ([@kabilar](https://github.com/kabilar))
- Properly open filehandles for `RemoteReadableAsset`s ([@jwodder](https://github.com/jwodder))
- Dedup log message ([@jwodder](https://github.com/jwodder))
- Double-check file sizes before & after uploading ([@jwodder](https://github.com/jwodder))
- [gh-actions](deps): Bump actions/setup-python from 4 to 5 ([@dependabot[bot]](https://github.com/dependabot[bot]))
- Copy `dandischema.digests.zarr.get_checksum()` to dandi-cli ([@jwodder](https://github.com/jwodder))
- Repeatedly double-check return values of zero when spying on `super_len()` ([@jwodder](https://github.com/jwodder))
- Set 30-second connect & read timeout when downloading files ([@jwodder](https://github.com/jwodder))
- Move imports in functions to top level or annotate why they can't be moved ([@jwodder](https://github.com/jwodder))
- Remove redundant `ensure_datetime()` call ([@jwodder](https://github.com/jwodder))
- Update for `zarr_checksum` 0.2.12 ([@jwodder](https://github.com/jwodder))
- Make it compatible with py 3.8, thanks @jwodder ([@yarikoptic](https://github.com/yarikoptic))
- Ignore deprecation warnings addressed in joblib already ([@yarikoptic](https://github.com/yarikoptic))
- RF: replace use of deprecated utcnow() ([@yarikoptic](https://github.com/yarikoptic))
- BF: ignore DeprecationWarning within dateutil which triggers while considering the next listed warning ([@yarikoptic](https://github.com/yarikoptic))
- Use released 3.12 ([@yarikoptic](https://github.com/yarikoptic))
- I think we need the .gitattributes here but forgot to git add it ([@yarikoptic](https://github.com/yarikoptic))
- Upgrade versioneer to the current non-released one with 3.12 support ([@yarikoptic](https://github.com/yarikoptic))
- Add python 3.12 to supported and test against its RC on github actions ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 7

- [@aaronkanzer](https://github.com/aaronkanzer)
- [@dependabot[bot]](https://github.com/dependabot[bot])
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Kabilar Gunalan ([@kabilar](https://github.com/kabilar))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.5.0 (Wed Feb 14 2024)

#### 🚀 Enhancement

- Update messaging and root directory for lincbrain logs [#35](https://github.com/lincbrain/linc-cli/pull/35) (aaronkanzer@Aarons-MacBook-Pro.local [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)

---

# 0.4.0 (Mon Feb 12 2024)

#### 🚀 Enhancement

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)

---

# 0.3.0 (Mon Feb 12 2024)

#### 🚀 Enhancement

- Update DANDI_API_KEY to LINCBRAIN_API_KEY [#33](https://github.com/lincbrain/linc-cli/pull/33) (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU [@aaronkanzer](https://github.com/aaronkanzer))

#### 🐛 Bug Fix

- More test fixes for patching in test suite [#32](https://github.com/lincbrain/linc-cli/pull/32) (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU)

#### Authors: 3

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU)

---

# 0.2.3 (Wed Jan 31 2024)

#### 🐛 Bug Fix

- resolve build process with correct files [#31](https://github.com/lincbrain/linc-cli/pull/31) (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU)

---

# 0.2.2 (Wed Jan 31 2024)

#### 🐛 Bug Fix

- Resolve one other test import for CLI integration tests [#30](https://github.com/lincbrain/linc-cli/pull/30) (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 2

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU)

---

# 0.2.1 (Wed Jan 31 2024)

#### 🐛 Bug Fix

- Alter imports for linc-archive <> CLI integration tests [#29](https://github.com/lincbrain/linc-cli/pull/29) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Update readme for instructions, correct links [#28](https://github.com/lincbrain/linc-cli/pull/28) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 3

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU)

---

# 0.2.0 (Tue Jan 30 2024)

#### 🚀 Enhancement

- remove changelog [#27](https://github.com/lincbrain/linc-cli/pull/27) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- naming convention in setup.py [#26](https://github.com/lincbrain/linc-cli/pull/26) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Route to lincbrain-cli for installation [#25](https://github.com/lincbrain/linc-cli/pull/25) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- More trivial change for new git tag [#24](https://github.com/lincbrain/linc-cli/pull/24) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Use lincbrain release equivalent with dandi [#23](https://github.com/lincbrain/linc-cli/pull/23) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Include proper PEP naming [#22](https://github.com/lincbrain/linc-cli/pull/22) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Fix autorc [#21](https://github.com/lincbrain/linc-cli/pull/21) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Revise versioning convention [#20](https://github.com/lincbrain/linc-cli/pull/20) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- use custom script to pep name files to upload [#19](https://github.com/lincbrain/linc-cli/pull/19) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Conform to PEP versioning standards [#18](https://github.com/lincbrain/linc-cli/pull/18) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Add naming suffix to circumvent PyPI historical sem var history [#17](https://github.com/lincbrain/linc-cli/pull/17) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Update main branch for tagging [#16](https://github.com/lincbrain/linc-cli/pull/16) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Trivial change with remote tags cleaned up [#15](https://github.com/lincbrain/linc-cli/pull/15) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Clean changelog for tagging [#14](https://github.com/lincbrain/linc-cli/pull/14) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Include PR from main branch for GHA test [#13](https://github.com/lincbrain/linc-cli/pull/13) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Trivial change -- forgot labels [#12](https://github.com/lincbrain/linc-cli/pull/12) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Try release again with release label [#10](https://github.com/lincbrain/linc-cli/pull/10) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))
- Trivial change to test labels and releases [#9](https://github.com/lincbrain/linc-cli/pull/9) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))

#### 🐛 Bug Fix

- Include permissions for actions bot [#11](https://github.com/lincbrain/linc-cli/pull/11) (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu [@aaronkanzer](https://github.com/aaronkanzer))

#### Authors: 4

- [@aaronkanzer](https://github.com/aaronkanzer)
- Aaron Kanzer (aaronkanzer@Aarons-MacBook-Pro.local)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.mit.edu)
- Aaron Kanzer (aaronkanzer@dhcp-10-29-194-155.dyn.MIT.EDU)

---

