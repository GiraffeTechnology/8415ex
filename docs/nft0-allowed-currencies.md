# Immutable NFT0 allowed currencies

Internal EX model fields map the existing NFT0/schema through the mandatory original mint verifier. No NFT0 ABI is invented. A receipt declares a nonempty immutable tuple of one or more currency identities and its original currency-set reference. Each signed order explicitly names one member and binds that reference. The original minted declaration and saved tuple/reference must still agree; mutation or missing data refuses the affected order. There is no automatic selection, conversion or aggregation of balances.

The existing PriorityBook stays keyed by receipt and selected currency. Price/FIFO comparisons never cross currency books. Each principal balance/freeze/release/refund remains tied to its order currency, and ETH gas stays independent. Ordinary continuous transfers add no holder=owner, closed-gap or current-finality gate. Holder remint is a separate v1.3 operation; it does not permit in-place currency mutation.

Eight regression methods are authored NOT_RUN. They use explicitly synthetic data and never prove native wallet, Oracle, chain or UI acceptance. Source follows complete private PRD v1.3 SHA256 1caec8509622c9d1af4db34e9e7a68b6feaa341a4c0690ad44d6d4abd0321a6f, cases T57/T58/T60/T62/T68. Real original schema/currency identity/unit verification and native atomic funds rechecks remain required.
