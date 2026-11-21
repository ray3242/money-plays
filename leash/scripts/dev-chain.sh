#!/usr/bin/env bash
# Local playground: starts Anvil, deploys a mock tUSD8 + PayeeRegistry + Leash,
# and prints the URL to open with `npm run dev`. Ctrl-C stops the chain.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8545}
RPC=http://127.0.0.1:$PORT
KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
anvil --port "$PORT" --block-time 1 >/dev/null 2>&1 &
ANVIL=$!
trap 'kill $ANVIL 2>/dev/null || true' EXIT
until cast chain-id -r $RPC >/dev/null 2>&1; do sleep 0.2; done
deploy() { (cd contracts && forge create -r $RPC --private-key $KEY --broadcast "$@" | awk '/Deployed to/ {print $3}'); }
TOKEN=$(deploy test/Leash.t.sol:MockUSD)
REGISTRY=$(deploy src/PayeeRegistry.sol:PayeeRegistry)
LEASH=$(deploy src/Leash.sol:Leash --constructor-args "$TOKEN" "$REGISTRY")
echo "Open: http://localhost:5173/?rpc=$RPC&leash=$LEASH&registry=$REGISTRY&token=$TOKEN"
wait $ANVIL
