from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from idp_agent.cli import main


def test_generate_process_evaluate_flow(tmp_path: Path) -> None:
    runner = CliRunner()
    data = tmp_path / "data"
    assert runner.invoke(main, ["generate-samples", "-d", str(data)]).exit_code == 0

    out = tmp_path / "out"
    result = runner.invoke(
        main, ["process", str(data / "samples" / "inspection_report_fr.txt"), "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "create_ticket" in result.output
    assert (out / "reports" / "inspection_report_fr_txt.md").is_file()

    result = runner.invoke(main, ["evaluate", str(data / "samples"), "--min-f1", "0.95"])
    assert result.exit_code == 0, result.output
    assert "Field accuracy" in result.output


def test_process_a_folder_and_report_failures(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("Maintenance report\nEquipment: P-1\n", encoding="utf-8")
    result = CliRunner().invoke(main, ["process", str(tmp_path), "-o", str(tmp_path / "o")])
    assert result.exit_code == 0 and "1 processed, 0 failed" in result.output


def test_unreadable_file_gives_nonzero_exit(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    result = CliRunner().invoke(main, ["process", str(empty), "-o", str(tmp_path / "o")])
    assert result.exit_code == 1


def test_evaluate_fails_below_threshold(data_root: Path) -> None:
    result = CliRunner().invoke(
        main, ["evaluate", str(data_root / "samples_hard"), "--min-f1", "0.9"]
    )
    assert result.exit_code == 1


def test_invalid_configuration_is_a_clean_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDP_MAX_RETRIES", "zero")
    result = CliRunner().invoke(main, ["process", str(tmp_path)])
    assert result.exit_code != 0 and "IDP_MAX_RETRIES" in result.output
