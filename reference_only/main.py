"""
MediShield Insurance — AI-Powered Document Classifier
======================================================
PRD Goal: Automate classification of scanned insurance documents so that
incoming images are categorised without human intervention and routed to
the correct downstream processing queue.

Categories (per PRD):
  • Patient Bills    — hospital or pharmacy invoices
  • Claim Forms      — MediShield's own claim submission forms
  • KYC Documents   — government-issued identity proofs (Aadhaar, PAN, passport)
  • Medical Reports  — lab results, diagnostic imaging reports
  • Prescriptions    — doctor-issued medication prescriptions
  • Unknown          — anything that does not fit the above

Success Metrics (from PRD):
  - Classification accuracy  ≥ 95% across all categories
  - Processing time / doc    < 5 seconds
  - Reduction in manual vol  ≥ 80%
  - Backlog SLA              < 15 minutes (upload → routed)

Usage:
  uv run python main.py              # process all images
  uv run python main.py --limit 5    # process first 5 images only
  uv run python main.py --delay 6    # 6-second gap between requests (default 4)
"""

import argparse
import os
import re
import time
import pathlib
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(dotenv_path=pathlib.Path(__file__).parent.parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError(
        "GEMINI_API_KEY not found. "
        "Add it to the .env file at the project root."
    )

# Gemini model to use (multimodal vision-capable model)
MODEL_ID = "gemini-2.0-flash-lite"

# Dataset directory (relative to this file)
DATASET_DIR = pathlib.Path(__file__).parent / "dataset"

# Supported image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Predefined document categories (exactly as specified in the PRD)
CATEGORIES = [
    "Patient Bills",
    "Claim Forms",
    "KYC Documents",
    "Medical Reports",
    "Prescriptions",
    "Unknown",
]

# Rate-limit defaults
# Free tier: 15 RPM for gemini-2.0-flash  →  ≥ 4 s between requests
DEFAULT_REQUEST_DELAY_S = 4.0
MAX_RETRIES = 3            # max retries on a 429 before giving up on that image
RETRY_BACKOFF_EXTRA_S = 5  # extra buffer added on top of the API's retryDelay hint

# Prompt sent to Gemini alongside each scanned image
CLASSIFICATION_PROMPT = f"""You are an intelligent document classifier for MediShield Insurance.

Examine the scanned document image carefully — consider its layout, visible text, headings, tables, stamps, logos, and any other visual cues.

Classify the document into EXACTLY ONE of the following categories:
{chr(10).join(f'  - {cat}' for cat in CATEGORIES)}

Category definitions:
- Patient Bills: Hospital or pharmacy invoices showing charges, itemised costs, or payment receipts.
- Claim Forms: MediShield's own standardised claim submission forms.
- KYC Documents: Government-issued identity proofs such as Aadhaar card, PAN card, or passport.
- Medical Reports: Lab results, diagnostic imaging reports, blood work, or pathology reports.
- Prescriptions: Doctor-issued medication prescriptions listing drugs and dosages.
- Unknown: Anything that does not clearly fit one of the above categories.

Rules:
1. Respond with ONLY the category name — no explanation, no punctuation, no extra text.
2. The response must be one of the exact strings listed above.
3. If you are uncertain, respond with "Unknown".
"""


# ---------------------------------------------------------------------------
# Rate-limit helpers
# ---------------------------------------------------------------------------

def _parse_retry_delay(exc: Exception) -> float | None:
    """
    Try to extract the retryDelay value (seconds) from a Gemini 429 exception.
    The API response embeds something like  'retryDelay': '55s'  in the message.
    Returns the number of seconds to wait, or None if it cannot be parsed.
    """
    msg = str(exc)
    # Look for patterns like "retryDelay': '55s'" or "retry in 55.6s"
    for pattern in (
        r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'",
        r"retry in\s+(\d+(?:\.\d+)?)s",
        r"Please retry in\s+(\d+(?:\.\d+)?)s",
    ):
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception is a 429 / RESOURCE_EXHAUSTED error."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """
    Return True if the daily free-tier quota is exhausted (limit: 0 on the
    per-day metric). In that case, retrying in the same day is pointless.
    """
    msg = str(exc)
    return "PerDay" in msg and "limit: 0" in msg


# ---------------------------------------------------------------------------
# Classifier  (with retry + back-off)
# ---------------------------------------------------------------------------

def classify_document(
    client: genai.Client,
    image_path: pathlib.Path,
    max_retries: int = MAX_RETRIES,
) -> tuple[str, float]:
    """
    Classify a single scanned document image using the Gemini multimodal API.
    Automatically retries on 429 RESOURCE_EXHAUSTED, honouring the API's own
    retryDelay hint.

    Args:
        client:      Authenticated Gemini API client.
        image_path:  Path to the image file.
        max_retries: Maximum number of retries on rate-limit errors.

    Returns:
        A tuple of (predicted_category, elapsed_seconds).

    Raises:
        Exception: Re-raises after exhausting retries, or immediately for
                   daily-quota exhaustion (retrying in the same day is futile).
    """
    mime_map = {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif":  "image/gif",
    }
    mime_type = mime_map.get(image_path.suffix.lower(), "image/png")
    image_bytes = image_path.read_bytes()

    attempt = 0
    while True:
        try:
            start = time.perf_counter()
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=CLASSIFICATION_PROMPT),
                ],
            )
            elapsed = time.perf_counter() - start

            raw = response.text.strip() if response.text else "Unknown"
            # Validate against known categories (case-insensitive)
            category = next(
                (cat for cat in CATEGORIES if cat.lower() == raw.lower()),
                "Unknown",
            )
            return category, elapsed

        except Exception as exc:
            if not _is_rate_limit_error(exc):
                raise  # non-rate-limit error → propagate immediately

            if _is_daily_quota_exhausted(exc):
                print(
                    "\n  ⛔  Daily free-tier quota exhausted for this API key.\n"
                    "      No point retrying today. Options:\n"
                    "        1. Wait until midnight (Pacific Time) for quota reset.\n"
                    "        2. Use a different API key with a paid billing plan.\n"
                    "        3. Run again tomorrow.\n"
                )
                raise  # bubble up so the pipeline can stop early

            attempt += 1
            if attempt > max_retries:
                raise  # exhausted retries → propagate

            # Honour the API's retryDelay hint, or fall back to exponential backoff
            hint = _parse_retry_delay(exc)
            wait = (hint + RETRY_BACKOFF_EXTRA_S) if hint else (2 ** attempt * 10)
            print(
                f"          ⚠ Rate limited (attempt {attempt}/{max_retries}). "
                f"Waiting {wait:.0f}s before retry…"
            )
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

# Mapping from category → downstream queue name
QUEUE_MAP: dict[str, str] = {
    "Patient Bills":   "billing_queue",
    "Claim Forms":     "claims_queue",
    "KYC Documents":   "verification_queue",
    "Medical Reports": "medical_review_queue",
    "Prescriptions":   "medical_review_queue",
    "Unknown":         "manual_review_queue",
}


def route_document(category: str) -> str:
    """Return the downstream processing queue for a given category."""
    return QUEUE_MAP.get(category, "manual_review_queue")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(limit: int | None = None, request_delay: float = DEFAULT_REQUEST_DELAY_S) -> None:
    """
    Process images in the dataset directory:
      1. Send to Gemini for classification (with retry on 429).
      2. Validate the returned category.
      3. Route to the correct downstream queue.
      4. Print a structured result and a final summary.

    Args:
        limit:         If set, process only the first N images.
        request_delay: Seconds to wait between API calls (default 4s → 15 RPM).
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    all_images = sorted(
        f for f in DATASET_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not all_images:
        print(f"No image files found in '{DATASET_DIR}'. Exiting.")
        return

    image_files = all_images[:limit] if limit else all_images
    total = len(image_files)
    skipped = len(all_images) - total

    print(f"\n{'='*65}")
    print(f"  MediShield Document Classifier  —  {total} document(s) queued")
    if skipped:
        print(f"  ({skipped} image(s) skipped due to --limit {limit})")
    print(f"  Model   : {MODEL_ID}")
    print(f"  Delay   : {request_delay}s between requests  (free tier: 15 RPM)")
    print(f"{'='*65}\n")

    results: list[dict] = []
    daily_quota_hit = False

    for idx, img_path in enumerate(image_files, start=1):
        print(f"[{idx:>3}/{total}]  Processing: {img_path.name}")

        category = "Unknown"
        queue = route_document(category)
        elapsed = 0.0
        status = "OK"

        try:
            category, elapsed = classify_document(client, img_path)
            queue = route_document(category)
        except Exception as exc:
            queue = route_document("Unknown")
            status = f"ERROR — {exc}"
            if _is_daily_quota_exhausted(exc):
                daily_quota_hit = True

        sla_flag = "⚠ SLOW" if elapsed >= 5 else ""
        print(
            f"          Category : {category}\n"
            f"          Queue    : {queue}\n"
            f"          Time     : {elapsed:.2f}s  {sla_flag}\n"
            f"          Status   : {status}\n"
        )

        results.append(
            {
                "file": img_path.name,
                "category": category,
                "queue": queue,
                "elapsed": elapsed,
                "status": status,
            }
        )

        if daily_quota_hit:
            print("  ⛔  Stopping pipeline — daily quota exhausted.\n")
            break

        # Polite delay between calls to respect free-tier RPM limit
        if idx < total:
            time.sleep(request_delay)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{'='*65}")
    print("  Classification Summary")
    print(f"{'='*65}")

    category_counts: dict[str, int] = {}
    for r in results:
        category_counts[r["category"]] = category_counts.get(r["category"], 0) + 1

    for cat in CATEGORIES:
        count = category_counts.get(cat, 0)
        bar = "█" * count
        print(f"  {cat:<20} {count:>4}   {bar}")

    processed = len(results)
    total_time = sum(r["elapsed"] for r in results)
    avg_time = total_time / processed if processed else 0
    errors = sum(1 for r in results if r["status"] != "OK")
    auto_routed = processed - category_counts.get("Unknown", 0)

    print(f"\n  Processed           : {processed} / {total}")
    print(f"  Auto-routed         : {auto_routed}  ({100*auto_routed/processed:.1f}%)" if processed else "")
    print(f"  Sent to manual review: {category_counts.get('Unknown', 0)}")
    print(f"  Errors              : {errors}")
    print(f"  Avg processing time : {avg_time:.2f}s per document")
    print(f"  Total time          : {total_time:.2f}s")
    print(f"{'='*65}\n")

    if daily_quota_hit:
        print(
            "  💡 Tip: Your free-tier daily quota is exhausted.\n"
            "     - Re-run tomorrow after quota resets, OR\n"
            "     - Enable billing on your Google AI Studio project for higher limits.\n"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MediShield AI Document Classifier — powered by Google Gemini"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        metavar="N",
        help="Process only the first N images (default: 5). Use 0 for all images.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_S,
        metavar="SECONDS",
        help=f"Seconds to wait between API calls (default: {DEFAULT_REQUEST_DELAY_S}). "
             "Free tier allows 15 RPM — keep this ≥ 4.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(limit=args.limit, request_delay=args.delay)
