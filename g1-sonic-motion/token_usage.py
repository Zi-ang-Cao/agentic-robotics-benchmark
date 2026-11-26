#!/usr/bin/env python3
"""Summarize one ALE episode's gateway LLM accounting without opening conversations.

Usage: python3 token_usage.py EPISODE_DIR
       python3 token_usage.py EPISODE_DIR/trace.transport.jsonl
       python3 token_usage.py --example

Pinned ALE engine: bfb75050aca2c54b45c5ab23bae6028a834a468a.
Input is exclusively the canonical v1 gateway transport JSONL. The tool never opens
ATIF trajectories, judge transcripts, execution logs, prompts, or provider payloads.
Run on a finished episode for final totals. The report covers this gateway only.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

TRACE = "trace.transport.jsonl"
ENGINE = "bfb75050aca2c54b45c5ab23bae6028a834a468a"
COUNTERS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
BASE = {"schema_version", "kind", "seq", "timestamp", "episode_id", "call_id"}
ALLOWED = {
    "call": BASE | set(COUNTERS) | {"model", "purpose", "request_digest", "response_digest",
        "provider_response_id", "stop_reason", "latency_ms", "disposition", "refusal_limit", "upstream_status"},
    "replay": BASE | {"request_digest", "reason", "charged"},
    "trajectory_link": BASE | {"trajectory_id", "step_id"},
}


class InvalidTrace(ValueError):
    """All diagnostics are fixed text and line numbers. Raw records stay private."""


def numeric(value):
    return type(value) is int and value >= 0


def count_call(group, row, line):
    disposition = row.get("disposition")
    if disposition not in ("forwarded", "failed", "refused"):
        raise InvalidTrace(f"line {line}: invalid call disposition")
    group[disposition] += 1
    present = {key: row[key] for key in COUNTERS if key in row and row[key] is not None}
    if any(not numeric(value) for value in present.values()):
        raise InvalidTrace(f"line {line}: expected nonnegative integer token counts")
    if "input_tokens" in present and any(present.get(key, 0) > present["input_tokens"]
                                          for key in ("cache_read_tokens", "cache_write_tokens")):
        raise InvalidTrace(f"line {line}: cache subset exceeds inclusive input")
    if disposition == "refused":
        if any(present.values()):
            raise InvalidTrace(f"line {line}: local refusal contains positive provider usage")
        return
    # The pinned gateway commits failed and forwarded attempts. When a provider
    # omits usage its dialect can normalize missing fields to literal zero.
    for key in COUNTERS:
        group[key] += present.get(key, 0)
        if key not in present:
            group["missing_" + key] += 1
    if "input_tokens" not in present or "output_tokens" not in present:
        group["missing_core_fields"] += 1
    elif present["input_tokens"] == 0 and present["output_tokens"] == 0:
        group["zero_pair"] += 1
    elif present["input_tokens"] == 0 or present["output_tokens"] == 0:
        group["one_zero"] += 1


def summarize_role(g):
    upstream = g["forwarded"] + g["failed"]
    total = g["input_tokens"] + g["output_tokens"]
    uncertain = g["missing_core_fields"] + g["zero_pair"] + g["one_zero"]
    evidence = ("no_upstream_calls" if upstream == 0 else
                "partial_or_ambiguous" if uncertain else "positive_input_and_output_on_every_call")
    return {
        "call_records": upstream + g["refused"], "ale_model_calls": upstream,
        "forwarded": g["forwarded"], "failed": g["failed"], "gateway_refused": g["refused"],
        "uncharged_replays": {"completed_cache": g["completed-cache"], "inflight_coalesced": g["inflight-coalesced"]},
        "recorded_token_sums": {**{k: g[k] for k in COUNTERS}, "input_plus_output": total},
        "missing_counter_calls": {k: g["missing_" + k] for k in COUNTERS},
        "upstream_calls_missing_input_or_output_field": g["missing_core_fields"],
        "upstream_calls_with_zero_input_and_output": g["zero_pair"],
        "upstream_calls_with_one_zero_core_counter": g["one_zero"],
        "usage_evidence": evidence,
        "supported_input_plus_output": None if uncertain else total,
    }


def summarize(lines):
    roles = {"agent": Counter(), "judge": Counter()}
    owners = {}
    episode = None
    links = 0
    digest = hashlib.sha256()
    for seq, raw in enumerate(lines):
        line = seq + 1
        # Only ALE's small, payload-free transport records are valid input.
        if not raw.endswith(b"\n"):
            raise InvalidTrace(f"line {line}: unterminated transport record")
        if len(raw) > 1024 * 1024:
            raise InvalidTrace(f"line {line}: oversized transport metadata")
        try:
            row = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise InvalidTrace(f"line {line}: invalid transport JSON") from None
        if not isinstance(row, dict) or type(row.get("kind")) is not str or row["kind"] not in ALLOWED:
            raise InvalidTrace(f"line {line}: unsupported transport event")
        kind = row["kind"]
        if set(row) - ALLOWED[kind]:
            raise InvalidTrace(f"line {line}: unexpected noncanonical transport fields")
        if type(row.get("schema_version")) is not int or row["schema_version"] != 1:
            raise InvalidTrace(f"line {line}: unsupported schema version")
        if not numeric(row.get("seq")) or row["seq"] != seq:
            raise InvalidTrace(f"line {line}: incomplete or repeated sequence")
        if not isinstance(row.get("episode_id"), str) or not row["episode_id"]:
            raise InvalidTrace(f"line {line}: missing episode identity")
        if episode is not None and row["episode_id"] != episode:
            raise InvalidTrace(f"line {line}: more than one episode in a trace")
        episode = row["episode_id"]
        call_id = row.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            raise InvalidTrace(f"line {line}: missing call identity")
        if kind == "call":
            purpose = row.get("purpose", "agent")
            if not isinstance(purpose, str) or purpose not in roles:
                raise InvalidTrace(f"line {line}: invalid call purpose")
            if call_id in owners:
                raise InvalidTrace(f"line {line}: duplicate original call")
            owners[call_id] = purpose
            count_call(roles[purpose], row, line)
        else:
            if call_id not in owners:
                raise InvalidTrace(f"line {line}: event refers to an unobserved call")
            if kind == "replay":
                reason = row.get("reason")
                if row.get("charged", False) is not False or reason not in ("completed-cache", "inflight-coalesced"):
                    raise InvalidTrace(f"line {line}: invalid replay accounting")
                roles[owners[call_id]][reason] += 1
            else:
                links += 1
        digest.update(raw)
    return {
        "source": TRACE, "schema_version": 1, "ale_engine_commit": ENGINE, "trace_sha256": digest.hexdigest(),
        "trajectory_links_ignored": links,
        "agent": summarize_role(roles["agent"]),
        "judge": summarize_role(roles["judge"]),
        "combined": summarize_role(roles["agent"] + roles["judge"]),
        "provider_billable_tokens": None,
        "interpretation": [
            "ALE model calls count forwarded and failed attempts. A gateway refusal adds no upstream call.",
            "Gateway replays reuse an earlier call without an additional charge. Provider cache reads and writes are subsets of inclusive input.",
            "Recorded sums add counters present in transport. ALE can write zero for unavailable provider usage. Supported totals are null whenever a core counter is missing or zero on an upstream attempt.",
            "Provider billing and prices are external. Robot FSQ actions and local ONNX inference are outside the LLM transport trace."
        ],
    }


def example_records():
    """Synthetic metadata fixture with an agent, a judge, caching, retries and missing usage."""
    rows = [
        ("call", "A", dict(purpose="agent", disposition="forwarded", input_tokens=120, output_tokens=20,
                            cache_read_tokens=40, cache_write_tokens=10)),
        ("replay", "A", dict(reason="completed-cache", charged=False)),
        ("trajectory_link", "A", dict(trajectory_id="example-trajectory", step_id=1)),
        ("call", "J", dict(purpose="judge", disposition="forwarded", input_tokens=30, output_tokens=7,
                            cache_read_tokens=5, cache_write_tokens=0)),
        ("call", "F", dict(purpose="agent", disposition="failed", upstream_status=503,
                            input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0)),
        ("call", "R", dict(purpose="agent", disposition="refused", refusal_limit="max_model_calls",
                            input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0)),
        ("replay", "R", dict(reason="inflight-coalesced", charged=False)),
    ]
    for seq, (kind, call, fields) in enumerate(rows):
        row = dict(schema_version=1, seq=seq, timestamp="2000-01-01T00:00:00Z",
                   episode_id="synthetic-example", kind=kind, call_id=call)
        if kind in ("call", "replay"):
            row["request_digest"] = "sha256:" + hashlib.sha256(call.encode()).hexdigest()
        if kind == "call":
            row["model"] = "example-model"
        yield (json.dumps({**row, **fields}, separators=(",", ":")) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("episode", type=Path, nargs="?", help="one episode directory or its canonical transport trace")
    source.add_argument("--example", action="store_true", help="run the embedded numeric fixture")
    args = parser.parse_args()
    try:
        if args.example:
            report = summarize(example_records())
            report["example"] = True
        else:
            path = args.episode / TRACE if args.episode.is_dir() else args.episode
            if path.name != TRACE or path.is_symlink() or not path.is_file():
                raise InvalidTrace("canonical trace unavailable; usage is unknown")
            with path.open("rb") as stream:
                report = summarize(stream)
    except (InvalidTrace, OSError) as exc:
        print(json.dumps({"status": "unavailable", "reason": str(exc) if isinstance(exc, InvalidTrace)
                          else "cannot read canonical transport trace", "usage": None}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
