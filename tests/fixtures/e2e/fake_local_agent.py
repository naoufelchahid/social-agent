#!/usr/bin/env python3
"""Offline Agy/Codex executable fixture selected by the invoked filename."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _record_call(identity: str) -> None:
    log = Path.cwd() / "output" / "fake-agent-calls.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"identity": identity, "arguments": sys.argv[1:]}))
        handle.write("\n")


def _agy() -> None:
    linkedin = (
        "A local content workflow becomes trustworthy when every stage leaves durable "
        "evidence for the next one. Extraction, drafting, review, and image validation "
        "can each be inspected without relying on a hosted orchestration service.\n\n"
        "The useful design move is simple: keep the process sequential, persist each "
        "contract before advancing, and reserve the final decision for a person. This "
        "makes interruption recovery predictable and keeps automation inside a clear "
        "product boundary.\n\n"
        "For small teams, that combination offers a practical path to repeatable "
        "content work: local tools do the mechanical work, independent checks "
        "challenge the draft, and human approval remains the last word."
    )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "concept": "Durable local stages make content automation inspectable.",
                "linkedin": linkedin,
                "x": (
                    "Local content automation is easier to trust when every stage "
                    "persists evidence, independent checks challenge the draft, and "
                    "human approval remains the final boundary."
                ),
                "image_brief": (
                    "An editorial technical illustration of a local sequential "
                    "workflow moving through evidence, review, and human approval."
                ),
            }
        )
    )


def _codex() -> None:
    schema_index = sys.argv.index("--output-schema") + 1
    schema_path = Path(sys.argv[schema_index])
    if schema_path.name == "review-schema-v1.json":
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "passed": True,
                    "summary": "Grounded, aligned, and consistently adapted.",
                    "errors": [],
                }
            )
        )
        return
    if schema_path.name == "image-generation-schema-v1.json":
        from PIL import Image

        image_path = schema_path.parent / "image.png"
        Image.new("RGB", (1536, 1024), (26, 54, 83)).save(image_path, format="PNG")
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "path": image_path.as_posix(),
                    "final_prompt": "Fixture editorial workflow illustration.",
                    "generator_identity": "codex-imagegen-built-in",
                }
            )
        )
        return
    if schema_path.name == "image-review-schema-v1.json":
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "passed": True,
                    "relevance": True,
                    "no_unwanted_text": True,
                    "no_logos": True,
                    "no_watermarks": True,
                    "consistent_with_post": True,
                    "summary": (
                        "Relevant fixture image with no forbidden visual content."
                    ),
                    "feedback": None,
                }
            )
        )
        return
    raise SystemExit(f"unexpected schema: {schema_path}")


identity = Path(sys.argv[0]).name
_record_call(identity)
if identity == "agy":
    _agy()
elif identity == "codex":
    _codex()
else:
    raise SystemExit(f"unexpected fixture executable: {identity}")
