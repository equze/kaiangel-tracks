#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создаёт audio_manifest.json по MP3-файлам в audios/*.

Ожидаемая структура (в каждой папке с режимом — подпапки по 10 треков):
    audios/
      start/1/*.mp3
      start/2/*.mp3
      random/1/*.mp3
      random/2/*.mp3
      beat/1/*.mp3
      rewind/1/*.mp3
      best/1/*.mp3
      best/2/*.mp3

Допускаются также MP3 прямо в папке режима для обратной совместимости.
В манифест записывается путь относительно папки режима, например:
    {"file": "2/oKAk_on-me.mp3", "artist": "oKAk", "title": "on me"}

Имя файла: ИСПОЛНИТЕЛЬ_НАЗВАНИЕ-ТРЕКА.mp3
Первый '_' отделяет исполнителя от названия, '-' заменяются пробелами.
Запускай из любой папки: пути вычисляются относительно этого скрипта.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
AUDIO_ROOT = ROOT / "audios"
OUTPUT_FILE = ROOT / "audio_manifest.json"
FOLDERS = ("start", "random", "beat", "rewind", "best")
AUDIO_EXTENSIONS = {".mp3"}
MAX_TRACKS_PER_NUMBERED_FOLDER = 10


def clean_part(value: str) -> str:
    """Заменяет дефисы пробелами и схлопывает повторные пробелы."""
    value = value.replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_filename(path: Path, relative_file: str) -> dict[str, str] | None:
    """Разбирает artist_track.mp3; разделителем считается первый '_'."""
    stem = path.stem
    if "_" not in stem:
        return None

    artist_raw, title_raw = stem.split("_", 1)
    artist = clean_part(artist_raw)
    title = clean_part(title_raw)
    if not artist or not title:
        return None

    return {"file": relative_file, "artist": artist, "title": title}


def natural_path_key(path: Path, root: Path) -> tuple[tuple[int, object], ...]:
    """Сортирует папки 1, 2, 3 ... 10 по числовому порядку."""
    parts = path.relative_to(root).parts
    result: list[tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            result.append((0, int(part)))
        else:
            result.append((1, part.casefold()))
    return tuple(result)


def scan_folder(folder_name: str) -> tuple[list[dict[str, str]], list[str]]:
    folder = AUDIO_ROOT / folder_name
    entries: list[dict[str, str]] = []
    warnings: list[str] = []

    if not folder.exists():
        warnings.append(f"Папка не найдена: {folder.relative_to(ROOT)}")
        return entries, warnings
    if not folder.is_dir():
        warnings.append(f"Путь не является папкой: {folder.relative_to(ROOT)}")
        return entries, warnings

    files = sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS),
        key=lambda p: natural_path_key(p, folder),
    )

    # Проверяем рекомендуемую структуру: audios/<mode>/<number>/ <= 10 MP3.
    numbered_counts: dict[str, int] = {}
    for path in files:
        relative = path.relative_to(folder)
        if len(relative.parts) == 1:
            warnings.append(
                f"Файл лежит прямо в audios/{folder_name}. Для удобной загрузки перемести его в подпапку, например {folder_name}/1/: {path.name}"
            )
        else:
            first_dir = relative.parts[0]
            if first_dir.isdigit():
                numbered_counts[first_dir] = numbered_counts.get(first_dir, 0) + 1
            else:
                warnings.append(
                    f"Подпапка должна называться числом (1, 2, 3...): {path.relative_to(ROOT)}"
                )
            if len(relative.parts) > 2:
                warnings.append(
                    f"Ожидается только один уровень подпапок (например {folder_name}/1/file.mp3): {path.relative_to(ROOT)}"
                )

    for number, count in sorted(numbered_counts.items(), key=lambda item: int(item[0])):
        if count > MAX_TRACKS_PER_NUMBERED_FOLDER:
            warnings.append(
                f"В audios/{folder_name}/{number} находится {count} MP3; максимум по правилам проекта — {MAX_TRACKS_PER_NUMBERED_FOLDER}."
            )

    seen: set[tuple[str, str]] = set()
    for path in files:
        relative_file = path.relative_to(folder).as_posix()
        parsed = parse_filename(path, relative_file)
        if parsed is None:
            warnings.append(
                f"Пропущен файл без формата artist_track.mp3: {path.relative_to(ROOT)}"
            )
            continue

        key = (parsed["artist"].casefold(), parsed["title"].casefold())
        if key in seen:
            warnings.append(
                f"Повтор пары исполнитель/трек в audios/{folder_name}: "
                f"{parsed['artist']} — {parsed['title']} ({relative_file})"
            )
        seen.add(key)
        entries.append(parsed)

    return entries, warnings


def main() -> int:
    manifest: dict[str, Any] = {}
    total = 0
    all_warnings: list[str] = []

    for folder_name in FOLDERS:
        entries, warnings = scan_folder(folder_name)
        manifest[folder_name] = entries
        total += len(entries)
        all_warnings.extend(warnings)
        print(f"audios/{folder_name}: {len(entries)} MP3")

    OUTPUT_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nГотово: {OUTPUT_FILE}")
    print(f"Всего MP3 добавлено в манифест: {total}")
    if all_warnings:
        print("\nПредупреждения:")
        for warning in all_warnings:
            print(f" - {warning}")
    else:
        print("Ошибок в именах и структуре папок не найдено.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
