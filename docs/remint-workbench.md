# One original remint workbench

`RemintWorkbenchServer` composes the original history and receipt workbench servers into one existing HTTP instance. Cooperative initialization retains one original application binding, clock, gas controller, registration controller, terms-review binding, source identity and listener. The original history and receipt handlers delegate their independent routes through one handler hierarchy.

The host may provide either or both read bindings. Their absence or read failure affects only the corresponding view; there is no all-reader-ready execution requirement. When both are supplied, their existing private application contexts must identify the same original contract and stable bill. This is display identity consistency, not an execution, cleanup or financial gate. No source query occurs during construction.

Both six-language views share navigation with the original gas, registration and complete-terms review. History selection remains in its own language links. The result remains bound to its original receipt and operation context. Each GET calls only its own original read path; neither page reads or dispatches a remint POST. The original route-specific privacy, status and exact ETH rules remain intact.

The integration retains the exact original PR213 history and PR214 snapshot files while combining their fixed translation classification with PR216. Those retained files are not new implementations or inherited validation. This stage adds the single-server composition and eight synthetic approved-Linux HTTP definitions covering localization, route dispatch, source isolation, optional/failing readers, POST, original flows and mismatched display scopes.

Author execution is NOT_RUN. Original block/ABI and receipt reader authentication, actual source configuration, current-source validation, browser and native-chain acceptance remain outstanding. No endpoint, provider, credential, account, journal, runtime service or deployment parameter is selected by this source stage.
