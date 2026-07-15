import sentry_sdk

import app.main  # noqa: F401  — runs sentry_sdk.init() at import time


def test_client_ip_headers_are_scrubbed():
    # CF-Connecting-IP/True-Client-IP reached a real production Sentry event
    # in clear text (Cloudflare/Render-specific headers Sentry's own filter
    # doesn't know about) — this is the regression test for that fix.
    scrubber = sentry_sdk.get_client().options["event_scrubber"]
    event = {
        "request": {
            "headers": {
                "Cf-Connecting-Ip": "201.20.66.188",
                "True-Client-Ip": "201.20.66.188",
                "User-Agent": "curl/8.7.1",
            }
        }
    }

    scrubber.scrub_event(event)

    headers = event["request"]["headers"]
    assert headers["Cf-Connecting-Ip"] != "201.20.66.188"
    assert headers["True-Client-Ip"] != "201.20.66.188"
    assert headers["User-Agent"] == "curl/8.7.1"
