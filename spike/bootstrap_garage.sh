#!/bin/sh
# DEC-037 spike: Garage needs a cluster layout and an access key before it serves S3.
# The image has no shell, so the CLI runs through `docker compose exec`.
set -eu
# Git Bash on Windows would rewrite /garage into a host path.
export MSYS_NO_PATHCONV=1

compose="docker compose -f $(dirname "$0")/compose.s3.yaml"
garage="$compose exec -T garage /garage"

node_id=$($garage node id -q | cut -d@ -f1)
$garage layout assign -z dc1 -c 1G "$node_id"
$garage layout apply --version 1
# Throwaway key in Garage's required format (GK + 24 hex, 64-hex secret).
$garage key import --yes -n spike GK000000000000000000000000 \
  0000000000000000000000000000000000000000000000000000000000000000
$garage key allow --create-bucket GK000000000000000000000000
