"""Capture actual local workbench pages through an existing browser page.

No browser launch, context creation, credential configuration or wallet signing.
The independent QA host supplies a permitted async Page and approved sink.
"""
from datetime import datetime, timezone
import hashlib
import io
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlencode
import zipfile

NATIVE = ("receipt", "authorization", "timeline", "rollback", "queue", "evidence")
SCENARIOS = tuple("DEMO-"+str(i).zfill(2) for i in range(1,7))
MAX_IMAGE = 8*1024*1024
MAX_TOTAL = 64*1024*1024

def checked_origin(origin):
    p=urlsplit(origin)
    if (p.scheme!="http" or p.username or p.password or p.query or p.fragment
            or p.path not in ("", "/") or not p.hostname
            or not ipaddress.ip_address(p.hostname).is_loopback):
        raise ValueError("explicit loopback workbench origin required")
    if p.port is None:
        raise ValueError("explicit workbench port required")
    return origin.rstrip("/")

def checked_identity(source):
    if not isinstance(source,dict) or any(not isinstance(source.get(k),str)
        or re.fullmatch(r"[0-9a-f]{40}",source[k]) is None for k in ("commit","tree")):
        raise ValueError("full source commit and tree required")
    return {k:source[k] for k in ("commit","tree")}

def same_source(record,source):
    return isinstance(record,dict) and all(record.get(k)==v for k,v in source.items())

async def capture(page, origin, source):
    """Return PNGs and bound raw records in memory after actual browser work.

    Page is the host's existing authorized async browser Page. This function
    does not own or close its browser/context and cannot claim video completion.
    Failures propagate and no complete package is returned on partial capture.
    The host preserves partial browser logs in its original approved evidence.
    """
    origin=checked_origin(origin); source=checked_identity(source)
    started=datetime.now(timezone.utc).isoformat()
    files={}; captures=[]; total=0
    def retain(name,data):
        nonlocal total
        if not isinstance(data,bytes) or len(data)>MAX_IMAGE:
            raise ValueError("bounded byte artifact required")
        total+=len(data)
        if total>MAX_TOTAL:
            raise ValueError("browser material total limit exceeded")
        files[name]=data
    async def snapshot(name,url):
        response=await page.goto(url,wait_until="domcontentloaded")
        if response is None or response.status!=200:
            raise RuntimeError("browser page did not return HTTP200: "+name)
        await page.locator("main, body").first.wait_for(state="visible")
        current=urlsplit(page.url)
        if (current.scheme+"://"+current.netloc)!=origin:
            raise ValueError("browser navigated outside the local workbench")
        png=await page.screenshot(full_page=True,type="png")
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("browser screenshot is not PNG")
        retain("screens/"+name+".png",png)
        captures.append({"entry":name,"url":page.url,"observedUTC":datetime.now(timezone.utc).isoformat(),
                         "HTTP":response.status,"pngSHA256":hashlib.sha256(png).hexdigest()})
    response=await page.request.get(origin+"/api/snapshot")
    if response.status!=200:
        raise ValueError("native snapshot unavailable")
    initial=await response.json()
    if not same_source(initial.get("source"),source):
        raise ValueError("native runtime source differs from requested capture")
    retain("evidence/native-start.json",json.dumps(initial,sort_keys=True,indent=2).encode())
    for name in NATIVE:
        await snapshot("native-"+name,origin+"/"+name)
    records=[]
    for scenario in SCENARIOS:
        await page.goto(origin+"/demo",wait_until="domcontentloaded")
        await page.locator('select[name="scenario"]').select_option(scenario)
        await page.locator('form[action="/simulate"] button[type="submit"]').click()
        await page.wait_for_url(re.compile(re.escape(origin)+r"/run\?id=demo-[0-9a-f]{32}$"))
        from urllib.parse import parse_qs
        run_ids=parse_qs(urlsplit(page.url).query).get("id",[])
        if len(run_ids)!=1:
            raise ValueError("one actual run identity required")
        run_id=run_ids[0]
        response=await page.request.get(origin+"/evidence?"+urlencode({"id":run_id}))
        if response.status!=200:
            raise ValueError("actual run evidence unavailable")
        record=await response.json()
        result=record.get("report",{}).get("scenarios",[])
        if (record.get("runId")!=run_id or record.get("evidenceKind")!="LOCAL_SIMULATION"
                or not same_source(record.get("source"),source) or len(result)!=1
                or result[0].get("scenarioId")!=scenario):
            raise ValueError("browser run/source/scenario binding mismatch")
        if not record.get("realEvidence") or any(v!="NOT_RUN" for v in record["realEvidence"].values()):
            raise ValueError("local capture cannot inherit real execution evidence")
        retain("evidence/"+scenario+".json",json.dumps(record,sort_keys=True,indent=2).encode())
        records.append({"scenario":scenario,"runId":run_id,"path":result[0].get("mainPath"),
                        "recordedCounts":result[0].get("counts"),"recordedError":result[0].get("error")})
        await snapshot(scenario,page.url)
    final_response=await page.request.get(origin+"/api/snapshot")
    if final_response.status!=200:
        raise ValueError("final source observation unavailable")
    final=await final_response.json()
    if not same_source(final.get("source"),source):
        raise ValueError("source changed during browser capture")
    retain("evidence/native-end.json",json.dumps(final,sort_keys=True,indent=2).encode())
    manifest={"schema":"8415ex-native-browser-materials/1","source":source,
              "startedUTC":started,"finishedUTC":datetime.now(timezone.utc).isoformat(),
              "contentKind":"ACTUAL_BROWSER_SCREENSHOTS_OF_LOCAL_SIMULATION",
              "captures":captures,"scenarios":records,
              "files":{k:{"bytes":len(v),"sha256":hashlib.sha256(v).hexdigest()} for k,v in sorted(files.items())},
              "video":"AWAITING_HOST_FINALIZATION" if getattr(page,"video",None) else "NOT_RUN",
              "independentVisualQA":"NOT_RUN","providerSigningChain":"NOT_RUN",
              "deploymentAcceptance":"NOT_RUN","finalProductAcceptance":"NOT_RUN",
              "meaning":"actual capture observations only, no independent acceptance verdict"}
    return {"files":files,"manifest":manifest,"pendingVideo":getattr(page,"video",None)}

def pack_capture(captured):
    """Package completed capture bytes without extraction or storage changes."""
    files=captured["files"]; manifest=captured["manifest"]
    expected={k:{"bytes":len(v),"sha256":hashlib.sha256(v).hexdigest()} for k,v in sorted(files.items())}
    if manifest.get("files")!=expected:
        raise ValueError("captured material manifest mismatch")
    if sum(map(len,files.values()))>MAX_TOTAL:
        raise ValueError("capture byte limit exceeded")
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            if not re.fullmatch(r"(?:screens/[A-Za-z0-9-]+\.png|evidence/[A-Za-z0-9-]+\.json|video/browser-capture\.webm)",name):
                raise ValueError("unexpected captured material path")
            archive.writestr(name,data)
        archive.writestr("manifest.json",json.dumps(manifest,sort_keys=True,indent=2))
    return output.getvalue()

async def finish_video(captured, read_approved_bytes):
    """Collect the existing context's finalized WebM without creating a context.

    The host first closes only its own approved recording context. Its reader
    must verify the path's existing authorized storage mapping before reading.
    This function does not open a path or move a file itself. Container bytes
    and browser-handle provenance do not replace playback/content review.
    """
    import asyncio
    import copy
    handle=captured.get("pendingVideo")
    if handle is None:
        raise ValueError("existing page has no browser recording; video NOT_RUN")
    path=await asyncio.wait_for(handle.path(),timeout=30)
    data=await read_approved_bytes(path,MAX_TOTAL)
    if not isinstance(data,bytes) or not data.startswith(b"\x1aE\xdf\xa3") or len(data)>MAX_TOTAL:
        raise ValueError("bounded finalized browser WebM required")
    result={"files":dict(captured["files"]),"manifest":copy.deepcopy(captured["manifest"])}
    if sum(map(len,result["files"].values()))+len(data)>MAX_TOTAL:
        raise ValueError("combined browser material limit exceeded")
    name="video/browser-capture.webm"
    result["files"][name]=data
    result["manifest"]["files"][name]={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
    result["manifest"]["video"]={"kind":"EXISTING_BROWSER_CONTEXT_RECORDING",
        "path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
        "collectedUTC":datetime.now(timezone.utc).isoformat(),"playbackQA":"NOT_RUN",
        "contentQA":"NOT_RUN","meaning":"collected bytes from the original page video handle, not final acceptance"}
    return result


async def capture_market(page, origin, source):
    """Capture the current read-only catalogue and selectors in all six locales.

    Reuse the host's permitted Page and loopback origin. No simulation form,
    native command, provider refresh or original receipt is needed or invoked.
    A complete market capture is NOT a complete native/demo capture.
    """
    from .nft_detail_page import LOCALES

    origin = checked_origin(origin)
    source = checked_identity(source)
    started = datetime.now(timezone.utc).isoformat()
    files = {}
    captures = []
    total = 0

    def retain(name, data, maximum):
        nonlocal total
        if type(data) is not bytes or not 1 <= len(data) <= maximum:
            raise ValueError("bounded nonempty market capture bytes required")
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError("market browser material total limit exceeded")
        files[name] = data

    def location(url, path, query):
        actual = urlsplit(url)
        if ((actual.scheme + "://" + actual.netloc) != origin
                or actual.path != path or actual.query != query or actual.fragment):
            raise ValueError("market capture navigated away from the selected entry")

    async def health(name):
        response = await page.request.get(origin + "/healthz")
        if response.status != 200:
            raise ValueError("market runtime health observation unavailable")
        location(response.url, "/healthz", "")
        raw = await response.body()
        if type(raw) is not bytes or not 1 <= len(raw) <= 262144:
            raise ValueError("bounded market health bytes required")
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise ValueError("invalid market health observation") from None
        if (type(value) is not dict
                or value.get("schema") != "8415ex-http-health-observation/1"
                or value.get("httpProcess") != "serving"
                or not same_source(value.get("declaredSource"), source)):
            raise ValueError("market runtime source differs from requested capture")
        retain("evidence/" + name + ".json", raw, 262144)

    await health("market-start")
    for locale in LOCALES:
        for entry in ("market", "collateral", "scenarios"):
            path = "/" + entry
            query = urlencode({"lang": locale})
            url = origin + path + "?" + query
            response = await page.goto(url, wait_until="domcontentloaded")
            if response is None or response.status != 200:
                raise RuntimeError("market browser entry unavailable: " + entry)
            location(response.url, path, query)
            location(page.url, path, query)
            await page.locator("main, body").first.wait_for(state="visible")
            png = await page.screenshot(full_page=True, type="png")
            # Recheck after awaiting visibility and capture. A redirect to a
            # different local page is not evidence of the requested selector.
            location(page.url, path, query)
            if type(png) is not bytes or not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("market browser screenshot is not PNG")
            name = "screens/" + entry + "-" + locale + ".png"
            retain(name, png, MAX_IMAGE)
            captures.append({"entry": entry, "locale": locale, "url": page.url,
                "observedUTC": datetime.now(timezone.utc).isoformat(),
                "HTTP": response.status, "path": name,
                "pngSHA256": hashlib.sha256(png).hexdigest()})
    await health("market-end")
    manifest = {"schema": "8415ex-market-browser-materials/1", "source": source,
        "startedUTC": started, "finishedUTC": datetime.now(timezone.utc).isoformat(),
        "contentKind": "ACTUAL_BROWSER_SCREENSHOTS_OF_READ_ONLY_MARKET",
        "captures": captures,
        "files": {key: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for key, data in sorted(files.items())},
        "sourceIdentity": "DECLARED_ONLY",
        "independentVisualQA": "NOT_RUN", "languageRendering": "NOT_VERIFIED",
        "nativeReceiptAndSixDemos": "NOT_RUN", "providerSigningChain": "NOT_RUN",
        "deploymentAcceptance": "NOT_RUN", "finalProductAcceptance": "NOT_RUN",
        "meaning": "Actual market page observations only; not native execution or independent acceptance"}
    return {"files": files, "manifest": manifest}
