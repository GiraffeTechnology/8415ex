# 8415ex

8415ex is being developed in small, verifiable increments. Wallet integration will use ERC-8415, supporting 8415wallet and compatible wallets.

The current repository contains a dependency-free CI bootstrap. It does not yet contain the exchange application. Python 3.10 or newer is required only for these bootstrap checks; the application stack is not selected here.

Run the checks from the repository root after setting APPROVED_TEST_ROOT to an existing, canonical directory on approved execution storage:

```sh
BOOTSTRAP_TEST_ROOT="$APPROVED_TEST_ROOT" python3 -B -m unittest discover -s ci/tests -v
```

See [the bootstrap guide](ci/README.md) for the smoke command, output manifest and result contract.
