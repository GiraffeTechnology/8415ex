# Per-leg commitment deadlines on the queue

The existing queue reports when a registrar request's commitment window has passed but does not show its reported cutoff in the row. This stage adds a fourth column to the existing native and integrated queue component. The receipt observation and overdue reports use the same original observation time, with no additional reader or clock call.

A cutoff is displayed only when the original matching leg report supplies a nonnegative integer no later than that observation time. Missing, malformed, future or conflicting values remain “Not reported”. Identical repeated values do not create a second row or a second outcome. An explicitly supplied zero or equality-at-observation cutoff is retained; zero is never a missing-value default.

The existing state and detail columns keep their original meanings and precedence. A reported passed window is not a registrar refusal, effective registration, payment outcome or completed recovery. This stage does not change the overdue calculation or any registration, timing, funds or recovery rule. Unavailable cutoff metadata does not erase the original reported queue state.

The request commitment deadline is separate from the NFT mint registration cutoff and the trade cutoff. Neither mint declaration fields nor the current clock are substituted for a missing request cutoff. Numeric source values remain unchanged; no additional timezone, precision or time-unit claim is invented by this report. Source identifiers, request IDs, transfer IDs and private diagnostic fields are not rendered.

Fixed resources cover the heading, missing-value text and explanatory boundary in all six existing languages. The component continues to work with legacy reports that contain only leg and observation identities. An empty table spans four columns.

Eight regression definitions cover the single original observation, six languages, missing cutoff, malformed/future values, conflicts, explicitly reported zero/equality, private field exclusion and both existing HTTP compositions. Author product tests and browser execution are **NOT_RUN**. Actual Oracle timing, native recovery and full acceptance remain **OPEN**. No deployment or independent native result is claimed.
