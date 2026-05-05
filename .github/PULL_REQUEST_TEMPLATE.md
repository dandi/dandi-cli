<!--
Thanks for contributing to dandi-cli!

If your change depends on an unmerged PR (or a not-yet-released branch
state) in dandi-archive and/or dandi-schema, add a marker line below
(anywhere in the body) and CI will add an extra run that builds the
dandi-archive Docker image from that ref and/or installs dandischema
from that ref into the test environment.

Accepted forms — pick PR *or* branch per repo, not both:

  dandi-archive PR:     #2784
  dandi-archive PR:     https://github.com/dandi/dandi-archive/pull/2784
  dandi-archive branch: master
  dandi-schema  PR:     #321
  dandi-schema  branch: feature/foo

Branches must live in the dandi/<repo> upstream repository. Forks are
rejected (the workflow `::error::`s out) so a malicious user can't
trick CI into running their code with our workflow secrets.

Remove the marker once the upstream change has shipped in a release.

The same `Cross-repo PR tests` workflow can also be triggered manually
from the Actions tab (`workflow_dispatch`); in that mode you supply
`dandi_{cli,schema,archive}_{pr,branch}` directly. If no schema or
archive override is set the workflow silently skips — running it
without an override would just retest the released stack, which the
regular test matrix already covers.
-->
