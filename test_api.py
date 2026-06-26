import requests
import json
import os

# Allow overriding the test server base URL via env var `API_BASE`.
BASE = os.getenv("API_BASE", "http://localhost:8000")
pass_count = 0
fail_count = 0
results_log = []

def test(name, fn):
    global pass_count, fail_count
    try:
        result = fn()
        print(f"[PASS] {name}: {result}")
        results_log.append(("PASS", name, result))
        pass_count += 1
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        results_log.append(("FAIL", name, str(e)))
        fail_count += 1
    except Exception as e:
        print(f"[ERROR] {name}: {type(e).__name__}: {e}")
        results_log.append(("ERROR", name, f"{type(e).__name__}: {e}"))
        fail_count += 1


# ---------------------------------------------------------------------------
# LOOKUP TESTS
# ---------------------------------------------------------------------------
print("=" * 60)
print("LOOKUP /lookup?code= TESTS")
print("=" * 60)

def t_lookup_valid_meta():
    r = requests.get(f"{BASE}/lookup?code=133010")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["searched_by"] == "meta_code"
    assert len(data["results"]) > 0
    return f"found {len(data['results'])} result(s), searched_by=meta_code"
test("Valid meta_code (133010)", t_lookup_valid_meta)


def t_lookup_karix_only():
    # karix 601 has no meta_code in JSON -> should fall back to karix search
    r = requests.get(f"{BASE}/lookup?code=601")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["searched_by"] == "karix_code", f"Expected karix_code, got {data['searched_by']}"
    return f"searched_by={data['searched_by']}"
test("Karix-only code (601)", t_lookup_karix_only)


def t_lookup_code_100_ambiguity():
    # "100" exists as meta_code (Invalid parameter) AND as karix_code (Sent)
    # meta_code match should win
    r = requests.get(f"{BASE}/lookup?code=100")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["searched_by"] == "meta_code", f"Expected meta_code to win, got {data['searched_by']}"
    for rec in data["results"]:
        assert rec["meta_code"] == "100", "Result has wrong meta_code"
    return f"meta_code wins, {len(data['results'])} result(s)"
test("Code 100 ambiguity — meta_code should win over karix_code", t_lookup_code_100_ambiguity)


def t_lookup_duplicate_404():
    # meta_code 404 appears TWICE in error_codes.json
    r = requests.get(f"{BASE}/lookup?code=404")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert len(data["results"]) == 2, f"Expected 2 results for duplicate 404, got {len(data['results'])}"
    return f"both duplicates returned: {len(data['results'])} results"
test("Duplicate meta_code 404 returns ALL matches", t_lookup_duplicate_404)


def t_lookup_negative_code():
    # meta_code "-500" exists
    r = requests.get(f"{BASE}/lookup", params={"code": "-500"})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["searched_by"] == "meta_code"
    return f"negative code found, searched_by={data['searched_by']}"
test("Negative meta_code (-500)", t_lookup_negative_code)


def t_lookup_spaces():
    # strip() in the handler should clean these up
    r = requests.get(f"{BASE}/lookup", params={"code": "  133010  "})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return "leading/trailing spaces stripped correctly"
test("Code with leading/trailing spaces ('  133010  ')", t_lookup_spaces)


def t_lookup_unknown_code():
    r = requests.get(f"{BASE}/lookup?code=999999")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    return "correctly returned 404"
test("Unknown code (999999) -> 404", t_lookup_unknown_code)


def t_lookup_missing_param():
    r = requests.get(f"{BASE}/lookup")
    assert r.status_code == 422, f"Expected 422 (validation error), got {r.status_code}"
    return "correctly returned 422"
test("Missing ?code param -> 422", t_lookup_missing_param)


def t_lookup_empty_string():
    r = requests.get(f"{BASE}/lookup?code=")
    # After strip(), empty string won't match anything -> 404
    print(f"     [debug] status={r.status_code}, body={r.text[:200]}")
    return f"status={r.status_code} (expect 404 or 422)"
test("Empty code string (?code=)", t_lookup_empty_string)


def t_lookup_sql_injection():
    r = requests.get(f"{BASE}/lookup", params={"code": "' OR '1'='1"})
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    return "safely returned 404"
test("SQL-injection-like input", t_lookup_sql_injection)


def t_lookup_long_code():
    r = requests.get(f"{BASE}/lookup", params={"code": "A" * 5000})
    assert r.status_code in (404, 413, 422), f"Unexpected status {r.status_code}"
    return f"status={r.status_code}"
test("Very long code (5000 chars)", t_lookup_long_code)


def t_lookup_special_chars():
    r = requests.get(f"{BASE}/lookup", params={"code": "<script>alert(1)</script>"})
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    return "safely handled XSS-like input"
test("XSS-like input in code param", t_lookup_special_chars)


# ---------------------------------------------------------------------------
# GENERATE TESTS  (only structural/error-path tests — no Gemini key needed for failures)
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("GENERATE /generate TESTS")
print("=" * 60)

GOOD_PAYLOAD = {
    "karix_code": "708",
    "meta_code": "471",
    "description": "Spam rate limit hit — too many messages flagged by users.",
    "category": "Not Sent",
    "client_name": "Acme Corp"
}

def t_generate_missing_karix():
    payload = {"meta_code": "471", "description": "test", "category": "Not Sent"}
    r = requests.post(f"{BASE}/generate", json=payload)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "missing karix_code -> 422"
test("generate: missing required karix_code -> 422", t_generate_missing_karix)


def t_generate_missing_description():
    payload = {"karix_code": "708", "category": "Not Sent"}
    r = requests.post(f"{BASE}/generate", json=payload)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "missing description -> 422"
test("generate: missing required description -> 422", t_generate_missing_description)


def t_generate_missing_category():
    payload = {"karix_code": "708", "description": "test"}
    r = requests.post(f"{BASE}/generate", json=payload)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "missing category -> 422"
test("generate: missing required category -> 422", t_generate_missing_category)


def t_generate_empty_body():
    r = requests.post(f"{BASE}/generate", json={})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "empty body -> 422"
test("generate: empty JSON body -> 422", t_generate_empty_body)


def t_generate_no_body():
    r = requests.post(f"{BASE}/generate")
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "no body -> 422"
test("generate: no body at all -> 422", t_generate_no_body)


def t_generate_method_not_allowed():
    r = requests.get(f"{BASE}/generate")
    assert r.status_code == 405, f"Expected 405, got {r.status_code}"
    return "GET /generate -> 405"
test("generate: GET instead of POST -> 405", t_generate_method_not_allowed)


def t_generate_extra_fields():
    payload = {**GOOD_PAYLOAD, "unknown_field": "should_be_ignored"}
    r = requests.post(f"{BASE}/generate", json=payload)
    # Pydantic by default ignores extra fields; Gemini call may succeed or fail
    print(f"     [debug] status={r.status_code}")
    return f"status={r.status_code} (extra fields handled)"
test("generate: extra unknown fields in payload", t_generate_extra_fields)


# ---------------------------------------------------------------------------
# ANALYZE TESTS
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("ANALYZE /analyze TESTS")
print("=" * 60)

def t_analyze_missing_karix():
    payload = {"description": "test", "category": "Not Sent"}
    r = requests.post(f"{BASE}/analyze", json=payload)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "missing karix_code -> 422"
test("analyze: missing required karix_code -> 422", t_analyze_missing_karix)


def t_analyze_empty_body():
    r = requests.post(f"{BASE}/analyze", json={})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return "empty body -> 422"
test("analyze: empty JSON body -> 422", t_analyze_empty_body)


def t_analyze_method_not_allowed():
    r = requests.get(f"{BASE}/analyze")
    assert r.status_code == 405, f"Expected 405, got {r.status_code}"
    return "GET /analyze -> 405"
test("analyze: GET instead of POST -> 405", t_analyze_method_not_allowed)


# ---------------------------------------------------------------------------
# ROOT / STATIC
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("ROOT & STATIC TESTS")
print("=" * 60)

def t_root():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "html" in ct, f"Expected HTML content-type, got {ct}"
    return "returns 200 HTML"
test("GET / returns HTML", t_root)


def t_unknown_route():
    r = requests.get(f"{BASE}/this-does-not-exist")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    return "returns 404"
test("Unknown route -> 404", t_unknown_route)


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print(f"TOTAL: {pass_count} passed, {fail_count} failed out of {pass_count + fail_count} tests")
print("=" * 60)

if fail_count:
    print("\nFailed tests:")
    for status, name, detail in results_log:
        if status != "PASS":
            print(f"  [{status}] {name}: {detail}")
