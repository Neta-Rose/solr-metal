import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    url = "https://example.apps.cluster.local/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = {"status": response.status, "url": url}
            print(json.dumps(payload))
            return 0 if 200 <= response.status < 400 else 1
    except urllib.error.URLError as exc:
        print(json.dumps({"error": str(exc), "url": url}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
