"""Shared helpers for the staff harness. Stdlib only.

Every harness script fails closed: on any problem it exits non-zero with one
reason code from REASONS. Reason codes are fixed strings, so they are safe to
pass through job outputs and to post in a failure notice. Model text never is.
"""
import json
import os
import sys

# Fixed reason codes. The write stage posts only these (S-SEC-002).
REASONS = {
    # contract and input (build_input.py, contract.py, redact_check.py)
    "contract_invalid", "not_operator", "input_fetch_failed", "input_invalid",
    "input_too_large", "input_redaction", "nothing_to_review",
    # agent preparation (prepare_agent.py)
    "agent_invalid",
    # model run (workflow)
    "claude_timeout", "claude_failed",
    # envelope and output (validate_output.py)
    "envelope_invalid", "cost_unknown", "cost_cap", "max_turns", "budget_exceeded",
    "model_error", "usage_limit", "no_output", "output_not_json", "schema_invalid",
    "multiple_epics", "parent_mismatch", "blocking_order", "duplicate_id",
    "ac_id_mismatch", "recommended_not_option", "unknown_area", "stage_violation", "revision_rewritten",
    # reviewer output (validate_output.py --agent reviewer)
    "type_mismatch", "target_mismatch", "sha_mismatch", "finding_id_invalid", "severity_order",
    "unknown_finding",
    # architect output (validate_output.py --agent architect)
    "trigger_mismatch", "constraint_id_mismatch", "option_mismatch", "owner_field_set", "spec_invalid",
    "unknown_reference", "assumption_id_used",
    # developer (dev_bundle.py, code_map.py, validate_output.py --agent developer, work_sandbox.py)
    "code_map_invalid", "kind_mismatch", "ticket_mismatch", "not_ready", "path_out_of_scope", "flag_missing",
    "case_clash",
    "ac_not_ready", "sandbox_failed",
    # code diff check (dev_diff_check.py)
    "diff_failed",
    # test engineer (qa_bundle.py, test_map.py, validate_output.py --agent test-gen-api)
    "test_map_invalid", "citation_missing", "cite_invalid",
    # redaction of the output (redact_check.py, check_transcript.py)
    "redaction_hit",
    # interview transcripts (check_transcript.py)
    "transcript_invalid",
    # write stage and bookkeeping
    "record_failed", "read_job_failed", "artifact_missing", "render_failed", "render_too_large",
    # outcome store and review log (append_run_log.py, log_review.py, report.py)
    "log_invalid", "log_store_failed", "review_invalid",
}


class HarnessError(Exception):
    """A fail-closed stop with a fixed reason code and a detail free of model text."""

    def __init__(self, reason, detail=""):
        assert reason in REASONS, reason
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def run_main(main):
    """Run a script's main(); turn a HarnessError into exit code 2 and a reason."""
    try:
        main()
    except HarnessError as err:
        print(f"::error::{err}", file=sys.stderr)
        reason_file = os.environ.get("STAFF_REASON_FILE")
        # The first failure in a job wins; later steps don't overwrite it.
        if reason_file and not os.path.exists(reason_file):
            with open(reason_file, "w", encoding="utf-8") as fh:
                fh.write(err.reason)
        sys.exit(2)


def load_json(path, reason):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise HarnessError(reason, f"cannot read JSON from {path} ({type(exc).__name__})") from None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
