# Local scenario preparation

Run from the exact source root on Linux, with Python 3.10 or newer:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m exchange.stage5
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest exchange.tests.test_stage5 -v
```

Select one scenario with `--scenario DEMO-01` through `DEMO-06`. Select an existing simulated registration path with `--path REG_DIRECT`, `REG_ELECTRONIC` or `REG_INTERMEDIARY`. Default scenario routing cycles through those three fixture paths. It is a test selection, not a product routing policy.

The six scenario contracts cover single-sale exit, independent prefix release, first refusal, protected-prefix refusal, buyer-budget shortfall, and cutoff plus in-flight work. Results retain separate expected state, observed domain/funds/rollback/exit snapshots and intermediate checkpoints. The command returns nonzero for a failed local scenario and emits structured failure details.

All accounts, quote assets, prices, authority facts, payments, registrar results and gas conditions are synthetic. An ordinary wallet balance is not queried. The budget update in the shortfall case is an explicit test-fixture change; it does not top up a wallet. Gas responsibility and principal refunds are separate: an undecided fee conversion/deduction is not fabricated.

Local passing results do not establish deployment, real providers, interactive UI acceptance, signatures, network transactions or real gas deductions. Those evidence slots remain NOT_RUN. Existing source requirements and unresolved decisions continue to apply. Do not edit the shared implementation to force a scenario pass.
