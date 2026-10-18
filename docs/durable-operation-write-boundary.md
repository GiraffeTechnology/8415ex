# Recheck SQLite durability before operation writes

The EX journal accepts an explicitly supplied, caller-owned SQLite connection.
Checking synchronous mode only during journal construction leaves later claims
and reconciliation vulnerable to an intervening connection setting change.

Claim and reconciliation now check FULL or EXTRA again immediately before
starting their write transaction. Refusal happens before advancing the receipt
revision, persisting a claim, invoking an execution gateway or verifying a
terminal proof. The journal does not change the connection's settings itself.

Read-only lookup and original-operation enquiry remain available when writes
are refused. An existing UNKNOWN operation is preserved for reconciliation;
this change grants no retry, refund, unfreeze or replacement operation.

Three additional regression definitions cover a post-construction downgrade,
a downgrade during the original enquiry, and refused reconciliation with
continued read-only recovery. They are NOT_RUN until the established QA owner
executes them on an approved provider-verified remote Linux server. The affected
journal suite and its remint composition callers require version-bound review.
Previous 76 Python and 25 EVM results remain evidence for their unchanged inputs;
they are not results for this successor journal revision.

This local storage guard does not implement native financial writing, the
Oracle atomic read-and-act gate, full exchange restart reconstruction or live
Sepolia and UI acceptance.
