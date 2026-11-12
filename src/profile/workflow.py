"""Application profile: the technology choices made once, then followed by every stage."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ..agents.decision_judge import DecisionJudge
from ..decisions import DecisionService
from ..interaction import UserInteraction
from ..models import DecisionOption, DecisionOutcome, DecisionProposal, DecisionRecord
from ..notes import RunNotes
from .catalog import (
    APP_TYPE_TOPIC, CLIENT_OPTIONS, CLIENT_TOPIC, DATABASE_OPTIONS, DATABASE_TOPIC, ORM_OPTIONS, ORM_TOPIC,
    SERVER_OPTIONS, SERVER_TOPIC, THREE_TIER,
)

PROFILE_STAGE = "profile"


class ApplicationProfile(BaseModel):
    app_type: str
    client: str
    server: str
    orm: str
    database: str
    decisions: list[DecisionRecord] = Field(default_factory=list)

    def summary(self) -> str:
        return f"{self.client} web client, {self.server} API server, {self.orm} ORM, {self.database} database"


def load_profile(output_dir: Path) -> Optional[tuple[ApplicationProfile, Path]]:
    files = sorted((output_dir / "profile").glob("profile_*.json"))
    if not files:
        return None
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    return ApplicationProfile.model_validate(data["profile"]), files[-1]


def match_option(options: list[DecisionOption], wanted: str) -> DecisionOption:
    """An option by name or unique prefix, e.g. 'node' or 'postgres'."""
    text = wanted.strip().lower()
    exact = [o for o in options if o.name.lower() == text]
    found = exact or [o for o in options if text and o.name.lower().startswith(text)]
    if len(found) != 1:
        raise ValueError(f"'{wanted}' does not identify one option; choose from: {', '.join(o.name for o in options)}")
    return found[0]


class ProfileWorkflow:
    """Each choice shows its options, the judge's recommendation, and asks the user; presets skip the question."""

    def __init__(self, interaction: UserInteraction, output_dir: Path, judge: DecisionJudge) -> None:
        self._io = interaction
        self._output_dir = output_dir
        self._decisions = DecisionService(judge, interaction)

    def run(
        self,
        requirement: str = "",
        presets: Optional[dict[str, str]] = None,
        existing: Optional[tuple[ApplicationProfile, Path]] = None,
    ) -> tuple[ApplicationProfile, Path]:
        """presets may hold 'client', 'server', 'orm' and 'database'."""
        presets = {k: v for k, v in (presets or {}).items() if v}
        if existing and not presets:
            self._io.show(f"\nCurrent profile: {existing[0].summary()}")
            if self._io.confirm("Keep this profile?"):
                return existing

        records = [self._fixed(APP_TYPE_TOPIC, THREE_TIER, "Only this application type is supported", [])]
        client = self._choose(CLIENT_TOPIC, "Technology of the web client", CLIENT_OPTIONS, presets.get("client"), requirement, records)
        server = self._choose(SERVER_TOPIC, "Technology of the API server", SERVER_OPTIONS, presets.get("server"), requirement, records)
        orm = self._choose(
            ORM_TOPIC, f"ORM connecting the {server.name} API server to the data", ORM_OPTIONS[server.name],
            presets.get("orm"), requirement, records,
        )
        database = self._choose(DATABASE_TOPIC, "Relational database of the data tier", DATABASE_OPTIONS, presets.get("database"), requirement, records)

        for number, record in enumerate(records, 1):
            record.id = f"PRF-{number}"
        profile = ApplicationProfile(
            app_type=THREE_TIER, client=client.name, server=server.name, orm=orm.name, database=database.name,
            decisions=records,
        )
        return self._save(profile)

    @staticmethod
    def _fixed(topic: str, chosen: str, context: str, options: list[DecisionOption]) -> DecisionRecord:
        return DecisionRecord(
            id="", stage=PROFILE_STAGE, topic=topic, context=context, options=options, chosen=chosen,
            outcome=DecisionOutcome.PRESET,
        )

    def _choose(
        self, topic: str, context: str, options: list[DecisionOption], preset: Optional[str],
        requirement: str, records: list[DecisionRecord],
    ) -> DecisionOption:
        if preset:
            picked = match_option(options, preset)
            records.append(self._fixed(topic, picked.name, context, options))
            return picked
        if len(options) == 1:
            records.append(self._fixed(topic, options[0].name, f"{context} (the only option for this stack)", options))
            return options[0]

        background = "A three-tier web application." + (f" Requirement: {requirement}" if requirement else "")
        proposal = DecisionProposal(topic=topic, context=context, options=options)
        names = {o.name: o for o in options}
        while True:
            (record,) = self._decisions.decide(PROFILE_STAGE, [proposal], background, [])
            if record.chosen in names:
                records.append(record)
                return names[record.chosen]
            self._io.show("Only the listed options are supported; please choose one of them.")

    def _save(self, profile: ApplicationProfile) -> tuple[ApplicationProfile, Path]:
        notes = RunNotes("Application Profile")
        notes.step("Fixed the application type: a three-tier web application (the only supported type)")
        notes.step("Chose the technology of each tier from the catalog; each choice shows the options evaluated")
        for record in profile.decisions:
            notes.decision(record)
            notes.step(f"{record.topic}: {record.chosen}")

        folder = self._output_dir / "profile"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps({"profile": profile.model_dump(mode="json")}, indent=2), encoding="utf-8")
        path.with_name(f"{path.stem}.notes.md").write_text(notes.to_markdown(), encoding="utf-8")
        self._io.show(f"\nApplication profile saved to {path}\n  {profile.summary()}")
        return profile, path
