# Meridian production change policy

The change gateway enforces these preconditions. A change that skips one is refused.

## Change policy for purge_wal (deleting retained WAL)

Before purge_wal: snapshot(node) of the same node. Deleting retained WAL without a storage snapshot
is refused, because a paused CDC consumer may still need those segments.

## Change policy for sync_clock (stepping a node clock)

Before sync_clock: cordon(node) the node first. Stepping the clock of a node that still serves
traffic can let in-flight transactions read stale data.

## Change policy for rollback (reverting a release)

A rollback is only appropriate when the evidence points at the release itself (crash loops or errors
that start with the deploy), not merely because a deploy happened recently. No precondition.
