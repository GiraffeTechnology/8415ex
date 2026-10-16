"""Local Stage 5 preparation: deterministic scenario runners and evidence tools.

Everything in this package is local. It drives the existing `exchange` domain
APIs with labelled synthetic fixtures and records what they actually did. It
performs no deployment, sends no transaction, moves no value, and holds no
credential.

It does not modify the domain implementation. A scenario that disagrees with the
implementation records a genuine failure; it never relaxes an assertion to go
green, and it never invents an ordering the requirements leave open.
"""
