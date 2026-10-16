"""What this package reuses, and which interfaces are still unlocated.

Two questions keep being asked of a local candidate: what does it actually
consume, and what is simulated. Answering them from the code rather than from
memory is the point of this module. Every reuse point below is read from the
running package - the domain modules it imports, and the adapters a scenario
records in its own setup - so the list cannot drift from what the code does.

The second half is the part usually missing: the interfaces that are not
located yet. An unlocated interface is not a defect and not a simulated one; it
is work that cannot start until someone says where the real thing is. Each is
tied to the open decision that tracks it, so it is visible as a dependency
rather than as an unexplained gap.

Nothing here is evidence that a real component was exercised. A simulated
adapter is labelled simulated wherever it appears.
"""
import importlib
import importlib.util
import pathlib
import ast
import sys

from . import decisions

#: Domain modules this package reads, with the real attribute names it takes
#: from each. The names are checked against the imported module, and the module
#: list is checked against the package's own import statements, so neither can
#: drift from what the code does without a test failing.
DOMAIN_REUSE = (
    {
        "module": "exchange.ids",
        "uses": ("canonical_json", "digest"),
        "purpose": "one canonical serialisation and one digest, so two runs over "
                   "the same fixtures compare equal",
        "kind": "domain utility",
        "simulated": False,
    },
    {
        "module": "exchange.model",
        "uses": ("REGISTRATION_PATHS", "Asset", "WHOLE_RECEIPT_UNITS",
                 "WarehouseReceipt", "TradeIntent"),
        "purpose": "the three registrar route identifiers, the asset type, the "
                   "whole-receipt unit count and the two records a guarantee "
                   "contract has to build directly, taken from the domain so "
                   "neither the route list nor a record shape can drift from it",
        "kind": "domain contract",
        "simulated": False,
    },
    {
        "module": "exchange.rollback",
        "uses": ("rollback_binding", "SimulatedAssetControl"),
        "purpose": "the rollback binding the domain itself computes, so a contract "
                   "that triggers a deadline rollback builds the authority the "
                   "domain expects rather than a parallel shape, and the simulated "
                   "asset-return role, so the surface report counts its own methods",
        "kind": "domain contract",
        "simulated": False,
    },
    {
        "module": "exchange.errors",
        "uses": ("DomainError",),
        "purpose": "the domain's own error type, so a contract records the code the "
                   "domain raised instead of matching on the text of a message",
        "kind": "domain contract",
        "simulated": False,
    },
    {
        "module": "exchange.ledger",
        "uses": ("Exchange",),
        "purpose": "the domain class itself, so the logical operations of the "
                   "requirements are resolved against the real methods rather "
                   "than against a list of names",
        "kind": "domain contract",
        "simulated": False,
    },
    {
        "module": "exchange.registration",
        "uses": ("RegistrationEvidence", "SimulatedRegistrar", "DirectRegistrar",
                 "ElectronicRegistrar", "IntermediaryRegistrar"),
        "purpose": "the registration evidence record, so a path scenario reports "
                   "what the domain records rather than a parallel shape, and the "
                   "four registrar roles themselves, so the surface report counts "
                   "the methods the domain defines rather than a list of names",
        "kind": "domain contract",
        "simulated": False,
    },
    {
        "module": "exchange.settlement",
        "uses": ("SimulatedPaymentAdapter",),
        "purpose": "the simulated payment role, so the surface report counts the "
                   "methods it really defines, its enquiry surface included",
        "kind": "local fixture",
        "simulated": True,
    },
    {
        "module": "exchange.exit",
        "uses": ("exit_step_key", "SimulatedVoucherDesk"),
        "purpose": "the exit step key and the simulated collection desk, so a "
                   "contract names a step the way the domain does and the surface "
                   "report counts the desk's own methods",
        "kind": "domain contract",
        "simulated": False,
    },
    {
        "module": "exchange.fixtures",
        "uses": ("A", "B", "C", "D", "QUOTE_ASSET", "PRICE_AB", "PRICE_BC",
                 "PRICE_CD", "CHAIN_ID", "CONTRACT", "TOKEN_ID", "ALL_CHECKS",
                 "authorization", "redeem_authorization", "release_authority",
                 "rollback_authority", "confirm", "refuse", "submit_all",
                 "funded_hop", "funded_chain_to_d", "rollback_chain_to_d",
                 "exit_exchange"),
        "purpose": "deterministic counterparties, test prices, a labelled test "
                   "quote asset and the simulated adapter builders, so a run is "
                   "reproducible and obviously local",
        "kind": "local fixture",
        "simulated": True,
    },
)

#: Where this package's own source states its domain imports. Read from the
#: files rather than from a list, so a new import that nobody declared is
#: visible as an undeclared module instead of staying invisible.

#: The adapter roles a scenario runs against. Every one of them is simulated:
#: this package connects to no real registrar, payment provider, asset control
#: or collection desk, and says so wherever a result is reported.
ADAPTER_ROLES = (
    {
        "role": "registrar",
        "simulated": True,
        "standsFor": "a registrar that records a holder change, in three route "
                     "shapes: filed directly, filed through an electronic register, "
                     "and filed through a designated intermediary",
        "realInterface": "not located; see D-08",
    },
    {
        "role": "payment",
        "simulated": True,
        "standsFor": "an adapter that locks, releases and refunds a segment's "
                     "principal and answers an enquiry about an unknown outcome",
        "realInterface": "not located; see D-08",
    },
    {
        "role": "assetControl",
        "simulated": True,
        "standsFor": "control able to return the asset to a boundary account in one "
                     "operation, without walking the intermediate wallets",
        "realInterface": "not located; see D-05",
    },
    {
        "role": "voucherDesk",
        "simulated": True,
        "standsFor": "a desk that issues a voucher, confirms its hand-over and "
                     "records the burn as separate steps with their own instants",
        "realInterface": "not located; see D-07",
    },
    {
        "role": "wallet",
        "simulated": True,
        "standsFor": "a wallet authorization this package reads and checks, with "
                     "account switching, session loss and revocation visible",
        "realInterface": "not located; see D-09",
    },
)

#: Interfaces a real integration needs that this package cannot point at yet.
#: Each names the decision that tracks it, so it reads as a dependency rather
#: than as an unexplained hole.
UNLOCATED_INTERFACES = (
    {"interface": "the authoritative settlement binding for a real release",
     "neededFor": "real per-segment settlement", "trackedBy": "D-08",
     "owner": "engineering, by checking the existing components"},
    {"interface": "real asset-return control and its wallet authorization",
     "neededFor": "a real on-chain rollback", "trackedBy": "D-05",
     "owner": "engineering, by checking the existing contracts and permissions"},
    {"interface": "the real voucher hand-over and burn sequence",
     "neededFor": "a real exit", "trackedBy": "D-07",
     "owner": "the product owner"},
    {"interface": "the verified wallet capability matrix",
     "neededFor": "real execution against an unverified wallet", "trackedBy": "D-09",
     "owner": "engineering, against the real interfaces"},
    {"interface": "the deployment target and its approved configuration",
     "neededFor": "any deployment at all", "trackedBy": "D-08",
     "owner": "the party that owns the approved environment"},
)


def observed_domain_modules():
    """Which declared domain modules load, and whether every name resolves.

    A declared name that does not resolve is reported as unresolved rather than
    silently dropped: it means the domain moved and this map did not.
    """
    observed = []
    for entry in DOMAIN_REUSE:
        name = entry["module"]
        loaded = name in sys.modules
        try:
            module = sys.modules.get(name) or importlib.import_module(name)
            resolved = sorted(use for use in entry["uses"] if hasattr(module, use))
            unresolved = sorted(set(entry["uses"]) - set(resolved))
            error = None
        except ImportError as problem:
            resolved, unresolved, error = [], sorted(entry["uses"]), str(problem)
        observed.append(dict(entry, uses=list(entry["uses"]),
                             loadedBeforeThisCall=loaded,
                             resolvedNames=resolved,
                             unresolvedNames=unresolved,
                             error=error))
    return observed


def source_imports(root="."):
    """The domain imports this package's own source states, read from the files.

    Returns a mapping of module name to what is imported from it, split by
    where the import is: ``modules`` for the shipped modules, ``tests`` for the
    test suite. The split matters because the test suite imports domain modules
    to assert things about them, which is not the package consuming them.
    Python syntax is parsed without executing it. Comments and string literals
    cannot masquerade as imports; aliases and multiline imports are retained.
    """
    found = {"modules": {}, "tests": {}}
    package = pathlib.Path(root) / "scenarios"
    for path in sorted(package.rglob("*.py")):
        where = "tests" if "tests" in path.relative_to(package).parts else "modules"
        parsed = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                module = node.module or ""
                if module == "exchange" or module.startswith("exchange."):
                    found[where].setdefault(module, set()).update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "exchange" or alias.name.startswith("exchange."):
                        found[where].setdefault(alias.name, set())
    return {where: {module: sorted(names) for module, names in sorted(entries.items())}
            for where, entries in found.items()}


#: Surfaces outside this package that depend on it. Their own code is not this
#: package's to declare, so nothing here is hand-maintained: the dependency is
#: read from their source and the names are resolved against the live modules.
CONSUMER_SURFACES = ("integration",)


def _spec(module):
    """Whether a module exists, without importing it.

    A missing parent raises rather than returning None, and a module that is
    not there is the answer this is asked for, so both become None.
    """
    try:
        return importlib.util.find_spec(module)
    except (ImportError, AttributeError, ValueError):
        return None


def _bound_names(tree):
    """The names a module body binds at its top level.

    Only the module body is walked. A name bound inside a function or a class
    is not importable from the module, so counting it would make a missing name
    look present.
    """
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_targets(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            names.update(_targets(node.target))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            names.update(_targets(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    names.update(_targets(item.optional_vars))
    return names


def _targets(node):
    """The plain names an assignment target binds."""
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        bound = set()
        for element in node.elts:
            bound.update(_targets(element))
        return bound
    if isinstance(node, ast.Starred):
        return _targets(node.value)
    return set()


def _reads_star(tree):
    """Whether the module body re-exports an unknown set of names."""
    return any(isinstance(node, ast.ImportFrom)
               and any(alias.name == "*" for alias in node.names)
               for node in tree.body)


def _surface(module):
    """What a module offers, read from its source rather than by importing it.

    Returns the bound top-level names and whether a star import makes that set
    incomplete. An unreadable or absent source is reported as incomplete too,
    so a name is never called missing on the strength of a file that was not
    read.
    """
    spec = _spec(module)
    origin = getattr(spec, "origin", None) if spec is not None else None
    if not origin or not origin.endswith(".py"):
        return set(), True
    try:
        tree = ast.parse(pathlib.Path(origin).read_text(encoding="utf-8"),
                         filename=origin)
    except (OSError, SyntaxError):
        return set(), True
    return _bound_names(tree), _reads_star(tree)


def consumers(root="."):
    """What depends on this package, and on which of its names.

    The declared half of this map answers what this package consumes. This is
    the other direction, and it was missing: another surface imports seven of
    these modules and nothing said so, which is exactly the dependency a rename
    here would break silently.

    A name that does not resolve on the module it is imported from is a finding:
    this package and that surface have drifted apart. Python syntax is parsed
    rather than matched, so a comment or a string literal cannot pose as an
    import.
    """
    base = pathlib.Path(root)
    found = {}
    unreadable = []
    for surface in CONSUMER_SURFACES:
        folder = base / surface
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.py")):
            try:
                parsed = ast.parse(path.read_text(encoding="utf-8"),
                                   filename=str(path))
            except (OSError, SyntaxError) as problem:
                unreadable.append({"path": path.relative_to(base).as_posix(),
                                   "error": "%s: %s" % (type(problem).__name__,
                                                        problem)})
                continue
            where = path.relative_to(base).as_posix()
            for node in ast.walk(parsed):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    module = node.module or ""
                    if module == "scenarios" or module.startswith("scenarios."):
                        entry = found.setdefault(module, {"names": set(),
                                                          "importedBy": set()})
                        entry["names"].update(alias.name for alias in node.names)
                        entry["importedBy"].add(where)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if (alias.name == "scenarios"
                                or alias.name.startswith("scenarios.")):
                            entry = found.setdefault(alias.name,
                                                     {"names": set(),
                                                      "importedBy": set()})
                            entry["importedBy"].add(where)

    depended = []
    unresolved = []
    undecided = []
    for module, entry in sorted(found.items()):
        resolved, missing, unknown, error = [], [], [], None
        # Nothing is imported to answer this. Importing a module that this run
        # had not already loaded would change the set of loaded modules, and
        # the provenance snapshot reports that - correctly - as the source
        # moving during the run. So a module's own source is parsed for the
        # names it binds, which gives the same answer as an import for every
        # name written in the file, and gives it whether or not this run
        # happened to have the module loaded already.
        loaded = sys.modules.get(module)
        exists = loaded is not None or _spec(module) is not None
        if not exists:
            error = "no module named %r" % module
            missing = sorted(entry["names"])
        else:
            offered, incomplete = _surface(module)
            for name in sorted(entry["names"]):
                # A name imported from a package root may be a submodule rather
                # than an attribute, so both count.
                if name in offered:
                    resolved.append(name)
                elif loaded is not None and hasattr(loaded, name):
                    resolved.append(name)
                elif _spec("%s.%s" % (module, name)) is not None:
                    resolved.append(name)
                elif incomplete:
                    # The module's own names could not be read in full, so this
                    # name is neither located nor missing. Calling it either
                    # would be a guess.
                    unknown.append(name)
                else:
                    missing.append(name)
        depended.append({
            "module": module,
            "names": sorted(entry["names"]),
            "importedBy": sorted(entry["importedBy"]),
            "resolvedNames": resolved,
            "unresolvedNames": missing,
            "undecidedNames": unknown,
            "error": error,
        })
        for name in missing:
            unresolved.append("%s.%s" % (module, name))
        for name in unknown:
            undecided.append("%s.%s" % (module, name))

    return {
        "surfaces": list(CONSUMER_SURFACES),
        "dependedOn": depended,
        "moduleCount": len(depended),
        "unreadableFiles": unreadable,
        "unresolvedNames": sorted(unresolved),
        "undecidedNames": sorted(undecided),
        "consistent": not unresolved and not unreadable and not undecided,
        "meaning": ("these are the names another surface would break on if this "
                    "package renamed or removed them"),
    }


def _attribute(imported, declared):
    """Attribute a submodule import to the submodule it names, where declared."""
    attributed = {}
    for module, names in imported.items():
        if module in declared:
            attributed.setdefault(module, set()).update(names)
            continue
        placed = [name for name in names if "%s.%s" % (module, name) in declared]
        for name in placed:
            attributed.setdefault("%s.%s" % (module, name), set())
        if not names or set(names) - set(placed):
            attributed.setdefault(module, set()).update(set(names) - set(placed))
    return {module: sorted(names) for module, names in sorted(attributed.items())}


def declared_coverage(root="."):
    """Whether the declared map accounts for every domain import in the source.

    Three one-sided findings are kept apart. An undeclared module is a real
    gap: a shipped module consumes something this map does not mention. A
    declared module with no import left is stale: the map still claims a
    dependency the code dropped. A module only the test suite imports is
    neither - it is reported on its own, so it is visible without being
    counted as package reuse.
    """
    imported = source_imports(root)
    declared = {entry["module"] for entry in DOMAIN_REUSE}
    shipped = _attribute(imported["modules"], declared)
    tested = _attribute(imported["tests"], declared)
    undeclared = sorted(module for module in shipped if module not in declared)
    unused = sorted(declared - set(shipped))
    test_only = sorted(module for module in tested
                       if module not in declared and module not in shipped)
    declared_names = {entry["module"]: set(entry["uses"]) for entry in DOMAIN_REUSE}
    undeclared_names = {module: sorted(set(names) - declared_names[module])
                        for module, names in shipped.items()
                        if module in declared_names and set(names) - declared_names[module]}
    return {
        "undeclaredNames": undeclared_names,
        "importsFoundInModules": shipped,
        "importsFoundInTests": tested,
        "declaredModules": sorted(declared),
        "undeclaredModules": undeclared,
        "declaredButNotImported": unused,
        "importedOnlyByTests": test_only,
        "complete": not undeclared and not unused and not undeclared_names,
    }


def adapters_recorded_by(scenario_report):
    """The adapter roles the scenarios actually recorded, read from a report.

    Taken from the runs rather than from this module's own list, so a role that
    stopped being exercised stops appearing.
    """
    seen = {}
    for scenario in (scenario_report or {}).get("scenarios", []):
        adapters = scenario.get("setup", {}).get("simulatedAdapters", {})
        for role, label in adapters.items():
            if label is None:
                continue
            seen.setdefault(role, set()).add(label)
    return {role: sorted(labels) for role, labels in sorted(seen.items())}


def build(scenario_report=None, root="."):
    """The reuse map: what is consumed, what is simulated, what is unlocated."""
    recorded = adapters_recorded_by(scenario_report)
    register = {entry["id"]: entry for entry in decisions.OPEN_DECISIONS}
    unlocated = [dict(entry,
                      decision=register.get(entry["trackedBy"], {}).get("undecided"),
                      blocks=register.get(entry["trackedBy"], {}).get("blocks"))
                 for entry in UNLOCATED_INTERFACES]
    domain = observed_domain_modules()
    coverage = declared_coverage(root)
    depending = consumers(root)
    return {
        # The consuming direction is folded into the same verdict rather than
        # added beside it, so the rule that already acts on this map covers it
        # too. A verdict nobody reads is worse than no verdict.
        "complete": coverage["complete"] and depending["consistent"] and all(
            not row["error"] and not row["unresolvedNames"] for row in domain),
        "schema": "8415ex-reuse-map/2",
        "consumers": depending,
        "domainReuse": domain,
        "declaredCoverage": coverage,
        "adapterRoles": [dict(entry) for entry in ADAPTER_ROLES],
        "adaptersRecordedInThisRun": recorded,
        "allAdaptersSimulated": all(entry["simulated"] for entry in ADAPTER_ROLES),
        "unlocatedInterfaces": unlocated,
        "unlocatedCount": len(unlocated),
        "meaning": ("every adapter role is simulated: this package connects to no "
                    "real registrar, payment provider, asset control, collection "
                    "desk or wallet, and an unlocated interface is a dependency "
                    "with an owner rather than a defect"),
    }
