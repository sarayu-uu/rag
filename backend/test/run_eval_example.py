"""
Quick local caller for POST /test/evaluate.

Usage:
  python test/run_eval_example.py --token "<ACCESS_TOKEN>" --question "What is X?"
"""

from __future__ import annotations

import argparse
import json

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Call /test/evaluate and print JSON response.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--token", required=True, help="Bearer access token.")
    parser.add_argument("--question", required=True, help="Question to evaluate.")
    parser.add_argument("--ground-truth", default=None, help="Optional reference answer.")
    parser.add_argument("--limit", type=int, default=5, help="Context chunk limit.")
    args = parser.parse_args()

    payload = {
        "question": args.question,
        "ground_truth": args.ground_truth,
        "limit": args.limit,
    }

    response = requests.post(
        f"{args.base_url.rstrip('/')}/test/evaluate",
        headers={
            "Authorization": f"Bearer {args.token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )

    print(f"HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        print(response.text)
        return
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
