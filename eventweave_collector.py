"""Bounded Stellar RPC ingestion. No secrets, signing, or transaction submission."""
import argparse
import json
import ssl
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'checkpoint-store'))
from eventweave_store import Journal


class RetentionGap(RuntimeError):
    pass


def rpc(url, method, params):
    if not url.startswith('https://'):
        raise ValueError('RPC endpoint must use HTTPS')
    request = urllib.request.Request(url, json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
        headers={'Content-Type': 'application/json'})
    # Python.org macOS builds can lack their CA bundle; use the system CA file.
    system_ca = Path('/etc/ssl/cert.pem')
    context = ssl.create_default_context(cafile=str(system_ca)) if sys.platform == 'darwin' and system_ca.exists() else ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        data = json.load(response)
    if 'error' in data:
        raise RuntimeError('RPC error: ' + json.dumps(data['error']))
    return data['result']


def collect(journal, config, request=rpc, page_limit=100, max_pages=100):
    if (type(config['start']) is not int or type(config['end']) is not int or
            not 0 < config['start'] < config['end']):
        raise ValueError('Range must be positive integer ledgers [start,end)')
    if not 1 <= page_limit <= 10000 or max_pages < 1:
        raise ValueError('Invalid page limits')
    health = request(config['endpoint'], 'getHealth', {})
    if config['start'] < health['oldestLedger']:
        raise RetentionGap('Requested start predates RPC retention; checkpoint unchanged')
    if config['end'] > health['latestLedger'] + 1:
        raise ValueError('Requested end has not been closed yet')
    job = journal.open_job(config)
    for _ in range(max_pages):
        state = journal.state(job)
        if state['complete']:
            return journal.replay(job)
        params = {'filters': config.get('filters', []), 'pagination': {'limit': page_limit}}
        if state['cursor']:
            params['pagination']['cursor'] = state['cursor']
        else:
            params.update(startLedger=config['start'], endLedger=config['end'])
        result = request(config['endpoint'], 'getEvents', params)
        # Retention can move during ingestion. Never silently turn a gap into completeness.
        if result.get('oldestLedger', health['oldestLedger']) > config['start']:
            raise RetentionGap('Retention moved past requested start during ingestion')
        if result['latestLedger'] < config['end'] - 1:
            raise ValueError('RPC response is behind the requested range')
        raw = result['events']
        if not isinstance(raw, list) or len(raw) > page_limit:
            raise ValueError('Malformed event page')
        for event in raw:
            if type(event.get('ledger')) is not int or not isinstance(event.get('id'), str):
                raise ValueError('Malformed event record')
        if any(raw[i]['ledger'] > raw[i+1]['ledger'] for i in range(len(raw)-1)):
            raise ValueError('Event page is not ordered by ledger')
        events = [e for e in raw if config['start'] <= e['ledger'] < config['end']]
        complete = len(raw) < page_limit or any(e['ledger'] >= config['end'] for e in raw)
        journal.commit_page(job, state['cursor'], result.get('cursor'), events, complete)
        if complete:
            return journal.replay(job)
    return journal.replay(job)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--endpoint', default='https://soroban-testnet.stellar.org')
    p.add_argument('--start', type=int, required=True)
    p.add_argument('--end', type=int, required=True)
    p.add_argument('--db', default='events.sqlite')
    p.add_argument('--contract')
    p.add_argument('--output', default='manifest.json')
    args = p.parse_args()
    config = {'endpoint': args.endpoint, 'start': args.start, 'end': args.end,
              'filters': [{'type': 'contract', **({'contractIds': [args.contract]} if args.contract else {})}]}
    journal = Journal(args.db)
    try:
        result = collect(journal, config)
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(json.dumps({k:v for k,v in result.items() if k != 'events'}, indent=2))
    finally:
        journal.close()


if __name__ == '__main__':
    main()
