# Local scenario and inspection commands

The scenario commands use labelled synthetic model inputs. A local result is not deployment, real signatures, chain execution, a browser journey or complete product acceptance. Published requirement metadata retains its historical baseline identity.

```sh
python3 -B -m scenarios.cli run-all
python3 -B -m scenarios.cli scenarios
python3 -B -m scenarios.cli paths
python3 -B -m scenarios.cli guarantees
python3 -B -m scenarios.cli surface
python3 -B -m scenarios.cli matrix
python3 -B -m scenarios.cli manifest
python3 -B -m scenarios.cli handoff
python3 -B -m scenarios.cli validate-config
python3 -B -m scenarios.cli observations
python3 -B -m scenarios.cli evidence-index
python3 -B -m scenarios.cli decisions
python3 -B -m scenarios.cli receipt
python3 -B -m scenarios.cli reuse
python3 -B -m scenarios.cli events
python3 -B -m scenarios.cli stages
python3 -B -m scenarios.cli dossier
python3 -B -m scenarios.cli storyboard
python3 -B -m scenarios.cli operations
python3 -B -m scenarios.cli usage
python3 -B -m scenarios.cli completion
python3 -B -m scenarios.cli sections
python3 -B -m scenarios.cli run-all --execute-suites --root . --json --json-out /tmp/scenario-result.json --text-out /tmp/scenario-result.txt
```

The output paths must be outside the tracked source. Each invocation records its own actual results; errors and incomplete evidence remain visible.

Other runnable product entry points are listed below. Inspect their command-specific arguments before running a server or producing an artifact. These examples name entry points, not already completed executions.

```sh
python3 -B -m ci.smoke
python3 -B -m exchange.catalogue_serve
python3 -B -m exchange.cli
python3 -B -m exchange.demo_materials
python3 -B -m exchange.demo_package
python3 -B -m exchange.demo_ui
python3 -B -m exchange.deployment_readback
python3 -B -m exchange.stage5
python3 -B -m exchange.webui
python3 -B -m exchange.workbench
python3 -B -m scenarios.current_prd
python3 -B -m exchange.cli view
python3 -B -m exchange.cli timeline
python3 -B -m exchange.cli queue
```
