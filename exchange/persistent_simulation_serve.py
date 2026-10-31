"""Serve the existing local simulation with explicit private history storage."""
import argparse
import hashlib
from pathlib import Path

from exchange.cli import scenario
from exchange.eia_reference_serve import CONFIG_LIMIT, load_eia_reference_config
from exchange.eia_wti_spot_reader import EIAWTISpotReader
from exchange.persistent_simulation import SQLiteSimulationHistory, PersistentSimulationWorkbench
from exchange.reference_feed import CommodityReferenceFeed
from exchange.views import REGISTRATION_PATHS
from exchange.workbench import RuntimeBinding
from exchange.simulation_origin import canonical_public_origin


def configured_reference(path, expected_sha256, *, resume_path=None, resume_sha256=None):
    if path is None and expected_sha256 is None:
        if resume_path is not None or resume_sha256 is not None:
            raise ValueError('reference continuation requires its original source configuration')
        return None
    import re
    if path is None or type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('explicit existing reference file and digest required')
    with open(path, 'rb') as stream:
        raw = stream.read(CONFIG_LIMIT + 1)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('reference configuration identity differs')
    config = load_eia_reference_config(raw)
    policy = config['policy']
    reader = EIAWTISpotReader(**config['reader'])
    feed = CommodityReferenceFeed(policy, reader, lambda candidate: candidate == policy,
                                  observe_transport=reader.transport_observation)
    if resume_path is not None or resume_sha256 is not None:
        from exchange.reference_continuation import resume_eia_reference, LIMIT
        if resume_path is None or type(resume_sha256) is not str:
            raise ValueError("explicit original continuation file and digest required")
        with open(resume_path, "rb") as stream:
            resume_raw = stream.read(LIMIT + 1)
        resume_eia_reference(feed, reader, policy, resume_raw, resume_sha256)
    return feed


def create_simulation_server(*, state_path, port, commit, tree, registration_path,
                             reference_feed=None, public_origin=None):
    public_origin = canonical_public_origin(public_origin)
    if registration_path not in REGISTRATION_PATHS:
        raise ValueError('existing registration scenario required')
    # This is the original explicit local business fixture, not a native
    # registration or Wallet login. The unchanged gateway remains unconfigured.
    exchange, _, _, _ = scenario(registration_path)
    binding = RuntimeBinding(exchange, 'rcpt-8415-0001',
        ('auth-sell-ab', 'auth-buy-ab'),
        {'runId': 'native-local-fixture', 'scenario': 'read-only fixture'})
    history = SQLiteSimulationHistory(state_path)
    try:
        return PersistentSimulationWorkbench(binding, history=history, port=port,
                    commit=commit, tree=tree, reference_feed=reference_feed,
                    public_origin=public_origin)
    except BaseException:
        history.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, help='explicit private SQLite simulation-history file')
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--tree', required=True)
    parser.add_argument('--registration-path', choices=REGISTRATION_PATHS, default='REG_DIRECT')
    parser.add_argument('--reference-config')
    parser.add_argument('--reference-config-sha256')
    parser.add_argument('--reference-resume')
    parser.add_argument('--reference-resume-sha256')
    parser.add_argument('--public-origin', help='explicit canonical HTTPS origin; loopback listener unchanged')
    args = parser.parse_args(argv)
    feed = configured_reference(args.reference_config, args.reference_config_sha256,
                                resume_path=args.reference_resume, resume_sha256=args.reference_resume_sha256)
    server = None
    try:
        server = create_simulation_server(state_path=Path(args.state), port=args.port,
            commit=args.commit, tree=args.tree, registration_path=args.registration_path,
            reference_feed=feed, public_origin=args.public_origin)
        print(server.origin + '/receipt - LOCAL_SIMULATION, durable scenario history; native gateway NOT_CONFIGURED', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            try:
                server.server_close()
            finally:
                server.history.close()
        elif feed is not None:
            feed.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
