#!/usr/bin/env bash
# Fetches the two Solidity libraries at pinned versions into contracts/lib.
set -euo pipefail
cd "$(dirname "$0")/../contracts"
mkdir -p lib
[ -d lib/forge-std ] || git clone --quiet --depth 1 --branch v1.17.0 https://github.com/foundry-rs/forge-std lib/forge-std
[ -d lib/openzeppelin-contracts ] || git clone --quiet --depth 1 --branch v5.1.0 https://github.com/OpenZeppelin/openzeppelin-contracts lib/openzeppelin-contracts
