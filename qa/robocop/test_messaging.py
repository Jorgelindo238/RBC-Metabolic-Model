from services.robocop.messaging.robocop_alerts import (
    build_iteration_message,
    build_session_completed_message,
    build_session_failed_message,
    build_session_started_message,
)
from services.robocop.messaging.telegram_notifier import (
    build_telegram_notifier_from_env,
)


def test_build_telegram_notifier_from_env_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ROBOCOP_TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("ROBOCOP_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ROBOCOP_TELEGRAM_CHAT_ID", raising=False)
    notifier = build_telegram_notifier_from_env()
    assert notifier.is_enabled is False


def test_build_telegram_notifier_from_env_reads_config(monkeypatch):
    monkeypatch.setenv("ROBOCOP_TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("ROBOCOP_TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("ROBOCOP_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("ROBOCOP_TELEGRAM_MESSAGE_THREAD_ID", "7")
    notifier = build_telegram_notifier_from_env()
    assert notifier.is_enabled is True
    assert notifier.config.bot_token == "bot-token"
    assert notifier.config.chat_id == "12345"
    assert notifier.config.message_thread_id == 7


def test_build_session_started_message_contains_core_session_fields():
    message = build_session_started_message(
        "session-1",
        base_policy_path="config/base_policy.json",
        base_manifest_path="config/base_manifest.json",
        max_iterations=3,
        loop_budget_seconds=3600,
        time_budget_seconds=1200,
        case_time_budget_seconds=300,
        timeout_policy="stop_after_case",
        dry_run=False,
        stop_on_keep=True,
    )
    assert "RoBoCop autosearch started" in message
    assert "session-1" in message
    assert "config/base_policy.json" in message


def test_build_iteration_message_contains_decision_and_scores():
    message = build_iteration_message(
        "session-1",
        {
            "iteration": 2,
            "decision": "Keep",
            "decision_category": "completed_keep",
            "time_aware_score": 12.34,
            "aggregate_score": 18.76,
            "mean_final_loss": 1.2345,
            "completion_status": "completed",
            "benchmark_status": "keep",
            "mutation_summary": "Mutated vmax_VLDH from 0.2 to 0.5",
            "run_dir": "Simulations/brodbar/autoresearch/run_002",
            "decision_record_path": "Simulations/brodbar/autoresearch/record_002.json",
            "decision_reason": "Completed full manifest and passed the keep gate.",
        },
        max_iterations=4,
    )
    assert "RoBoCop iteration 2/4" in message
    assert "completed_keep" in message
    assert "12.3400" in message
    assert "Mutated vmax_VLDH" in message


def test_build_session_completed_message_contains_summary_path():
    message = build_session_completed_message(
        {
            "session_id": "session-1",
            "stop_reason": "stop_on_keep",
            "iterations_completed": 1,
            "max_iterations": 4,
            "kept_iterations": 1,
            "final_promoted_policy_path": "config/final_policy.json",
            "final_promoted_manifest_path": "config/final_manifest.json",
            "elapsed_seconds": 42.0,
            "final_iteration_state": {"orchestrator_decision": "Keep"},
        },
        session_summary_path="Simulations/brodbar/autoresearch/agent_orchestration/sessions/session_1.json",
    )
    assert "RoBoCop session complete" in message
    assert "stop_on_keep" in message
    assert "session_1.json" in message


def test_build_session_failed_message_contains_error():
    message = build_session_failed_message(
        "session-1",
        RuntimeError("scientific evaluator failed"),
        iteration=2,
        base_policy_path="config/base_policy.json",
    )
    assert "RoBoCop session failed" in message
    assert "scientific evaluator failed" in message
    assert "config/base_policy.json" in message
