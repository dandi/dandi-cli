#!/bin/bash

#
# This is a demonstration of a typical workflow to prepare and upload
# dataset to dandi archive.
#
# HOWTO:
#  - Provide this script with a folder containing .nwb files, which
#    you would like to upload to DANDI.
#
#  This script will
#   - organize your data
#   - validate it
#   - register a new dandiset in the archive
#   - upload to the archive
#  and to demonstrate full round-trip/possible simple collaborative workflow
#   - redownload it from the archive

#
# By default let's use our local instance
#
set -eu

: "${DANDI_DEVEL:=1}"
: "${DANDI_INSTANCE:=local-docker}"
: "${ORGANIZE_FILE_MODE:=symlink}"  # Mode which will be used by organize
export DANDI_DEVEL

function info() {
    echo
    echo "I: $*"
}

function indent () {
    sed -e 's,^,   ,g'
}

function sneak() {
    if hash tree && hash head ; then
        info "sneak preview of $1:"
        tree "$1" | head -n 10 | indent
    fi
}


TOPPATH=$(mktemp -d --tmpdir dandiset-XXXXXXX)

if [ "$#" != 1 ]; then
    echo "No path was provided, we will use some really lightweight data repo with a single file"
    git clone http://github.com/dandi-datasets/nwb_test_data $TOPPATH/sourcedata
    SRCPATH="$TOPPATH/sourcedata/v2.0.0/test_Subject.nwb"
else
    SRCPATH="$1"
fi
OUTPATH=$TOPPATH/organized

info "Working on $SRCPATH under $OUTPATH"

info "Organizing"
dandi organize -f "$ORGANIZE_FILE_MODE" -d "$OUTPATH" "$SRCPATH"
sneak "$OUTPATH"

info "Now we will work in $OUTPATH"
cd "$OUTPATH"

info "Register a new dandiset"
info "Before that you might need to obtain an API key from the archive"
dandi register -i "$DANDI_INSTANCE" -n "$(basename $SRCPATH)" -D "description"
# TODO: avoid -i if env var is set
info "dandiset.yaml now contains dandiset identifier"

info "Validating dandiset"
dandi validate

info "Uploading to the archive"
# TODO: should pick up identifier from dandiset.yaml,
# TODO: avoid -i if env var is set
dandi upload -i "$DANDI_INSTANCE"

# TODO: with dandi download it is impossible ATM to (re)download into the same dandiset

info "You can use  dandi download  now to download the dandiset"
#info "Downloading from the archive to a new directory"
# Cannot do for a local one yet since no router configured, so even if I know
# top url, would need to know girder id
#dandi download

info "We are done -- you can explore "$OUTPATH" and/or remove it"
