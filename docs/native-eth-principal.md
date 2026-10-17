# Native ETH principal in the original journal bridge

The original bridge accepted only a nonzero token address. The v1.3 successor
also accepts the existing canonical `ETH` price identity when the original escrow
already selects ETH and verified decimals equal 18. No currency is selected or
converted by this bridge. Wrapped ETH, aliases and the zero-address token are not
substitutes. NFT0 membership and signed-order currency admission remain mandatory
in the original mint/trade path.

ETH principal uses integer wei and its original principal freeze. Its immutable
binding includes native asset kind and wei unit. Release/refund consume that
same freeze without a second buyer debit. Gas is separately accounted in ETH wei;
consumed gas is not restored and gas prepayment does not pay principal. Unknown
outcomes return reconciliation-only with no request. Existing ERC-20 binding
terms retain their exact schema and digest behavior.

These are EX internal translation fields, not a new Wallet API, calldata ABI or
claim that an installed native writer accepts this contract. The original native
writer/verifier must authenticate the exact binding and perform atomic revision,
funds, gas, grant and nonce checks. No store, dispatch or financial mutation is
implemented here. A prepared request never marks a leg funded.

Six new synthetic regression definitions are NOT_RUN. The affected original
principal-journal suite must also run on the approved evidence-bound remote Linux
target after installation of this successor; its previous results remain bound to
the prior source. No local test, import, compile or typecheck was executed.
