# Separate recorded trade execution on the timeline

The existing timeline previously displayed registration, funding and recovery but omitted the trade execution observation and its recorded time. This stage adds those two columns to the same native and integrated route. It reuses the same original receipt observation and does not introduce a second state source or event journal.

The current original domain contract records trade execution as `executed`. The projection therefore exposes only that exact value as an execution recorded in the domain. Every other value, including absent, future, native-looking success and submitted/pending values, remains unknown. Registration confirmation, funds release or a current owner position cannot supply the missing execution state.

The existing `executedAt` field remains an exact nonnegative integer from the original observation, or unknown. The UI calls it a recorded execution time, not a transaction block timestamp, authoritative registration effective time or finality. It does not substitute the current clock or mint cutoff for a missing execution time. An existing timestamp alongside an unknown execution state is still a separate recorded field, not an inference of success.

Fixed six-language resources keep trade recording, registration, funding and native transaction completion distinct. Existing predecessor positions, withdrawn branches and the parent stage's two mint-cutoff views remain visible. Empty timelines have ten labeled column headers and one explicit empty row. Unknown raw execution text, parties and private identifiers are never embedded in HTML.

This is a feature stage on the original mint-cutoff timeline branch. The parent must be reviewed and its actual fixes reconciled before retargeting this branch to main and validating the exact combined source.

Eight regression definitions cover the closed state mapping, invalid time, independent execution/registration/funding, unchanged source history, six-language privacy, ambiguous future states, empty histories and both existing HTTP compositions. Author product tests and browser execution are **NOT_RUN**. Domain recording alone does not prove a successful native transaction, receipt, payment, registration or full acceptance. No new execution, recovery, signing or deployment is performed.
