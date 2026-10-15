# Local simulation console

This console executes the existing six fixed scenarios through
`scenarios.demos` and `scenarios.harness`. It does not implement another
state machine or change the producer scenarios. All registry, payment,
asset-control and voucher roles are synthetic. No institutional cooperation
is implied. It sends no transaction and never obtains wallet credentials.

## Run on approved Linux

Use the existing reviewed source checkout and approved output/storage route.
No dependency installation is needed (Python standard library only).

```sh
python3 -B -m exchange.demo_ui --port 8415 --commit "$(git rev-parse HEAD)" --tree "$(git rev-parse HEAD^{tree})"
```

Open the loopback URL printed by the process in a browser that can reach the
same host. This command does not create a tunnel, public listener, service,
credentials or deployment. A remote browser route must already be approved;
do not widen binding or network permissions to make it reachable.

The page lists the six existing scenarios and their selected registrar paths.
Select one and press **Run simulation**. A fresh synthetic domain run executes;
its expected/observed checks, setup, prices, gas conditions and observations
are retained under a unique run ID. Follow **Next observation** and
**Previous observation** to inspect that recorded run. Navigation does not
perform more domain actions. The JSON link returns the identical stored report.

Results remain in RAM, up to 16 runs. Older runs expire; an expired run returns
404 and does not run again. Stopping the process discards all results.
This is not durable recovery. Preserve required evidence via the existing
approved archive process; this service writes no evidence file.

The supplied commit/tree are declared labels, validated as full identities.
An independent execution receipt must bind them to actual source bytes.
When omitted they read UNVERIFIED. No chain ID, real token address, transaction
hash, signature or deployed identity is fabricated.

## Focused verification

```sh
python3 -B -m unittest integration.test_demo_ui -v
```

Tests exercise real loopback HTTP requests and the existing scenario runner:
six scenario runs and step navigation, equality of JSON and stored records,
origin/host/token refusal, invalid inputs, failed checks preserved rather than
reported as passed, escaped HTML, bounded history and loopback binding.
They are synthetic HTTP integration checks, not a real browser, real provider,
public-chain or production acceptance certificate.

## Stop and rollback

Stop this console with Ctrl-C; the server closes its listener. No service or
persistent state was installed, and no credentials or provider settings changed.
To compare an earlier candidate, stop the console and use the separately reviewed
source version; never replace another task's checkout or reset dirty work.

## Remaining live work

Real provider UI/signing, persistent process recovery, approved deployment,
Sepolia and the designated test token remain separately NOT_RUN. Existing
authority/journal/provider bindings and the unresolved business decisions
continue to gate only their actual dependent paths.
