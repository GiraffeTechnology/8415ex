# Original workbench with one serialized EX access

`compose_serialized_workbench` constructs the existing remint-capable integrated
workbench using a caller-supplied `SerializedExchangeAccess`. The primary receipt
binding and every directory receipt binding are created from that same access.
The factory stamps the original server source metadata on the detail bindings
as well as the primary binding. It does not create another Exchange instance.

The existing gas page, registration controller, reference feed and original
gateway/readers remain caller-supplied objects. Runtime options retain the
original `RuntimeBinding` contract. No wallet, account, signer, provider, tenant,
database, deployment directory or command outcome is selected by this factory.
Construction binds the original loopback socket but does not start serving.

An optional original remint review is rebound to a reader that captures and
detaches both original projections while holding the same EX access lock.
It retains the original review validation, six languages and read-only route.
No additional command, remint qualification or human approval step is added.
The existing host, CSRF, command enquiry and UNKNOWN behavior remain in the
original workbench handlers and gateway.

The host must still route all participating EX writers through the same access.
A retained raw Exchange reference or independently configured external reader
can escape this lock. Matching metadata is not installed-source attestation;
source, provider, actual served bytes and operational outcome need their actual
deployment evidence. This source factory does not start or deploy a production
service, activate an authorization, recover an Exchange, or execute a transaction.

Six synthetic regression definitions cover the shared primary/detail access,
controller preservation, original gas and multilingual review routes, paired
observation versus a writer, and original UNKNOWN command enquiry. They have not
been executed locally and do not inherit earlier source versions' green checks.
