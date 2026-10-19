# Isolate recorded history from mutable reader objects

The receipt timeline previously returned a tuple containing its internal event
dictionaries. The tuple protected membership only; readers could still alter
event kind, sequence and nested detail. Recording also retained the caller's
detail dictionary, allowing a later caller mutation to rewrite history.

Capture detached detail when recording and return detached event dictionaries
when reading. Event ordering and domain transitions are unchanged. This prevents
accidental mutation through these two object references; it is not cryptographic
authentication, durable persistence or a replacement for the original journal.

Three regression definitions cover nested reader mutation, mutation of the
original input after recording, and stable earlier reads as events are appended.
They use explicit synthetic domain fixtures and remain NOT_RUN until approved
remote Linux QA. They establish no financial, registration or chain acceptance.
