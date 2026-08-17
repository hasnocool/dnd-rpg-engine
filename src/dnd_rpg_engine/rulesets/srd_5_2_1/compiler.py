# src/dnd_rpg_engine/rulesets/srd_5_2_1/compiler.py
from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from dnd_rpg_engine.rulesets.srd_5_2_1.catalog import CLASSES, FEATS
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import (
    CatalogSection,
    ClassFeatureEntry,
    ClassProgressionLevel,
    CompilationDiagnostic,
    CompiledCatalogManifest,
    DiceExpression,
    FeatCatalogEntry,
    MagicItemCatalogEntry,
    MonsterCatalogEntry,
    SourceRef,
    SpellCatalogEntry,
    SubclassDefinition,
)
from dnd_rpg_engine.rulesets.srd_5_2_1.rules import proficiency_bonus
from dnd_rpg_engine.rulesets.srd_5_2_1.source import OFFICIAL_SRD_SOURCE
from dnd_rpg_engine.rulesets.srd_5_2_1.toolbox import (
    ENCOUNTER_BUDGETS,
    ENVIRONMENTAL_RULES,
    TERRAIN_TRAVEL_RULES,
    TRAVEL_PACES,
)


class SRDCompilerError(RuntimeError):
    pass


class SRDCompilerDependencyError(SRDCompilerError):
    pass


@dataclass(frozen=True, slots=True)
class SRDDocument:
    pages: tuple[str, ...]
    source_sha256: str

    @classmethod
    def from_pages(cls, pages: Iterable[str], *, source_sha256: str = "synthetic") -> "SRDDocument":
        return cls(tuple(pages), source_sha256)

    def page(self, printed_page: int) -> str:
        index = printed_page - 1
        return self.pages[index] if 0 <= index < len(self.pages) else ""

    def range_text(self, start: int, end: int) -> list[tuple[int, str]]:
        return [(page, self.page(page)) for page in range(start, end + 1) if self.page(page)]


SUBCLASSES: dict[str, tuple[str, str, int]] = {
    "barbarian": ("path_of_the_berserker", "Path of the Berserker", 30),
    "bard": ("college_of_lore", "College of Lore", 35),
    "cleric": ("life_domain", "Life Domain", 40),
    "druid": ("circle_of_the_land", "Circle of the Land", 46),
    "fighter": ("champion", "Champion", 49),
    "monk": ("warrior_of_the_open_hand", "Warrior of the Open Hand", 52),
    "paladin": ("oath_of_devotion", "Oath of Devotion", 56),
    "ranger": ("hunter", "Hunter", 61),
    "rogue": ("thief", "Thief", 64),
    "sorcerer": ("draconic_sorcery", "Draconic Sorcery", 69),
    "warlock": ("fiend_patron", "Fiend Patron", 76),
    "wizard": ("evoker", "Evoker", 82),
}

_CLASS_END_PAGE = {
    "barbarian": 30, "bard": 35, "cleric": 40, "druid": 46, "fighter": 49, "monk": 52,
    "paladin": 56, "ranger": 61, "rogue": 64, "sorcerer": 69, "warlock": 76, "wizard": 82,
}

_FULL_CASTER_SLOT_TABLE: tuple[tuple[int, ...], ...] = (
    (),
    (2,),
    (3,),
    (4, 2),
    (4, 3),
    (4, 3, 2),
    (4, 3, 3),
    (4, 3, 3, 1),
    (4, 3, 3, 2),
    (4, 3, 3, 3, 1),
    (4, 3, 3, 3, 2),
    (4, 3, 3, 3, 2, 1),
    (4, 3, 3, 3, 2, 1),
    (4, 3, 3, 3, 2, 1, 1),
    (4, 3, 3, 3, 2, 1, 1),
    (4, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 2, 1, 1, 1, 1),
    (4, 3, 3, 3, 3, 1, 1, 1, 1),
    (4, 3, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 3, 2, 2, 1, 1),
)
_FULL_CASTERS = {"bard", "cleric", "druid", "sorcerer", "wizard"}
_HALF_CASTERS = {"paladin", "ranger"}

_SPELL_META_RE = re.compile(r"^(?:Level\s+([1-9])\s+([A-Za-z]+)|([A-Za-z]+)\s+Cantrip)\s*\(([^)]+)\)\s*$", re.I)
_FIELD_RE = re.compile(r"^(Casting Time|Range|Components|Duration):\s*(.*)$", re.I)
_SAVE_RE = re.compile(r"\b(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+Saving Throw\b", re.I)
_DAMAGE_RE = re.compile(r"\b(\d+d\d+(?:\s*[+-]\s*\d+)?)\s+(Acid|Cold|Fire|Force|Lightning|Necrotic|Poison|Psychic|Radiant|Thunder)\s+damage\b", re.I)
_HEAL_RE = re.compile(r"\b(?:regains?|restore(?:s|d)?)\s+(\d+d\d+(?:\s*[+-]\s*\d+)?)\s+(?:Hit Points|HP)\b", re.I)
_MONSTER_TYPE_RE = re.compile(r"^(Tiny|Small|Medium|Large|Huge|Gargantuan)\s+(.+?),\s+(.+)$")
_AC_RE = re.compile(r"^AC\s+(\d+).*?Initiative\s+([+−-]?\d+)")
_HP_RE = re.compile(r"^HP\s+(\d+)(?:\s+\(([^)]+)\))?")
_CR_RE = re.compile(r"^CR\s+([^\s]+)\s+\(XP\s+([\d,]+);\s+PB\s+[+−-]?\d+\)")
_ABILITY_RE = re.compile(r"\b(Str|Dex|Con|Int|Wis|Cha)\s+(\d+)\s+([+−-]?\d+)\s+([+−-]?\d+)", re.I)
_MAGIC_META_RE = re.compile(
    r"^(Armor|Potion|Ring|Rod|Scroll|Staff|Wand|Wondrous Item)(?:\s+\([^)]*\))?,\s*([^\n]+)$",
    re.I,
)
_RARITY_RE = re.compile(r"\b(Common|Uncommon|Rare|Very Rare|Legendary|Artifact)\b", re.I)
_CHARGES_RE = re.compile(r"\b(?:has|with)\s+(\d+)\s+charges?\b", re.I)
_FEATURE_RE = re.compile(r"^Level\s+(\d{1,2}):\s+(.+?)\s*$", re.I)
_DISALLOWED_FEATURE_TERMS = ("weapon",)


async def load_pdf_document(path: str | Path) -> SRDDocument:
    return await asyncio.to_thread(_load_pdf_document_sync, Path(path))


def _load_pdf_document_sync(path: Path) -> SRDDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SRDCompilerDependencyError("install the 'srd' extra to compile the official PDF: pip install -e '.[srd]'") from exc
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-"):
        raise SRDCompilerError("source is not a PDF")
    reader = PdfReader(str(path))
    pages = tuple((page.extract_text() or "") for page in reader.pages)
    return SRDDocument(pages=pages, source_sha256=hashlib.sha256(raw).hexdigest())


async def compile_srd_catalog(pdf_path: str | Path, database_path: str | Path) -> CompiledCatalogManifest:
    document = await load_pdf_document(pdf_path)
    return await compile_document(document, database_path)


async def compile_document(document: SRDDocument, database_path: str | Path) -> CompiledCatalogManifest:
    _validate_document(document)
    diagnostics: list[CompilationDiagnostic] = []

    spells = parse_spells(document, diagnostics)
    class_features = parse_class_features(document, diagnostics)
    subclasses = build_subclasses(class_features)
    progressions = build_class_progressions(class_features)
    feats = build_feats()
    magic_items = parse_magic_items(document, diagnostics)
    monsters = parse_monsters(document, diagnostics)

    store = SRDCatalogStore(database_path)
    await store.initialize()
    sections = {
        CatalogSection.SPELLS.value: [row.model_dump(mode="json") for row in spells],
        CatalogSection.CLASS_FEATURES.value: [row.model_dump(mode="json") for row in class_features],
        CatalogSection.CLASS_PROGRESSIONS.value: [row.model_dump(mode="json") | {"id": row.id, "name": row.id} for row in progressions],
        CatalogSection.SUBCLASSES.value: [row.model_dump(mode="json") for row in subclasses],
        CatalogSection.FEATS.value: [row.model_dump(mode="json") for row in feats],
        CatalogSection.MAGIC_ITEMS.value: [row.model_dump(mode="json") for row in magic_items],
        CatalogSection.MONSTERS.value: [row.model_dump(mode="json") for row in monsters],
        CatalogSection.TRAVEL.value: [
            *(row.model_dump(mode="json") | {"name": row.id} for row in TRAVEL_PACES.values()),
            *(row.model_dump(mode="json") | {"name": row.id} for row in TERRAIN_TRAVEL_RULES.values()),
        ],
        CatalogSection.ENVIRONMENT.value: [row.model_dump(mode="json") for row in ENVIRONMENTAL_RULES.values()],
        CatalogSection.ENCOUNTERS.value: [
            row.model_dump(mode="json") | {"id": f"level_{row.level}", "name": f"Level {row.level}"}
            for row in ENCOUNTER_BUDGETS.values()
        ],
    }
    for section, entries in sections.items():
        await store.replace_section(section, entries)

    manifest = CompiledCatalogManifest(
        source_sha256=document.source_sha256,
        source_pages=len(document.pages),
        compiled_at=datetime.now(UTC).isoformat(),
        section_counts={section: len(entries) for section, entries in sections.items()},
        omitted_sections={
            "weapon_catalog_and_masteries": "not compiled by this build",
            "monster_actions_and_gear": "runtime catalog keeps non-action stat data only",
            "long_form_prose": "mechanics are normalized; source prose stays in the official SRD",
        },
        diagnostics=diagnostics,
        provenance={
            "release_name": OFFICIAL_SRD_SOURCE.release_name,
            "release_page": OFFICIAL_SRD_SOURCE.release_page,
            "pdf_url": OFFICIAL_SRD_SOURCE.pdf_url,
            "license": OFFICIAL_SRD_SOURCE.license_id,
        },
    )
    await store.put_manifest(manifest)
    return manifest


def _validate_document(document: SRDDocument) -> None:
    if len(document.pages) < 350:
        raise SRDCompilerError("document is too short to be SRD 5.2.1")
    head = "\n".join(document.pages[:4])
    if "System Reference Document 5.2.1" not in head:
        raise SRDCompilerError("document does not identify itself as System Reference Document 5.2.1")


def parse_spells(document: SRDDocument, diagnostics: list[CompilationDiagnostic] | None = None) -> list[SpellCatalogEntry]:
    diagnostics = diagnostics if diagnostics is not None else []
    entries: list[SpellCatalogEntry] = []
    seen: set[str] = set()
    for page_number, text in document.range_text(107, 175):
        lines = _clean_lines(text)
        index = 0
        while index + 1 < len(lines):
            title = lines[index]
            match = _SPELL_META_RE.match(lines[index + 1])
            if not match or not _plausible_title(title):
                index += 1
                continue
            level = int(match.group(1) or 0)
            school = (match.group(2) or match.group(3) or "").title()
            classes = tuple(sorted(_slug(part) for part in match.group(4).split(",") if part.strip()))
            block_end = _next_spell_header(lines, index + 2)
            block = lines[index:block_end]
            fields = _extract_named_fields(block[2:])
            block_text = " ".join(block[2:])
            entry_id = _slug(title)
            if entry_id in seen:
                index = block_end
                continue
            seen.add(entry_id)
            damage = tuple(
                DiceExpression(expression=formula.replace(" ", ""), damage_type=damage_type.lower())
                for formula, damage_type in _DAMAGE_RE.findall(block_text)
            )
            healing = tuple(formula.replace(" ", "") for formula in _HEAL_RE.findall(block_text))
            save_match = _SAVE_RE.search(block_text)
            lower = block_text.lower()
            attack_kind = "ranged_spell" if "ranged spell attack" in lower else "melee_spell" if "melee spell attack" in lower else None
            duration = fields.get("duration", "")
            casting_time = fields.get("casting time", "")
            components = tuple(part.strip() for part in fields.get("components", "").split(",") if part.strip())
            conditions = tuple(sorted(condition for condition in _CONDITIONS if re.search(rf"\b{re.escape(condition)}\b", lower)))
            area_tags = tuple(sorted(shape for shape in _AREA_TAGS if re.search(rf"\b{shape}\b", lower)))
            entries.append(
                SpellCatalogEntry(
                    id=entry_id,
                    name=title,
                    level=level,
                    school=school,
                    classes=classes,
                    casting_time=casting_time,
                    range=fields.get("range", ""),
                    components=components,
                    duration=duration,
                    concentration="concentration" in duration.lower(),
                    ritual="ritual" in casting_time.lower() or "ritual" in lines[index + 1].lower(),
                    save_ability=save_match.group(1).lower() if save_match else None,
                    attack_kind=attack_kind,
                    damage=damage,
                    healing=healing,
                    conditions=conditions,
                    area_tags=area_tags,
                    source=SourceRef(source_page=page_number, source_section="Spells"),
                    mechanics_hash=_hash_text(block_text),
                )
            )
            index = block_end
    if len(entries) < 100:
        diagnostics.append(CompilationDiagnostic(severity="warning", section="spells", message=f"only {len(entries)} spell records parsed; inspect PDF extraction quality"))
    return entries


def parse_class_features(document: SRDDocument, diagnostics: list[CompilationDiagnostic] | None = None) -> list[ClassFeatureEntry]:
    diagnostics = diagnostics if diagnostics is not None else []
    rows: list[ClassFeatureEntry] = []
    for class_id, class_def in CLASSES.items():
        start, end = class_def.source_page, _CLASS_END_PAGE[class_id]
        text_by_page = document.range_text(start, end)
        subclass_id = SUBCLASSES[class_id][0]
        for page_number, text in text_by_page:
            lines = _clean_lines(text)
            for i, line in enumerate(lines):
                match = _FEATURE_RE.match(line)
                if not match:
                    continue
                level = int(match.group(1))
                name = _normalize_feature_name(match.group(2))
                if not 1 <= level <= 20 or any(term in name.lower() for term in _DISALLOWED_FEATURE_TERMS):
                    continue
                context = " ".join(lines[i : min(len(lines), i + 8)])
                is_subclass = page_number >= SUBCLASSES[class_id][2] and _slug(name) not in {"subclass"}
                feature_id = f"{class_id}.{_slug(name)}"
                rows.append(
                    ClassFeatureEntry(
                        id=feature_id,
                        name=name,
                        class_id=class_id,
                        level=level,
                        subclass_id=subclass_id if is_subclass else None,
                        tags=("subclass",) if is_subclass else (),
                        source=SourceRef(source_page=page_number, source_section=f"Classes/{class_def.name}"),
                        mechanics_hash=_hash_text(context),
                    )
                )
    rows = _dedupe_model_rows(rows)
    if len(rows) < 40:
        diagnostics.append(CompilationDiagnostic(severity="warning", section="class_features", message=f"only {len(rows)} level-feature headings parsed; table-only features may require manual catalog augmentation"))
    return rows


def build_subclasses(features: list[ClassFeatureEntry]) -> list[SubclassDefinition]:
    result: list[SubclassDefinition] = []
    for class_id, (subclass_id, name, page) in SUBCLASSES.items():
        feature_ids = tuple(row.id for row in features if row.subclass_id == subclass_id)
        result.append(SubclassDefinition(id=subclass_id, name=name, class_id=class_id, source=SourceRef(source_page=page, source_section="Classes"), feature_ids=feature_ids))
    return result


def build_class_progressions(features: list[ClassFeatureEntry]) -> list[ClassProgressionLevel]:
    result: list[ClassProgressionLevel] = []
    for class_id in CLASSES:
        for level in range(1, 21):
            core_features = tuple(row.id for row in features if row.class_id == class_id and row.level == level and row.subclass_id is None)
            subclass_features = tuple(row.id for row in features if row.class_id == class_id and row.level == level and row.subclass_id is not None)
            result.append(
                ClassProgressionLevel(
                    class_id=class_id,
                    level=level,
                    proficiency_bonus=proficiency_bonus(level),
                    feature_ids=core_features,
                    subclass_feature_ids=subclass_features,
                    spell_slots=_spell_slots_for(class_id, level),
                )
            )
    return result


def build_feats() -> list[FeatCatalogEntry]:
    return [
        FeatCatalogEntry(
            id=row.id,
            name=row.name,
            category=row.category,
            repeatable=row.repeatable,
            source=SourceRef(source_page=row.source_page, source_section="Feats"),
        )
        for row in FEATS.values()
    ]


def parse_magic_items(document: SRDDocument, diagnostics: list[CompilationDiagnostic] | None = None) -> list[MagicItemCatalogEntry]:
    diagnostics = diagnostics if diagnostics is not None else []
    entries: list[MagicItemCatalogEntry] = []
    seen: set[str] = set()
    for page_number, text in document.range_text(209, 253):
        lines = _clean_lines(text)
        for index in range(len(lines) - 1):
            name = lines[index]
            meta = _MAGIC_META_RE.match(lines[index + 1])
            if not meta or not _plausible_title(name):
                continue
            category = meta.group(1).title()
            metadata = meta.group(2)
            item_id = _slug(name)
            if item_id in seen:
                continue
            seen.add(item_id)
            end = _next_magic_header(lines, index + 2)
            block_text = " ".join(lines[index + 2 : end])
            rarity_match = _RARITY_RE.search(metadata)
            charges_match = _CHARGES_RE.search(block_text)
            entries.append(
                MagicItemCatalogEntry(
                    id=item_id,
                    name=name,
                    category=category,
                    rarity=rarity_match.group(1).lower().replace(" ", "_") if rarity_match else None,
                    attunement="attunement" in metadata.lower(),
                    charges=int(charges_match.group(1)) if charges_match else None,
                    tags=tuple(sorted(tag for tag in ("consumable", "sentient", "cursed") if tag in block_text.lower())),
                    source=SourceRef(source_page=page_number, source_section="Magic Items"),
                    mechanics_hash=_hash_text(metadata + " " + block_text),
                )
            )
    if len(entries) < 30:
        diagnostics.append(CompilationDiagnostic(severity="warning", section="magic_items", message=f"only {len(entries)} non-weapon magic item records parsed"))
    return entries


def parse_monsters(document: SRDDocument, diagnostics: list[CompilationDiagnostic] | None = None) -> list[MonsterCatalogEntry]:
    diagnostics = diagnostics if diagnostics is not None else []
    entries: list[MonsterCatalogEntry] = []
    seen: set[str] = set()
    for page_number, text in document.range_text(258, min(364, len(document.pages))):
        lines = _clean_lines(text)
        for index, line in enumerate(lines):
            type_match = _MONSTER_TYPE_RE.match(line)
            if not type_match or index < 1:
                continue
            name = lines[index - 1]
            if not _plausible_title(name) or name in {"Traits", "Actions", "Reactions", "Bonus Actions"}:
                continue
            block = _monster_preamble(lines, index)
            cr_line = next((part for part in block if _CR_RE.match(part)), None)
            if cr_line is None:
                continue
            monster_id = _slug(name)
            if monster_id in seen:
                continue
            ac_line = next((part for part in block if _AC_RE.match(part)), "")
            hp_line = next((part for part in block if _HP_RE.match(part)), "")
            speed_line = next((part for part in block if part.startswith("Speed ")), "")
            ac_match = _AC_RE.match(ac_line)
            hp_match = _HP_RE.match(hp_line)
            cr_match = _CR_RE.match(cr_line)
            if cr_match is None:
                continue
            ability_scores: dict[str, int] = {}
            saves: dict[str, int] = {}
            for part in block:
                for ability, score, _modifier, save in _ABILITY_RE.findall(part):
                    key = ability.lower()
                    ability_scores[key] = int(score)
                    saves[key] = _signed_int(save)
            sections = _monster_named_sections(block)
            stat_hash_text = " ".join(part for part in block if not part.startswith("Gear "))
            entries.append(
                MonsterCatalogEntry(
                    id=monster_id,
                    name=name,
                    size=type_match.group(1).lower(),
                    creature_type=type_match.group(2),
                    alignment=type_match.group(3),
                    armor_class=int(ac_match.group(1)) if ac_match else None,
                    initiative=_signed_int(ac_match.group(2)) if ac_match else None,
                    hit_points=int(hp_match.group(1)) if hp_match else None,
                    hit_points_formula=hp_match.group(2) if hp_match else None,
                    speed=speed_line.removeprefix("Speed ") if speed_line else None,
                    abilities=ability_scores,
                    saves=saves,
                    challenge_rating=cr_match.group(1),
                    xp=int(cr_match.group(2).replace(",", "")),
                    resistances=_split_values(sections.get("Resistances", "")),
                    immunities=_split_values(sections.get("Immunities", "")),
                    vulnerabilities=_split_values(sections.get("Vulnerabilities", "")),
                    senses=_split_values(sections.get("Senses", ""), semicolon_only=True),
                    languages=_split_values(sections.get("Languages", ""), semicolon_only=True),
                    skills=_parse_bonus_map(sections.get("Skills", "")),
                    source=SourceRef(source_page=page_number, source_section="Monsters"),
                    stat_block_hash=_hash_text(stat_hash_text),
                )
            )
            seen.add(monster_id)
    if len(entries) < 100:
        diagnostics.append(CompilationDiagnostic(severity="warning", section="monsters", message=f"only {len(entries)} stat blocks parsed; inspect PDF extraction quality"))
    return entries


def _spell_slots_for(class_id: str, level: int) -> tuple[int, ...]:
    if class_id in _FULL_CASTERS:
        return _FULL_CASTER_SLOT_TABLE[level]
    if class_id in _HALF_CASTERS:
        effective = max(1, (level + 1) // 2)
        return _FULL_CASTER_SLOT_TABLE[effective]
    if class_id == "warlock":
        pact_level = min(5, (level + 1) // 2)
        count = 1 if level == 1 else 2 if level <= 10 else 3 if level <= 16 else 4
        return tuple(count if slot_level == pact_level else 0 for slot_level in range(1, 6))
    return ()


def _next_spell_header(lines: list[str], start: int) -> int:
    for i in range(start, len(lines) - 1):
        if _plausible_title(lines[i]) and _SPELL_META_RE.match(lines[i + 1]):
            return i
    return len(lines)


def _next_magic_header(lines: list[str], start: int) -> int:
    for i in range(start, len(lines) - 1):
        if _plausible_title(lines[i]) and _MAGIC_META_RE.match(lines[i + 1]):
            return i
    return len(lines)


def _monster_preamble(lines: list[str], type_index: int) -> list[str]:
    result = [lines[type_index]]
    for part in lines[type_index + 1 :]:
        if part in {"Traits", "Actions", "Reactions", "Bonus Actions", "Legendary Actions"}:
            break
        result.append(part)
        if _CR_RE.match(part):
            break
    return result


def _monster_named_sections(block: list[str]) -> dict[str, str]:
    names = ("Skills", "Resistances", "Immunities", "Vulnerabilities", "Senses", "Languages")
    result: dict[str, str] = {}
    for line in block:
        for name in names:
            if line.startswith(name + " "):
                result[name] = line[len(name) + 1 :].strip()
    return result


def _parse_bonus_map(value: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for match in re.finditer(r"([A-Za-z ]+?)\s+([+−-]\d+)(?:,|$)", value):
        result[_slug(match.group(1))] = _signed_int(match.group(2))
    return result


def _split_values(value: str, *, semicolon_only: bool = False) -> tuple[str, ...]:
    if not value or value.lower() == "none":
        return ()
    separator = ";" if semicolon_only else r"[,;]"
    return tuple(part.strip() for part in re.split(separator, value) if part.strip())


def _extract_named_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines[:10]:
        match = _FIELD_RE.match(line)
        if match:
            fields[match.group(1).lower()] = match.group(2).strip()
    return fields


def _clean_lines(text: str) -> list[str]:
    text = text.replace("\u00ad", "").replace("\u2011", "-").replace("\u2212", "-")
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _plausible_title(value: str) -> bool:
    if len(value) < 2 or len(value) > 90 or ":" in value or value.endswith("."):
        return False
    return bool(re.match(r"^[A-Z][A-Za-z0-9'’+ ,()\-]+$", value))


def _normalize_feature_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().rstrip(".")


def _slug(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _signed_int(value: str) -> int:
    return int(value.replace("−", "-"))


def _dedupe_model_rows(rows: list[ClassFeatureEntry]) -> list[ClassFeatureEntry]:
    seen: set[str] = set()
    result: list[ClassFeatureEntry] = []
    for row in rows:
        key = f"{row.id}:{row.level}:{row.subclass_id or ''}"
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


_CONDITIONS = {
    "blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled", "incapacitated",
    "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious",
}
_AREA_TAGS = {"cone", "cube", "cylinder", "emanation", "line", "sphere"}
