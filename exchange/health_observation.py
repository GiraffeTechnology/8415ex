"""HTTP process observation without probing adapters or attesting readiness."""
import re


def health_observation(source, *, gateway_configured, reference_feed_configured,
                       gas_page_configured, registration_sources_configured):
    if type(source) is not dict:
        raise ValueError("original server source declaration required")
    configured = {
        "commandGateway": gateway_configured,
        "referenceFeed": reference_feed_configured,
        "gasPage": gas_page_configured,
        "registrationSources": registration_sources_configured,
    }
    if any(type(value) is not bool for value in configured.values()):
        raise ValueError("explicit component presence required")
    declared = {}
    for key in ("commit", "tree"):
        value = source.get(key)
        declared[key] = value if (type(value) is str
            and re.fullmatch(r"[0-9a-f]{40}", value) is not None) else None
    return {
        "schema": "8415ex-http-health-observation/1",
        "httpProcess": "serving",
        "declaredSource": declared,
        "sourceIdentity": ("DECLARED_ONLY" if all(declared.values())
                           else "UNVERIFIED"),
        "configuredComponents": configured,
        "operationsREADY": "NOT_VERIFIED",
        "providerExecution": "NOT_EVALUATED",
        "chainAcceptance": "NOT_EVALUATED",
        "persistentRecovery": "NOT_EVALUATED",
        "meaning": ("HTTP handler response and supplied component presence only; "
                    "independent artifact, served-version, provider and business "
                    "evidence are required for deployment acceptance"),
    }
