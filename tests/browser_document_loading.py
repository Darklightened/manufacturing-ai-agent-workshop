"""Exercise real PDF/CSV loading with delayed and failed local HTTP responses.

The app is operated only through its visible controls. No application globals,
model endpoints, or GPU processes are used. Fault injection is restricted to a
loopback preview; receipts pin the actual served sources and downloaded sessions.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.async_api import Error as PlaywrightError, async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = {
    "measurement_demo": ("BSH-2630", "DR-BSH-2630", "EDU-BSH-001"),
    "measurement_precision_demo": ("BSH-2630-P", "DR-BSH-2630-P", "EDU-BSH-P-001"),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inputs() -> dict:
    paths = [ROOT / "packages/core/core.mjs"]
    for sid in PRODUCTS:
        paths += [ROOT / "scenarios" / sid / name for name in ("scenario.json", "SOP.pdf", "criteria.csv")]
    return {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths}


async def run(args):
    origin = urlparse(args.url)
    if origin.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Delay/404 injection is only allowed against a loopback preview URL")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "seminar.document-loading-regression.v1",
        "status": "running",
        "url": args.url,
        "delaySeconds": args.delay,
        "sourcePinsBefore": inputs(),
        "checks": [],
        "requests": [],
        "servedDocumentPins": [],
        "blockedRequests": [],
        "pageErrors": [],
        "expectedHttpFailures": [],
        "unexpectedHttpFailures": [],
        "routeCancellations": [],
        "modelCalls": 0,
        "scope": "Transport timing, atomic product/document binding and explicit retry; not OCR or model accuracy",
    }
    policy = {"fail_precision_pdf_once": False, "reverse_delay": False}
    pending = set()
    page = None
    source_contracts = {
        sid: json.loads((ROOT / "scenarios" / sid / "scenario.json").read_text())
        for sid in PRODUCTS
    }

    async def route_request(route):
        request = route.request
        parsed = urlparse(request.url)
        path = unquote(parsed.path)
        record = {"path": path, "method": request.method}
        receipt["requests"].append(record)
        if parsed.netloc != origin.netloc or request.method != "GET":
            receipt["blockedRequests"].append(record)
            await route.abort()
            return
        match = re.search(r"(scenarios/(measurement_demo|measurement_precision_demo)/(SOP\.pdf|criteria\.csv))$", path)
        if not match:
            if path.endswith("/app.mjs"):
                response = await route.fetch()
                receipt["servedAppSha256"] = digest(await response.body())
                await route.fulfill(response=response)
            else:
                await route.continue_()
            return
        relative, sid, kind = match.groups()
        token = object()
        pending.add(token)
        try:
            response = await route.fetch()
            body = await response.body()
            assert response.status == 200, f"Real preview document unavailable: {relative}: {response.status}"
            assert digest(body) == receipt["sourcePinsBefore"][relative], f"Served document differs from source: {relative}"
            injected = policy["fail_precision_pdf_once"] and sid == "measurement_precision_demo" and kind == "SOP.pdf"
            if injected:
                policy["fail_precision_pdf_once"] = False
            delay = args.delay
            if policy["reverse_delay"] and sid == "measurement_precision_demo":
                delay += 1.0
            await asyncio.sleep(delay)
            if injected:
                record.update(status=404, injected=True)
                receipt["expectedHttpFailures"].append(relative)
                await route.fulfill(status=404, content_type="text/plain", body="Intentional local regression fixture: missing PDF")
            else:
                record.update(status=response.status, injected=False)
                receipt["servedDocumentPins"].append({"path": relative, "sha256": digest(body)})
                await route.fulfill(response=response, body=body)
        except PlaywrightError as exc:
            # Product changes may legitimately abort the obsolete HTTP request.
            # Every adopted product still has to pass the complete wire/hash check.
            record["cancelled"] = True
            receipt["routeCancellations"].append({"path": path, "error": str(exc)})
        finally:
            pending.discard(token)

    async def settle_routes():
        deadline = time.monotonic() + 20
        while pending:
            assert time.monotonic() < deadline, "Delayed routes did not finish"
            await asyncio.sleep(0.05)

    async def busy(target, previous=None):
        await expect(page.locator("#document-load-status")).to_be_visible(timeout=3000)
        await expect(page.locator("#main")).to_have_attribute("aria-busy", "true")
        # On the first selection the home screen remains visible; on later
        # selections the previous complete document view is retained but locked.
        for selector in ["#compile", "#next-setup", "#upload-pdf", "#csv-editor"]:
            if await page.locator(selector).count():
                await expect(page.locator(selector)).to_be_disabled()
        if previous:
            assert await page.locator(".measurement-identity strong span").first.inner_text() == PRODUCTS[previous][0]
        else:
            assert not await page.locator("#next-setup").count()
        receipt["checks"].append({"check": "no_partial_compile_during_load", "target": target, "retained": previous})

    async def ready(sid):
        await expect(page.locator("#document-load-status")).to_be_hidden(timeout=20000)
        await expect(page.locator("#compile")).to_be_enabled(timeout=20000)
        await expect(page.locator(".measurement-identity strong span").first).to_have_text(PRODUCTS[sid][0])
        await expect(page.locator(".inspection-drawing")).to_have_attribute("src", f"scenarios/{sid}/drawing.svg")
        actual_csv = await page.locator("#csv-editor").input_value()
        expected_csv = (ROOT / "scenarios" / sid / "criteria.csv").read_text()
        assert actual_csv.replace("\r\n", "\n") == expected_csv.replace("\r\n", "\n"), "CSV is not from the selected product"

    async def export_session(name):
        async with page.expect_download() as event:
            await page.locator("#backup").click()
        download = await event.value
        dest = out / f"{name}.json"
        await download.save_as(str(dest))
        return json.loads(dest.read_text())

    async def compile_and_verify(sid, name):
        await ready(sid)
        await page.locator("#compile").click()
        await expect(page.locator("#next-setup")).to_be_visible(timeout=30000)
        text = await page.locator("#pdf-text").text_content()
        for key, expected in zip(("product_id", "drawing_id", "specimen_id"), PRODUCTS[sid]):
            assert re.search(rf"{key}:\s*{re.escape(expected)}(?=\s|$)", text), f"PDF product identity mismatch: {key}"
        await page.locator("#next-setup").click()
        await page.locator("#start-session").click()
        await expect(page.locator("#advance")).to_be_visible(timeout=15000)
        data = await export_session(name)
        assert data["scenarioId"] == sid
        session = data["session"]
        inspection = session["bundle"]["inspection"]
        assert tuple(inspection[key] for key in ("productId", "drawingId", "specimenId")) == PRODUCTS[sid]
        assert session["bundle"]["criteria"] == source_contracts[sid]["criteria"]
        assert inspection["features"] == source_contracts[sid]["inspection"]["features"]
        assert not session["assessments"]
        assert session["position"] == -1
        receipt["checks"].append({"check": "real_pdf_compile_and_exported_bundle", "scenario": sid, "export": dest_name(name), "productId": inspection["productId"]})
        return data

    def dest_name(name):
        return f"{name}.json"

    async def open_product_selector():
        await page.locator('[data-page="documents"]').click()
        await expect(page.locator(".product-options")).to_be_visible()

    async def select_product(sid, previous):
        await page.locator(f'[data-product-scenario="{sid}"]').click()
        await busy(sid, previous)
        await ready(sid)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = await browser.new_context(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
        await context.route("**/*", route_request)
        page = await context.new_page()
        page.on("pageerror", lambda error: receipt["pageErrors"].append(str(error)))
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        def response_status(response):
            if response.status >= 400 and not (response.status == 404 and response.url.endswith("scenarios/measurement_precision_demo/SOP.pdf")):
                receipt["unexpectedHttpFailures"].append({"url": response.url, "status": response.status})
        page.on("response", response_status)
        try:
            await page.goto(args.url, wait_until="networkidle")
            await page.locator('[data-select="measurement_demo"]').click()
            await busy("measurement_demo")
            await compile_and_verify("measurement_demo", "01-fresh-standard")

            await open_product_selector()
            await select_product("measurement_precision_demo", "measurement_demo")
            await compile_and_verify("measurement_precision_demo", "02-precision")

            await open_product_selector()
            await select_product("measurement_demo", "measurement_precision_demo")
            await compile_and_verify("measurement_demo", "03-return-standard")

            # Overlap target loads. The late precision response cannot replace
            # the most recently requested standard product or its document pair.
            await open_product_selector()
            policy["reverse_delay"] = True
            await page.locator('[data-product-scenario="measurement_precision_demo"]').click()
            await busy("measurement_precision_demo", "measurement_demo")
            await page.locator('[data-product-scenario="measurement_demo"]').click()
            await ready("measurement_demo")
            await settle_routes()
            await ready("measurement_demo")
            policy["reverse_delay"] = False
            await compile_and_verify("measurement_demo", "04-latest-selection-wins")
            receipt["checks"].append({"check": "late_response_cannot_replace_latest_selection", "scenario": "measurement_demo"})

            # A failed target document must retain the prior, complete session.
            await open_product_selector()
            before = await export_session("05-before-404")
            prior_csv = await page.locator("#csv-editor").input_value()
            prior_pdf = await page.locator("#pdf-text").text_content()
            policy["fail_precision_pdf_once"] = True
            await page.locator('[data-product-scenario="measurement_precision_demo"]').click()
            await busy("measurement_precision_demo", "measurement_demo")
            await expect(page.locator("#document-load-status")).to_be_hidden(timeout=20000)
            await expect(page.locator("#toast")).to_contain_text("404", timeout=3000)
            assert await page.locator(".measurement-identity strong span").first.inner_text() == PRODUCTS["measurement_demo"][0]
            assert await page.locator("#csv-editor").input_value() == prior_csv
            assert await page.locator("#pdf-text").text_content() == prior_pdf
            assert await export_session("06-after-404") == before
            assert len(receipt["expectedHttpFailures"]) == 1
            receipt["checks"].append({"check": "missing_pdf_does_not_partially_replace_prior_product_or_session", "httpStatus": 404})

            await select_product("measurement_precision_demo", "measurement_demo")
            await compile_and_verify("measurement_precision_demo", "07-explicit-retry")
            receipt["checks"].append({"check": "explicit_product_retry_recovers_after_404"})
            await settle_routes()
            assert not receipt["blockedRequests"], receipt["blockedRequests"]
            assert not receipt["pageErrors"], receipt["pageErrors"]
            assert not receipt["unexpectedHttpFailures"], receipt["unexpectedHttpFailures"]
            assert not any("/recordings/" in r["path"] for r in receipt["requests"])
            receipt["sourcePinsAfter"] = inputs()
            assert receipt["sourcePinsAfter"] == receipt["sourcePinsBefore"], "Source contract changed during regression"
            receipt["status"] = "passed"
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["failure"] = {"type": type(exc).__name__, "message": str(exc)}
            receipt["sourcePinsAfter"] = inputs()
            try:
                await page.screenshot(path=str(out / "failure.png"), full_page=True)
                receipt["visibleTextAtFailure"] = (await page.locator("#main").inner_text())[:7000]
            except Exception:
                pass
        finally:
            await context.close()
            await browser.close()
    (out / "DOCUMENT_LOADING_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "checks": len(receipt["checks"]), "receipt": str(out / "DOCUMENT_LOADING_RECEIPT.json"), "failure": receipt.get("failure")}, ensure_ascii=False))
    return receipt["status"] == "passed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--browser")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    arguments = parser.parse_args()
    if not 0.5 <= arguments.delay <= 5:
        parser.error("--delay must be between 0.5 and 5 seconds")
    raise SystemExit(0 if asyncio.run(run(arguments)) else 1)
