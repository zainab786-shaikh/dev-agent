"""Entry point.

  python main.py profile [--client angular|react] [--server node|python|java] [--orm <name>] [--database <name>]
  python main.py prd "<product requirement>" [--file req.txt] [--new]
  python main.py sysrs [--prd <file>] [--new]
  python main.py srs [--prd <file>] [--sysrs <file>] [--new]
  python main.py architecture [--srs <file>] [--sysrs <file>] [--new]
  python main.py lld [--srs <file>] [--architecture <file>] [--new]
  python main.py dev [--architecture <file>] [--lld <file>] [--new]
  python main.py testing [--prd <file>] [--srs <file>] [--architecture <file>] [--lld <file>] [--dev <file>] [--new]

After every step the living traceability matrix in output/traceability/ is rebuilt from the latest artifacts.

Run `profile` first: it fixes the technology stack of the three-tier web application (web client, API server,
ORM, database) and every later stage follows it.

Inputs default to the latest saved file of each earlier artifact. If an earlier version of the artifact
itself exists in output/<artifact>/, it is updated; use --new to start from scratch.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.decision_judge import DecisionJudge  # noqa: E402
from src.architecture import ArchitectureAuthorAgent, ArchitectureReviewerAgent, ArchitectureWorkflow  # noqa: E402
from src.architecture.models import ArchitectureAnalysis, ArchitectureDocument  # noqa: E402
from src.artifact_store import latest_artifact_file, load_architecture, load_dev, load_lld, load_prd, load_srs, load_sysrs  # noqa: E402
from src.config import Settings  # noqa: E402
from src.dev import DevAuthorAgent, DevReviewerAgent, DevWorkflow  # noqa: E402
from src.dev.models import DevAnalysis, DevDocument  # noqa: E402
from src.existing import load_existing  # noqa: E402
from src.interaction import ConsoleInteraction  # noqa: E402
from src.llm import LLMFactory  # noqa: E402
from src.lld import LldAuthorAgent, LldReviewerAgent, LldWorkflow  # noqa: E402
from src.lld.models import LldAnalysis, LldDocument  # noqa: E402
from src.profile import ProfileWorkflow, load_profile  # noqa: E402
from src.prd import PrdAuthorAgent, PrdReviewerAgent, PrdWorkflow  # noqa: E402
from src.prd.models import ProductRequirementsAnalysis, ProductRequirementsDocument  # noqa: E402
from src.testing import QaAuthorAgent, QaReviewerAgent, QaWorkflow  # noqa: E402
from src.testing.models import QaAnalysis, QaDocument  # noqa: E402
from src.traceability import refresh  # noqa: E402
from src.srs import SrsAuthorAgent, SrsReviewerAgent, SrsWorkflow  # noqa: E402
from src.srs.models import SoftwareRequirementsAnalysis, SoftwareRequirementsDocument  # noqa: E402
from src.sysrs import SysrsAuthorAgent, SysrsReviewerAgent, SysrsWorkflow  # noqa: E402
from src.sysrs.models import SystemRequirementsAnalysis, SystemRequirementsDocument  # noqa: E402


def common(settings: Settings, factory: LLMFactory, name: str) -> dict:
    return {
        "interaction": ConsoleInteraction(),
        "output_dir": settings.output_dir / name,
        "max_iterations": settings.max_iterations,
        "judge": DecisionJudge(factory.create(settings.model_for(name, "reviewer"))),
    }


def previous_version(args, settings: Settings, name: str, document_cls, analysis_cls):
    return None if args.new else load_existing(settings.output_dir / name, name, document_cls, analysis_cls)


def latest(settings: Settings, name: str, explicit: Path | None) -> Path:
    return explicit or latest_artifact_file(settings.output_dir / name, name)


def profile_decisions(settings: Settings):
    found = load_profile(settings.output_dir)
    if found is None:
        raise SystemExit("No application profile found. Choose the technology stack first: python main.py profile")
    return found[0].decisions


def run_profile(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    ProfileWorkflow(
        ConsoleInteraction(), settings.output_dir,
        DecisionJudge(factory.create(settings.model_for("profile", "reviewer"))),
    ).run(
        requirement=args.requirement or "",
        presets={"client": args.client, "server": args.server, "orm": args.orm, "database": args.database},
        existing=None if args.new else load_profile(settings.output_dir),
    )


def run_prd(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    if args.file:
        requirement = args.file.read_text(encoding="utf-8")
    else:
        requirement = args.requirement or input("Describe the software requirement:\n> ")
    if not requirement.strip():
        raise SystemExit("A product requirement is required")

    PrdWorkflow(
        author=PrdAuthorAgent(factory.create(settings.model_for("prd", "author"))),
        reviewer=PrdReviewerAgent(factory.create(settings.model_for("prd", "reviewer"))),
        **common(settings, factory, "prd"),
    ).use_profile(profile_decisions(settings)).run(
        requirement,
        previous_version(args, settings, "prd", ProductRequirementsDocument, ProductRequirementsAnalysis),
    )


def run_sysrs(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    SysrsWorkflow(
        author=SysrsAuthorAgent(factory.create(settings.model_for("sysrs", "author"))),
        reviewer=SysrsReviewerAgent(factory.create(settings.model_for("sysrs", "reviewer"))),
        **common(settings, factory, "sysrs"),
    ).use_profile(profile_decisions(settings)).run(
        load_prd(latest(settings, "prd", args.prd)),
        previous_version(args, settings, "sysrs", SystemRequirementsDocument, SystemRequirementsAnalysis),
    )


def run_srs(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    SrsWorkflow(
        author=SrsAuthorAgent(factory.create(settings.model_for("srs", "author"))),
        reviewer=SrsReviewerAgent(factory.create(settings.model_for("srs", "reviewer"))),
        **common(settings, factory, "srs"),
    ).use_profile(profile_decisions(settings)).run(
        load_prd(latest(settings, "prd", args.prd)),
        load_sysrs(latest(settings, "sysrs", args.sysrs)),
        previous_version(args, settings, "srs", SoftwareRequirementsDocument, SoftwareRequirementsAnalysis),
    )


def run_architecture(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    ArchitectureWorkflow(
        author=ArchitectureAuthorAgent(factory.create(settings.model_for("architecture", "author"))),
        reviewer=ArchitectureReviewerAgent(factory.create(settings.model_for("architecture", "reviewer"))),
        **common(settings, factory, "architecture"),
    ).use_profile(profile_decisions(settings)).run(
        load_srs(latest(settings, "srs", args.srs)),
        load_sysrs(latest(settings, "sysrs", args.sysrs)),
        previous_version(args, settings, "architecture", ArchitectureDocument, ArchitectureAnalysis),
    )


def run_lld(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    LldWorkflow(
        author=LldAuthorAgent(factory.create(settings.model_for("lld", "author"))),
        reviewer=LldReviewerAgent(factory.create(settings.model_for("lld", "reviewer"))),
        **common(settings, factory, "lld"),
    ).use_profile(profile_decisions(settings)).run(
        load_srs(latest(settings, "srs", args.srs)),
        load_architecture(latest(settings, "architecture", args.architecture)),
        previous_version(args, settings, "lld", LldDocument, LldAnalysis),
    )


def run_dev(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    DevWorkflow(
        author=DevAuthorAgent(factory.create(settings.model_for("dev", "author"))),
        reviewer=DevReviewerAgent(factory.create(settings.model_for("dev", "reviewer"))),
        project_dir=settings.output_dir / "dev" / "project",
        **common(settings, factory, "dev"),
    ).use_profile(profile_decisions(settings)).run(
        load_architecture(latest(settings, "architecture", args.architecture)),
        load_lld(latest(settings, "lld", args.lld)),
        previous_version(args, settings, "dev", DevDocument, DevAnalysis),
    )


def run_testing(args: argparse.Namespace, settings: Settings, factory: LLMFactory) -> None:
    QaWorkflow(
        author=QaAuthorAgent(factory.create(settings.model_for("testing", "author"))),
        reviewer=QaReviewerAgent(factory.create(settings.model_for("testing", "reviewer"))),
        **common(settings, factory, "testing"),
    ).use_profile(profile_decisions(settings)).run(
        load_prd(latest(settings, "prd", args.prd)),
        load_srs(latest(settings, "srs", args.srs)),
        load_architecture(latest(settings, "architecture", args.architecture)),
        load_lld(latest(settings, "lld", args.lld)),
        load_dev(latest(settings, "dev", args.dev)),
        previous_version(args, settings, "testing", QaDocument, QaAnalysis),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate software artifacts with local LLM agents.")
    sub = parser.add_subparsers(dest="artifact", required=True)

    def add(name: str, help_text: str, run) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--new", action="store_true", help="Ignore the existing version and start from scratch")
        p.set_defaults(run=run)
        return p

    profile = add("profile", "Application profile: the three-tier technology stack", run_profile)
    profile.add_argument("--requirement", help="Optional product description, only used to inform the recommendation")
    profile.add_argument("--client", help="Web client framework: angular or react (skips the question)")
    profile.add_argument("--server", help="API server stack: node, python or java (skips the question)")
    profile.add_argument("--orm", help="ORM for the chosen server stack (skips the question)")
    profile.add_argument("--database", help="Database: postgresql, mysql or sql server (skips the question)")

    prd = add("prd", "Product Requirements Document", run_prd)
    prd.add_argument("requirement", nargs="?", help="New or changed product requirement text")
    prd.add_argument("--file", type=Path, help="Read the requirement from a file")

    sysrs = add("sysrs", "System Requirements Specification", run_sysrs)
    sysrs.add_argument("--prd", type=Path, help="Saved PRD JSON (default: latest in output/prd)")

    srs = add("srs", "Software Requirements Specification", run_srs)
    srs.add_argument("--prd", type=Path, help="Saved PRD JSON (default: latest in output/prd)")
    srs.add_argument("--sysrs", type=Path, help="Saved system requirements JSON (default: latest in output/sysrs)")

    architecture = add("architecture", "Architecture Design", run_architecture)
    architecture.add_argument("--srs", type=Path, help="Saved SRS JSON (default: latest in output/srs)")
    architecture.add_argument("--sysrs", type=Path, help="Saved system requirements JSON (default: latest in output/sysrs)")

    lld = add("lld", "Detailed Technical Design", run_lld)
    lld.add_argument("--srs", type=Path, help="Saved SRS JSON (default: latest in output/srs)")
    lld.add_argument("--architecture", type=Path, help="Saved architecture JSON (default: latest in output/architecture)")

    dev = add("dev", "Development artifacts: source code, unit tests, git workflow", run_dev)
    dev.add_argument("--architecture", type=Path, help="Saved architecture JSON (default: latest in output/architecture)")
    dev.add_argument("--lld", type=Path, help="Saved LLD JSON (default: latest in output/lld)")

    testing = add("testing", "Testing artifacts: strategy, test cases, UAT, performance, security", run_testing)
    for option, help_text in [
        ("prd", "output/prd"), ("srs", "output/srs"), ("architecture", "output/architecture"),
        ("lld", "output/lld"), ("dev", "output/dev"),
    ]:
        testing.add_argument(f"--{option}", type=Path, help=f"Saved JSON (default: latest in {help_text})")

    args = parser.parse_args()
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
    args.run(args, settings, LLMFactory(settings))

    if args.artifact == "profile":
        return
    matrix = refresh(settings.output_dir, args.artifact)
    print(
        f"\nTraceability matrix updated: {len(matrix.nodes)} items, {len(matrix.edges)} links, "
        f"{len(matrix.gaps)} gaps, {len(matrix.broken_links)} broken links "
        f"({settings.output_dir / 'traceability' / 'traceability.md'})"
    )


if __name__ == "__main__":
    main()
