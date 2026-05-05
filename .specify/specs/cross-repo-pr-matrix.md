# Cross-repo PR matrix testing in dandi-cli CI

## Goal

Allow a dandi-cli PR description to declare it depends on a PR in
`dandi/dandi-schema` and/or `dandi/dandi-archive`. When such a marker is
detected, CI adds a new matrix run that exercises the dandi-cli changes
**against the referenced PR(s)** of those repos, in addition to the regular
matrix (which uses released `dandischema` from PyPI and the prebuilt
`dandiarchive/dandiarchive-api` image from Docker Hub).

Reference pattern: bids-standard/bids-examples
[validate_datasets.yml](https://github.com/bids-standard/bids-examples/blob/master/.github/workflows/validate_datasets.yml#L35).

Immediate target:
- dandi/dandi-cli#1839 (this branch) tested against dandi/dandi-archive#2784.

## Background — what currently happens

`.github/workflows/run-tests.yml` defines a single `test` job with a Python ×
OS × `mode` matrix. Test runs that need a live archive use the
`dandi-api` mode. The archive is brought up in
`dandi/tests/fixtures.py::docker_compose_setup` via
`docker compose` against `dandi/tests/data/dandiarchive-docker/docker-compose.yml`,
which references the prebuilt image:

```yaml
services:
  django:
    image: dandiarchive/dandiarchive-api
  celery:
    image: dandiarchive/dandiarchive-api
```

The image is built by `dandi/dandi-archive` from `dev/django-public.Dockerfile`
(`uv sync --extra development` over the checked-out tree) and pushed to Docker
Hub. `dandischema` is an ordinary PyPI dependency in **both** repos
(`dandi-cli/pyproject.toml`: `dandischema ~= 0.12.0`;
`dandi-archive/pyproject.toml`: `dandischema==0.12.1`). dandi-archive itself
already does the build-image-from-source dance for its own
`cli-integration.yml` workflow — we mirror that here.

## PR-body marker syntax

Two parallel marker forms per repo — pick one, never both. Labels are
matched case-insensitively, whitespace-tolerant.

PR markers (a `#NNN` number or a full URL):

```
dandi-archive PR: #2784
dandi-archive PR: https://github.com/dandi/dandi-archive/pull/2784
dandi-schema  PR: #321
dandi-schema  PR: https://github.com/dandi/dandi-schema/pull/321
dandi-cli     PR: #1839              (rare; see "implicit cli source" below)
```

Branch markers (the branch name in `dandi/<repo>`):

```
dandi-archive branch: master
dandi-archive branch: feature/foo
dandi-schema  branch: maint-0.12
dandi-cli     branch: master
```

Branches use `[\w./-]+`, so `feature/foo`, `maint-0.12.x`, etc. are accepted.
The discover step `gh api repos/dandi/<repo>/branches/<name>`s the branch to
pin to a SHA so the build is reproducible.

**Implicit cli source.** On `pull_request` events, the dandi-cli code under
test defaults to the PR's own head ref (via `actions/checkout`'s default
behaviour). The `dandi-cli` markers above only matter when you want to
deliberately *override* that — e.g. test a dandi-cli PR's archive interaction
against a *different* dandi-cli ref. Most users won't need them.

## Fork rejection (security)

PR resolution returns `head.repo.full_name`. The discover step refuses to
proceed if that's not under `dandi/`:

```
::error::dandi/dandi-archive PR #N: refusing to build from non-dandi repo 'attacker/dandi-archive' — cross-repo overrides must come from the dandi/ org to avoid running untrusted code with workflow secrets.
```

Why: `pull_request` triggered from a fork of dandi-cli already runs in
sandboxed mode (no secrets, read-only `GITHUB_TOKEN`). But `workflow_dispatch`
runs from the dispatched ref *with full secrets*, and a maintainer triggering
a manual run on a fork-PR pointer would otherwise be running attacker code.
Rejecting forks unconditionally — including on `pull_request` — is the
simplest invariant and avoids the
[`pull_request_target` foot-gun](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/).
Branches are inherently safe because we resolve them under `dandi/<repo>` only;
a fork's branch name happens to match an upstream branch is irrelevant.

## Manual `workflow_dispatch` mode

The same workflow is also runnable from the Actions tab with six string
inputs (one PR + one branch per repo, mutually exclusive within a repo):

- `dandi_cli_pr`     / `dandi_cli_branch`
- `dandi_schema_pr`  / `dandi_schema_branch`
- `dandi_archive_pr` / `dandi_archive_branch`

PR inputs accept a number, `#N`, or full GitHub URL. Branch inputs accept
the branch name as it appears in `dandi/<repo>`. If you supply both a PR
and a branch for the same repo, the discover step `::error::`s and
exits.

If neither `dandi_schema_pr` nor `dandi_archive_pr` is supplied (so
there is no override that diverges from the regular test matrix), the
discover job sets `should_run=false` and the downstream `build-archive-image`
/ `test-cross-repo` jobs are silently skipped. A `dandi_cli_pr`-only
dispatch is treated the same way — that combination would just retest
released schema + released archive, which the regular `run-tests.yml`
matrix already covers. There is no PR body in this mode, so the
parsing branch is skipped entirely.

The same skip semantics apply to `pull_request` events with no markers
in the body: the workflow runs `discover-cross-repo-prs` (cheap), sees
no pointers, and short-circuits — so adding this workflow doesn't add
any meaningful CI cost to PRs that don't opt in.

## Workflow changes (`.github/workflows/run-tests.yml`)

### 1. New `discover-cross-repo-prs` job (runs only on `pull_request`)

Outputs:

- `archive_repo` (e.g. `dandi/dandi-archive` or fork)
- `archive_ref`  (head ref / SHA of that PR)
- `schema_repo`
- `schema_ref`
- `extra_matrix` — a JSON list of matrix `include` entries (empty when no
  markers found)

Implementation sketch:

```yaml
discover-cross-repo-prs:
  if: github.event_name == 'pull_request'
  runs-on: ubuntu-latest
  outputs:
    extra_matrix: ${{ steps.build.outputs.extra_matrix }}
    archive_repo: ${{ steps.parse.outputs.archive_repo }}
    archive_ref:  ${{ steps.parse.outputs.archive_ref }}
    schema_repo:  ${{ steps.parse.outputs.schema_repo }}
    schema_ref:   ${{ steps.parse.outputs.schema_ref }}
  steps:
    - name: Parse PR body
      id: parse
      env:
        BODY: ${{ github.event.pull_request.body }}
        GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        printf '%s' "$BODY" > /tmp/pr_body.txt
        # numeric id, with or without URL prefix
        ARCH_PR=$(grep -oiP 'dandi-archive\s+PR:\s*(https://github\.com/dandi/dandi-archive/pulls?/|dandi/dandi-archive#)*\K[0-9]+' /tmp/pr_body.txt | head -1 || true)
        SCHEMA_PR=$(grep -oiP 'dandi-schema\s+PR:\s*(https://github\.com/dandi/dandi-schema/pulls?/|dandi/dandi-schema#)*\K[0-9]+' /tmp/pr_body.txt | head -1 || true)

        resolve() {  # repo, prnum -> "owner/repo<TAB>ref<TAB>sha"
          gh api "repos/$1/pulls/$2" \
            --jq '[.head.repo.full_name, .head.ref, .head.sha] | @tsv'
        }
        if [ -n "$ARCH_PR" ]; then
          IFS=$'\t' read -r REPO REF SHA < <(resolve dandi/dandi-archive "$ARCH_PR")
          echo "archive_repo=$REPO" >> "$GITHUB_OUTPUT"
          echo "archive_ref=$SHA"   >> "$GITHUB_OUTPUT"
        fi
        if [ -n "$SCHEMA_PR" ]; then
          IFS=$'\t' read -r REPO REF SHA < <(resolve dandi/dandi-schema "$SCHEMA_PR")
          echo "schema_repo=$REPO" >> "$GITHUB_OUTPUT"
          echo "schema_ref=$SHA"   >> "$GITHUB_OUTPUT"
        fi

    - name: Build extra matrix entry
      id: build
      run: |
        if [ -n "${{ steps.parse.outputs.archive_repo }}${{ steps.parse.outputs.schema_repo }}" ]; then
          cat <<'EOF' >> "$GITHUB_OUTPUT"
        extra_matrix=[{"os":"ubuntu-latest","python":"3.13","mode":"dandi-api","cross_repo":"true"}]
        EOF
        else
          echo 'extra_matrix=[]' >> "$GITHUB_OUTPUT"
        fi
```

### 2. Pre-build the dandi-archive Docker image (only if archive PR was found)

A second new job, gated on `discover-cross-repo-prs`, checks out the PR head
(possibly from a fork) and builds the image with `dev/django-public.Dockerfile`,
optionally swapping `dandischema` to the schema PR head, then exports it as a
tarball artifact (same trick dandi-archive's own `cli-integration.yml` uses):

```yaml
build-archive-image:
  needs: discover-cross-repo-prs
  if: needs.discover-cross-repo-prs.outputs.archive_repo != ''
  runs-on: ubuntu-24.04
  steps:
    - uses: actions/checkout@v6
      with:
        repository: ${{ needs.discover-cross-repo-prs.outputs.archive_repo }}
        ref:        ${{ needs.discover-cross-repo-prs.outputs.archive_ref }}
        fetch-depth: 0
    - name: Patch pyproject for dandi-schema PR
      if: needs.discover-cross-repo-prs.outputs.schema_repo != ''
      run: |
        # Replace the pinned dandischema with a git URL pointing at the PR head.
        REPO='${{ needs.discover-cross-repo-prs.outputs.schema_repo }}'
        REF='${{ needs.discover-cross-repo-prs.outputs.schema_ref }}'
        python - <<PY
        import re, pathlib
        p = pathlib.Path("pyproject.toml")
        s = p.read_text()
        s = re.sub(
            r'"dandischema[^"]*"',
            f'"dandischema @ git+https://github.com/$REPO@$REF"',
            s,
        )
        p.write_text(s)
        PY
        # uv supports PEP 508 direct refs; rerun lock so uv sync picks it up
        # If a uv.lock is checked in and strict, regenerate:
        uv lock || true
    - name: Build image
      run: docker build -t dandiarchive/dandiarchive-api -f dev/django-public.Dockerfile .
    - name: Export image
      run: docker image save -o dandiarchive-api.tgz dandiarchive/dandiarchive-api
    - uses: actions/upload-artifact@v7
      with:
        name: dandiarchive-api.tgz
        path: dandiarchive-api.tgz
```

### 3. Augment the existing `test` job

- Add a job-level `needs: [discover-cross-repo-prs, build-archive-image]` —
  but only when those jobs ran (use `always() && (needs.X.result == 'success' || needs.X.result == 'skipped')`).
- Append `${{ fromJson(needs.discover-cross-repo-prs.outputs.extra_matrix) }}`
  to `matrix.include` so the cross-repo run is added when markers are present.
- Add new conditional steps controlled by `matrix.cross_repo == 'true'`:

```yaml
- name: Download prebuilt dandi-archive image (cross-repo)
  if: matrix.cross_repo == 'true' && needs.discover-cross-repo-prs.outputs.archive_repo != ''
  uses: actions/download-artifact@v8
  with: { name: dandiarchive-api.tgz }
- name: Load image
  if: matrix.cross_repo == 'true' && needs.discover-cross-repo-prs.outputs.archive_repo != ''
  run: docker image load -i dandiarchive-api.tgz

- name: Install dandi-schema from PR (cross-repo)
  if: matrix.cross_repo == 'true' && needs.discover-cross-repo-prs.outputs.schema_repo != ''
  run: |
    pip install --force-reinstall \
      "dandischema @ git+https://github.com/${{ needs.discover-cross-repo-prs.outputs.schema_repo }}@${{ needs.discover-cross-repo-prs.outputs.schema_ref }}"
```

Set `DANDI_TESTS_PULL_DOCKER_COMPOSE=0` for cross-repo runs so the loaded
image isn't overwritten by `docker compose pull`. (`dandi/tests/fixtures.py`
already honors this env var at line 398.)

The existing matrix entries continue to use the published `dandischema`
wheel and the published `dandiarchive/dandiarchive-api` image, so we get
a clean before/after signal: regular matrix shows compatibility with the
released stack; the new entry validates that the dandi-cli PR works against
the unmerged backend/schema work.

## Override mechanics — why each piece is needed

| Component overridden | Where it lives during tests | Override mechanism |
|---|---|---|
| `dandischema` in the runner's pytest env | dandi-cli venv | `pip install --force-reinstall "dandischema @ git+https://…@<sha>"` after `pip install .[extras,test]` |
| `dandischema` inside the dandi-archive container | `/opt/django/.venv` populated by `uv sync` | rewrite `pyproject.toml` before `docker build` so `uv` resolves the git URL — same result, different toolchain |
| `dandi-archive` itself | the `dandiarchive/dandiarchive-api` image | replace the Docker Hub pull with a locally built image: `docker build -f dev/django-public.Dockerfile -t dandiarchive/dandiarchive-api .` against the PR's checkout, exported via `docker image save` and shared between jobs as an artifact |

The "tag-collision trick" — keeping the same `image: dandiarchive/dandiarchive-api`
name in `docker-compose.yml` and just *loading* a same-named image into the
local Docker daemon before compose runs — means **no edits** to the
compose file are required. Compose will use the locally loaded image
because it already exists by that name and pull is disabled.

## Edge cases / risks

1. **Forks.** PRs from forks send `secrets.GITHUB_TOKEN` as read-only; we
   only need read access to call `gh api` for the resolution step, so this
   works. Pulling code from forks via `actions/checkout` with `repository:`
   does not need a token for public repos.
2. **Untrusted code execution.** Building an image from an unmerged
   dandi-archive PR runs that PR's code in CI. This is identical to the
   exposure dandi-archive's own `cli-integration.yml` already accepts. No
   new secrets are exposed because we use the default `GITHUB_TOKEN` and
   the new job doesn't push images anywhere.
3. **`pull_request_target` is NOT used.** Stick with `pull_request` so PRs
   from forks run against their own code, never against `master` with
   write secrets.
4. **`uv.lock` drift in dandi-archive.** If dandi-archive ever starts
   committing a `uv.lock`, the schema-override patch must regenerate it
   (`uv lock`); otherwise `uv sync` will reject the URL spec. The plan
   above includes `uv lock || true` defensively.
5. **`DJANGO_DANDI_SCHEMA_VERSION`.** The fixture at
   `dandi/tests/fixtures.py:395` injects `DJANGO_DANDI_SCHEMA_VERSION` from
   `dandi.dandi_schema_version`; if the schema PR bumps the version, the
   new dandi-cli pin must be present (or the dandi-cli PR must include the
   bump too). Document this in the PR-marker convention: when overriding
   schema, the dandi-cli PR is responsible for any required pin bumps.
6. **Stale matrix.** If a contributor leaves the marker in the body after
   the upstream PR merges, CI will keep building from the (now-merged)
   branch ref — harmless but wasteful. Mitigation: also accept the marker
   `dandi-archive PR: none` to explicitly disable, and delete markers in
   reviewer checklists.
7. **macOS / Windows runners.** The cross-repo entry runs `ubuntu-latest`
   only — Docker is unavailable on the others, matching today's
   `dandi-api` rows.

## Concrete steps to land this

1. Add `.github/workflows/run-tests.yml` changes per §1–§3 above.
2. Update PR template (`.github/PULL_REQUEST_TEMPLATE.md` if present, else
   create) to mention the optional `dandi-archive PR:` /
   `dandi-schema PR:` markers.
3. Verify locally with `act` or by pushing a dummy PR with the marker.
4. Land 1839's body update so it carries
   `dandi-archive PR: https://github.com/dandi/dandi-archive/pull/2784`,
   confirm the new matrix row goes green (or surfaces real incompatibilities).

## Out of scope

- Triggering a *return* run on dandi-archive/dandi-schema PRs from a
  dandi-cli PR. dandi-archive's `cli-integration.yml` already covers
  release+master; symmetric cross-triggering can be a follow-up.
- Caching the built dandi-archive image across PR pushes (we rebuild each
  run for now; the build is ~minutes, acceptable).
