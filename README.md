# 8415ex

8415ex is being developed in small, verifiable increments. Wallet integration will use ERC-8415, supporting 8415wallet and compatible wallets.

The repository contains a dependency-free CI bootstrap and the Stage 1 exchange domain: warehouse-receipt state, the owner/holder dual track, the serial registration contract with three simulated registrar adapters, explicitly paired limit intents, wallet-authorization checks and a read-only status console. Python 3.10 or newer and the standard library are the only requirements; there is no third-party dependency.

Registration adapters are simulated business roles, not real registration institutions. Nothing here sends a transaction, moves value or deploys. See [the Stage 1 guide](exchange/README.md).

Run the checks from the repository root after setting APPROVED_TEST_ROOT to an existing, canonical directory explicitly selected for the tests:

```sh
BOOTSTRAP_TEST_ROOT="$APPROVED_TEST_ROOT" python3 -B -m unittest discover -s ci/tests -v
```

See [the bootstrap guide](ci/README.md) for the smoke command, output manifest and result contract.

Domain checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s exchange/tests -t . -v
```

Local scenario preparation, covering the six scenarios and the three registrar
routes, with every unexecuted real obligation reported as `NOT_RUN`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scenarios/tests -t . -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m scenarios.cli run-all
```

See [the local preparation guide](scenarios/README.md). It performs no
deployment and sends no transaction.
