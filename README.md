# EventWeave — Stellar RPC collector

Owns bounded ledger ingestion, pagination, retention diagnostics and resume behavior.

Developer preview: bounded, replayable event ingestion for Stellar application teams. Python 3.11+ and SQLite from the standard library; the optional live pilot also uses curl.

## Repository layout
Check out `checkpoint-store`, `collector`, `replay-console` and `fault-scenarios` as siblings. This repository's entry point is `eventweave_collector.py`. Components are deliberately separate by operational responsibility; they share one journal/manifest contract.

## Run and verify
From the parent workspace:

```sh
python3 -m unittest discover -s fault-scenarios -v
python3 collector/eventweave_collector.py --start START --end END --db events.sqlite --output manifest.json
python3 replay-console/server.py --manifest manifest.json --port 4790
```

Then visit http://127.0.0.1:4790 and load the local manifest. START is inclusive; END is exclusive. Use closed ledgers within the RPC retention window. The default endpoint is Stellar testnet.

For a read-only live pilot:

```sh
python3 fault-scenarios/testnet_probe.py testnet-manifest.json
```

The pilot ingests a recent 21-ledger window and verifies repeat replay hashes. It does not deploy a contract or generate transactions. Public network activity may be zero in a chosen window.

## Guarantees and limits
A page and checkpoint commit atomically in SQLite with WAL and synchronous FULL. Event IDs deduplicate per ingestion job; conflicting payloads fail the entire page. Stale collectors cannot overwrite a checkpoint. Replay sorts by ledger and ID. An unfinished scan is explicitly incomplete.

`rpc-range-exhausted` means the source RPC reported exhaustion for the configured range and filters. It is not an independent or cryptographic proof of complete chain history. RPC retention gaps stop ingestion. Coverage is not inferred from the presence of events. A missing event is not proof that a contract emitted nothing.

The local database is a single-node prototype. Backups, multi-host coordination, authenticated RPC endpoints, automatic gap backfills, XDR decoding and arbitrary business projections are outside this release. The console displays counts and hashes; it does not execute event contents.

## Contribute
Provide a minimal failure case, expected outcome and acceptance test. Report genuine defects; do not create activity-only issues. Issues close only when the implementation and relevant tests pass. See CONTRIBUTING.md.

## Protocol reference
https://developers.stellar.org/docs/data/apis/rpc/api-reference/methods/getEvents
