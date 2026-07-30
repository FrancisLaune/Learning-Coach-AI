"""LCAI-0000A — Automated technical validation before human functional review."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "docs" / "phase3" / "exports"

CURRICULUM_TICKETS: dict[str, dict[str, object]] = {
    "LCAI-0018": {
        "grade": "FR-4E",
        "label": "4e",
        "scripts": [
            "scripts/lcai_0018_phase0_audit.py",
        ],
        "tests": [
            "tests/test_lcai_0018_4e_content_homework.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018_IMPLEMENTATION_REPORT.md",
    },
    "LCAI-0018C": {
        "grade": "FR-CM1",
        "label": "CM1",
        "scripts": [
            "scripts/lcai_0018c_phase0_audit.py",
            "scripts/lcai_0018c_cm1_pipeline.py",
        ],
        "tests": [
            "tests/test_lcai_0018c_cm1_phase0_audit.py",
            "tests/test_lcai_0018c_cm1_pipeline.py",
            "tests/test_lcai_0018c_cm1_content_homework.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018C_IMPLEMENTATION_REPORT.md",
    },
    "LCAI-0018D": {
        "grade": "FR-CM2",
        "label": "CM2",
        "scripts": [
            "scripts/lcai_0018d_phase0_audit.py",
            "scripts/lcai_0018d_cm2_pipeline.py",
        ],
        "tests": [
            "tests/test_lcai_0018d_cm2_phase0_audit.py",
            "tests/test_lcai_0018d_cm2_pipeline.py",
            "tests/test_lcai_0018d_cm2_content_homework.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018D_IMPLEMENTATION_REPORT.md",
    },
    "LCAI-0018E": {
        "grade": "FR-6E",
        "label": "6e",
        "scripts": [
            "scripts/lcai_0018e_phase0_audit.py",
            "scripts/lcai_0018e_6e_pipeline.py",
        ],
        "tests": [
            "tests/test_lcai_0018e_6e_phase0_audit.py",
            "tests/test_lcai_0018e_6e_pipeline.py",
            "tests/test_lcai_0018e_6e_content_homework.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018E_IMPLEMENTATION_REPORT.md",
    },
    "LCAI-0018F": {
        "grade": "FR-5E",
        "label": "5e",
        "scripts": [
            "scripts/lcai_0018f_phase0_audit.py",
            "scripts/lcai_0018f_5e_pipeline.py",
        ],
        "tests": [
            "tests/test_lcai_0018f_5e_phase0_audit.py",
            "tests/test_lcai_0018f_5e_pipeline.py",
            "tests/test_lcai_0018f_5e_content_homework.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018F_IMPLEMENTATION_REPORT.md",
    },
    "LCAI-0018G": {
        "grade": "FR-3E",
        "label": "3e",
        "scripts": [
            "scripts/lcai_0018g_phase0_audit.py",
            "scripts/lcai_0018g_3e_certification.py",
        ],
        "tests": [
            "tests/test_lcai_0018g_3e_content_homework.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018G_IMPLEMENTATION_REPORT.md",
    },
    "LCAI-0018H": {
        "grade": "ALL",
        "label": "Global",
        "scripts": [
            "scripts/lcai_0018h_global_certification_audit.py",
            "scripts/lcai_0000a_global_curriculum_inventory.py",
        ],
        "tests": [
            "tests/test_lcai_0018h_global_certification.py",
        ],
        "implementation_report": "docs/phase3/LCAI-0018H_IMPLEMENTATION_REPORT.md",
    },
}


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""
    duration_ms: int = 0


@dataclass
class ValidationReport:
    ticket: str
    generated_at: str
    implementation: str = "PENDING"
    auto_review: str = "PENDING"
    technical_validation: str = "PENDING"
    checks: list[CheckResult] = field(default_factory=list)
    auto_corrections: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    human_functional_only: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)

    def overall_ok(self) -> bool:
        if self.blocking_issues:
            return False
        failed = [c for c in self.checks if c.status == "FAIL"]
        missing = [c for c in self.checks if c.status == "MISSING"]
        return not failed and not missing


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _check_files_exist(paths: list[str]) -> CheckResult:
    missing = [path for path in paths if not (ROOT / path).exists()]
    if missing:
        return CheckResult(
            "implementation_files",
            "MISSING",
            f"missing: {', '.join(missing)}",
        )
    return CheckResult("implementation_files", "PASS", f"{len(paths)} file(s) present")


def _check_documentation(report_path: str) -> CheckResult:
    path = ROOT / report_path
    if not path.exists():
        return CheckResult("documentation", "MISSING", f"{report_path} not found")
    return CheckResult("documentation", "PASS", report_path)


def _check_ruff(paths: list[str]) -> CheckResult:
    existing = [str(ROOT / p) for p in paths if (ROOT / p).exists()]
    if not existing:
        return CheckResult("ruff", "SKIP", "no paths")
    started = time.perf_counter()
    result = _run([sys.executable, "-m", "ruff", "check", *existing])
    duration = int((time.perf_counter() - started) * 1000)
    if result.returncode == 0:
        return CheckResult("ruff", "PASS", "clean", duration)
    detail = _strip_ansi((result.stdout + result.stderr).strip())[:2000]
    return CheckResult("ruff", "FAIL", detail, duration)


def _check_ruff_format(paths: list[str]) -> CheckResult:
    existing = [str(ROOT / p) for p in paths if (ROOT / p).exists()]
    if not existing:
        return CheckResult("ruff_format", "SKIP", "no paths")
    started = time.perf_counter()
    result = _run([sys.executable, "-m", "ruff", "format", "--check", *existing])
    duration = int((time.perf_counter() - started) * 1000)
    if result.returncode == 0:
        return CheckResult("ruff_format", "PASS", "formatted", duration)
    return CheckResult("ruff_format", "FAIL", _strip_ansi((result.stdout + result.stderr).strip())[:2000], duration)


def _check_mypy(paths: list[str]) -> CheckResult:
    existing = [p for p in paths if (ROOT / p).exists()]
    if not existing:
        return CheckResult("mypy", "SKIP", "no paths")
    mypy_files = []
    for path in existing:
        full = ROOT / path
        if full.is_dir():
            mypy_files.append(path)
        elif path.startswith(("scripts/", "services/", "tests/")):
            mypy_files.append(path)
    if not mypy_files:
        return CheckResult("mypy", "SKIP", "no mypy scope")
    started = time.perf_counter()
    result = _run([sys.executable, "-m", "mypy", *mypy_files])
    duration = int((time.perf_counter() - started) * 1000)
    if result.returncode == 0:
        return CheckResult("mypy", "PASS", "clean", duration)
    return CheckResult("mypy", "FAIL", _strip_ansi((result.stdout + result.stderr).strip())[:2000], duration)


def _check_compileall(paths: list[str]) -> CheckResult:
    existing = [str(ROOT / p) for p in paths if (ROOT / p).exists()]
    if not existing:
        return CheckResult("compileall", "SKIP", "no paths")
    started = time.perf_counter()
    result = _run([sys.executable, "-m", "compileall", "-q", *existing])
    duration = int((time.perf_counter() - started) * 1000)
    if result.returncode == 0:
        return CheckResult("compileall", "PASS", "ok", duration)
    return CheckResult("compileall", "FAIL", (result.stdout + result.stderr).strip()[:2000], duration)


def _check_pytest(test_paths: list[str], *, attempts: int = 3) -> CheckResult:
    existing = [p for p in test_paths if (ROOT / p).exists()]
    if not existing:
        return CheckResult("pytest", "MISSING", "no tests found")
    started = time.perf_counter()
    last_output = ""
    for attempt in range(1, attempts + 1):
        result = _run([sys.executable, "-m", "pytest", *existing, "-q", "--tb=no"])
        output = (result.stdout + result.stderr).strip()
        last_output = output
        if result.returncode == 0:
            duration = int((time.perf_counter() - started) * 1000)
            tail = output.splitlines()[-1] if output else "no output"
            return CheckResult("pytest", "PASS", tail, duration)
        retryable = any(
            token in output.lower()
            for token in ("cannot open file", "utilisé par un autre processus", "used by another process", "io error")
        )
        if retryable and attempt < attempts:
            time.sleep(2 * attempt)
            continue
        if retryable and "learning_coach_v2.duckdb" in output.lower():
            duration = int((time.perf_counter() - started) * 1000)
            return CheckResult(
                "pytest",
                "WARN",
                "DuckDB verrouillée (Windows/git) — relancer hors lock ou fermer git index",
                duration,
            )
        break
    duration = int((time.perf_counter() - started) * 1000)
    tail = last_output.splitlines()[-1] if last_output else "no output"
    return CheckResult("pytest", "FAIL", tail, duration)


def _check_smoke_startup() -> CheckResult:
    smoke = ROOT / "scripts" / "smoke_family_virtual_teacher_connection.py"
    if not smoke.exists():
        return CheckResult("app_startup_smoke", "SKIP", "smoke script missing")
    started = time.perf_counter()
    result = _run([sys.executable, str(smoke)])
    duration = int((time.perf_counter() - started) * 1000)
    if result.returncode == 0:
        return CheckResult("app_startup_smoke", "PASS", "smoke ok", duration)
    detail = (result.stdout + result.stderr).strip()[:2000]
    return CheckResult("app_startup_smoke", "FAIL", detail, duration)


def validate_ticket(ticket: str, *, run_smoke: bool) -> ValidationReport:
    config = CURRICULUM_TICKETS.get(ticket)
    if config is None:
        raise SystemExit(f"Unknown ticket: {ticket}. Known: {', '.join(CURRICULUM_TICKETS)}")

    if config.get("status") == "PENDING":
        report = ValidationReport(
            ticket=ticket,
            generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            implementation="PENDING",
            auto_review="SKIP",
            technical_validation="PENDING",
        )
        report.human_functional_only = [
            f"Implémenter {ticket} puis relancer la validation technique IA",
        ]
        return report

    scripts = list(config["scripts"])
    tests = list(config["tests"])
    report_path = str(config["implementation_report"])
    all_paths = scripts + tests

    report = ValidationReport(
        ticket=ticket,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )

    report.checks.append(_check_files_exist(all_paths))
    report.checks.append(_check_documentation(report_path))
    report.checks.append(_check_ruff(all_paths))
    report.checks.append(_check_ruff_format(all_paths))
    report.checks.append(_check_mypy(all_paths))
    report.checks.append(_check_compileall(all_paths))
    report.checks.append(_check_pytest(tests))
    if run_smoke:
        report.checks.append(_check_smoke_startup())

    missing_impl = report.checks[0].status == "MISSING"
    report.implementation = "NOK" if missing_impl else "OK"
    failed = [c for c in report.checks if c.status == "FAIL"]
    warned = [c for c in report.checks if c.status == "WARN"]
    report.auto_review = "NOK" if failed else "OK"
    report.technical_validation = "OK" if report.overall_ok() else ("WARN" if failed == [] and warned else "NOK")

    label = str(config["label"])
    grade = str(config["grade"])
    report.human_functional_only = [
        f"Parcours devoirs {label} ({grade}) dans l'UI parent/élève",
        f"Vérification UX génération devoir par matière disponible",
        "Arbitrage produit sur écarts résiduels multi-matières (hors scope publication AI)",
    ]
    if missing_impl:
        report.blocking_issues.append(f"Implementation files missing for {ticket}")
    for check in failed:
        report.blocking_issues.append(f"{check.name}: {check.detail[:240]}")

    return report


def _write_reports(report: ValidationReport) -> tuple[Path, Path]:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    slug = report.ticket.lower().replace("-", "_")
    json_path = EXPORTS / f"lcai_0000a_{slug}_validation_report.json"
    md_path = EXPORTS / f"lcai_0000a_{slug}_validation_report.md"

    payload = asdict(report)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# LCAI-0000A — Rapport validation technique — {report.ticket}",
        "",
        f"- Généré : {report.generated_at}",
        f"- Implémentation : **{report.implementation}**",
        f"- Auto-revue IA : **{report.auto_review}**",
        f"- Validation technique : **{report.technical_validation}**",
        "",
        "## Contrôles",
        "",
        "| Contrôle | Statut | Détail |",
        "|----------|--------|--------|",
    ]
    for check in report.checks:
        detail = check.detail.replace("|", "\\|").replace("\n", " ")[:120]
        lines.append(f"| {check.name} | {check.status} | {detail} |")

    lines.extend(["", "## Validation humaine uniquement", ""])
    for item in report.human_functional_only:
        lines.append(f"- {item}")

    if report.blocking_issues:
        lines.extend(["", "## Blocages techniques (IA)", ""])
        for issue in report.blocking_issues:
            lines.append(f"- {issue}")
    else:
        lines.extend(["", "## Blocages techniques", "", "Aucun — prêt pour validation fonctionnelle humaine."])

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _write_curriculum_status(reports: list[ValidationReport]) -> Path:
    path = ROOT / "docs" / "phase3" / "LCAI-0000A_CURRICULUM_VALIDATION_STATUS.md"
    lines = [
        "# LCAI-0000A — État validation curriculums LCAI-0018",
        "",
        f"Dernière exécution : {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "",
        "| Ticket | Niveau | Implémentation | Validation technique IA | Action humaine |",
        "|--------|--------|----------------|-------------------------|----------------|",
    ]
    for report in reports:
        config = CURRICULUM_TICKETS[report.ticket]
        human = "Parcours UI devoirs" if report.technical_validation in {"OK", "WARN"} else (
            "En attente implémentation" if report.implementation == "PENDING" else "Bloqué — corriger d'abord"
        )
        lines.append(
            f"| {report.ticket} | {config['label']} | {report.implementation} | "
            f"{report.technical_validation} | {human} |"
        )
    lines.extend(
        [
            "",
            "## Processus",
            "",
            "1. Cursor exécute `scripts/lcai_0000a_technical_validation.py --curriculum-all`",
            "2. Cursor corrige automatiquement les échecs résolvables",
            "3. Commit + push après série 18 complète",
            "4. Humain : validation fonctionnelle et UX uniquement",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="LCAI-0000A technical validation runner")
    parser.add_argument("--ticket", help="Ticket id e.g. LCAI-0018E")
    parser.add_argument(
        "--curriculum-all",
        action="store_true",
        help="Validate all LCAI-0018 curriculum tickets (C/D/E/F)",
    )
    parser.add_argument("--smoke", action="store_true", help="Include app startup smoke test")
    args = parser.parse_args()

    if args.curriculum_all:
        tickets = list(CURRICULUM_TICKETS)
        reports = [validate_ticket(ticket, run_smoke=args.smoke and ticket == tickets[-1]) for ticket in tickets]
        for report in reports:
            json_path, md_path = _write_reports(report)
            print(f"{report.ticket}: {report.technical_validation} -> {md_path.name}")
        status_path = _write_curriculum_status(reports)
        print(f"Curriculum status: {status_path}")
        if not all(r.overall_ok() or r.technical_validation == "WARN" for r in reports if r.implementation == "OK"):
            raise SystemExit(1)
        pending = [r.ticket for r in reports if r.implementation == "PENDING"]
        if pending:
            print(f"Pending implementation: {', '.join(pending)}")
        return

    if not args.ticket:
        parser.error("Provide --ticket or --curriculum-all")

    report = validate_ticket(args.ticket, run_smoke=args.smoke)
    json_path, md_path = _write_reports(report)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if not report.overall_ok():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
