# Read-only reverse-hop progress

The original rollback observation now includes a separate hop-progress
projection. It binds the original reverse path, operation keys, transfer
occurrences, result observations and confirmed cursor before presenting public
positions. It does not call the asset controller or change a recovery step.

The public view retains a stable sequence fingerprint, total and confirmed hop
counts, source/destination positions, each hop's status and whether its original
result reference exists. It excludes accounts, raw authority/operation keys and
native result-reference strings. UNKNOWN remains UNKNOWN. A partial return does
not become completed asset recovery, and missing legacy sequence evidence is
displayed as unrecorded progress instead of an invented zero-hop success.

English, Simplified Chinese, Traditional Chinese, French, Spanish and Japanese
labels describe the reverse path and partial progress. No success, replay or
funds-writing control is added. An original report that claims complete while
its hop cursor is incomplete is inconsistent. Domain hop completion still does
not establish native wallet execution, actual settlement or chain acceptance.

Eight synthetic definitions cover partial progress, UNKNOWN, identity exclusion,
path/result substitution, false completion, legacy evidence, six-language
rendering and the native acceptance boundary. They have not been executed for
this source; browser and deployed-service acceptance remain separate.
