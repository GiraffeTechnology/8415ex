# Native component route composition

The combined source candidate now has an explicit application composition class,
IntegratedWorkbenchServer. It subclasses the existing WorkbenchServer and uses
the same binding, source identity, origin and request handler lifecycle.

The host supplies its existing GasConfirmationPage, RegistrationSourceWorkbench,
clock and exact commit/tree. The server does not select a default wallet, signer,
session, Oracle URL, provider, receipt, database or deployment configuration.
Construction does not start serving. This is a source integration increment;
the original application's actual installed composition remains outstanding.

Routes added:

- GET /gas renders the current typed gas quote and existing confirmation form.
- POST /gas/confirm delegates exact scalar fields to the original controller.
  Buyer, action and grant remain trusted server bindings. Existing controller
  CSRF and live quote checks remain required. Confirmation is not dispatch.
- GET /registration-source displays the three existing source choices.
  Its selected receipt must equal the one native workbench receipt.
  Reads delegate to the existing source controller and original journal reader.

The existing workbench pages link to both views. Other existing routes are
delegated unchanged; this increment does not install a gateway, grant authority,
change retired requirement guards or infer real registration from task status.
The existing source view remains read-only, and its unbound authority/funds
labels remain accurate. Gas confirmation returns no proof or wallet result to
the HTTP client. Unknown wallet outcomes must be enquired in the original system.

Validation in this submission is source-byte identity only. No server
construction, import, HTTP request, unit test, wallet callback, deployment,
browser run or chain action was executed. Independent exact-head route/controller
validation, actual session/CSRF installation, served-source binding and complete
v1.2 scenario acceptance remain required. No behavioral test result is claimed.
