#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер текстов песен с Genius.
Читает tracks.txt -> ищет каждый трек на Genius -> чистит -> пишет в texts.txt

Установка:
    pip install lyricsgenius

Токен получить тут: https://genius.com/api-clients
"""

import re
import sys
import time

try:
    from lyricsgenius import Genius
except ImportError:
    print("Нет библиотеки lyricsgenius. Установи: pip install lyricsgenius")
    sys.exit(1)


# ================== НАСТРОЙКИ ==================
GENIUS_TOKEN = "LhOCdBClVQZAca_6faQR5sEdwGygYsBfUOJ8Y1rlzYqIB0yEskNqL3ES-KBkyppg"
TRACKS_FILE  = "tracks.txt"
OUTPUT_FILE  = "texts.txt"
DELAY_SEC    = 0.7
# ================================================


# ------------------------------------------------------------------
# ПАРСИНГ tracks.txt
# ------------------------------------------------------------------
def parse_tracks_file(path):
    """Возвращает список (artist, title) из tracks.txt."""
    tracks = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if re.match(r"^-{3,}", line):
                continue

            parts = re.split(r"\s+-\s+", line)

            # Убираем хвост: MM:SS, 1.13M/510K, файл обложки
            while parts:
                last = parts[-1]
                if re.match(r"^\d{1,2}:\d{2}$", last):
                    parts.pop(); continue
                if re.match(r"^\d+(?:[.,]\d+)?\s*[KMGkmg]$", last):
                    parts.pop(); continue
                if re.search(r"\.(png|jpe?g|webp|gif|avif|bmp|svg)$", last, re.I):
                    parts.pop(); continue
                break

            if len(parts) < 2:
                continue

            artist = parts[0].strip()
            title  = " - ".join(parts[1:]).strip()
            tracks.append((artist, title))
    return tracks


# ------------------------------------------------------------------
# ЧИСТКА ТЕКСТА
# ------------------------------------------------------------------
SECTION_RE = re.compile(r"^\s*\[.*\]\s*$")

def clean_lyrics(lyrics):
    """
    Чистит текст песни:
      - убирает заголовки секций [Припев] / [Chorus] / [Куплет 1] и т.п.;
      - убирает блок 'You might also like' + следующие 6 строк (3 рекомендации × 2 строки: title + artist);
      - убирает пустые строки;
      - убирает первую служебную строку вида 'N Contributors...Lyrics';
      - убирает дубликаты строк (оставляет первое вхождение);
      - убирает хвост '...NNNEmbed' в самом конце текста.
    """
    if not lyrics:
        return ""

    # Убираем хвост вида "12Embed" в самом конце
    lyrics = re.sub(r"\d*Embed\s*$", "", lyrics)

    lines = lyrics.split("\n")
    cleaned = []
    seen = set()

    skip_left = 0  # сколько строк пропустить (после "You might also like")

    for idx, raw in enumerate(lines):
        line = raw.strip()

        # 1. Первая строка — служебная ("N Contributors...Lyrics") — вырезаем
        if idx == 0 and ("Lyrics" in line and ("Contributors" in line or "Translations" in line or "Contributors" in line)):
            continue
        # более общий случай
        if idx == 0 and re.search(r"\d+\s+Contributors?.*Lyrics", line):
            continue

        # 2. Пропускаем строки-рекомендации после "You might also like"
        if skip_left > 0:
            if not line:
                continue
            skip_left -= 1
            continue

        # 3. Встретили "You might also like" — ставим пропуск 6 строк
        if "You might also like" in line:
            skip_left = 6
            continue

        # 4. Пустая строка — выкидываем
        if not line:
            continue

        # 5. Заголовок секции [Chorus], [Куплет 1], [Припев], [Bridge] — выкидываем
        if SECTION_RE.match(line):
            continue

        # 6. Дубликат (точно совпадающая строка уже была) — выкидываем
        if line in seen:
            continue

        seen.add(line)
        cleaned.append(line)

    return "\n".join(cleaned)


# ------------------------------------------------------------------
# ОСНОВНОЙ ПРОГОН
# ------------------------------------------------------------------
def main():
    if not GENIUS_TOKEN or GENIUS_TOKEN == "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН":
        print("Укажи свой Genius API token в переменной GENIUS_TOKEN.")
        print("Получить: https://genius.com/api-clients")
        return

    genius = Genius(GENIUS_TOKEN)
    genius.verbose = False
    genius.remove_section_headers = False  # отключаем встроенную — чистим сами
    genius.timeout = 20
    genius.retries = 3

    tracks = parse_tracks_file(TRACKS_FILE)
    print(f"Найдено треков в {TRACKS_FILE}: {len(tracks)}")
    print(f"Результат пишется в {OUTPUT_FILE}\n")

    out = open(OUTPUT_FILE, "w", encoding="utf-8")

    ok = 0
    errors = []

    try:
        for i, (artist, title) in enumerate(tracks, 1):
            print(f"[{i}/{len(tracks)}] {artist} — {title}")
            try:
                song = genius.search_song(title, artist)
            except Exception as e:
                errors.append((artist, title, f"request: {e}"))
                print(f"    ошибка: {e}")
                time.sleep(DELAY_SEC)
                continue

            if not song or not song.lyrics:
                errors.append((artist, title, "не найдено"))
                print("    не найдено")
                time.sleep(DELAY_SEC)
                continue

            cleaned = clean_lyrics(song.lyrics)
            if not cleaned:
                errors.append((artist, title, "пустой текст"))
                print("    пустой текст после чистки")
                time.sleep(DELAY_SEC)
                continue

            out.write(f"- {artist} - {title}\n")
            out.write(cleaned + "\n\n")
            out.flush()

            ok += 1
            print(f"    ok ({len(cleaned.splitlines())} строк)")
            time.sleep(DELAY_SEC)
    finally:
        out.close()

    print("\n=== Готово ===")
    print(f"Успешно: {ok}")
    print(f"Ошибок:  {len(errors)}")
    if errors:
        print("\nНе удалось получить:")
        for a, t, e in errors:
            print(f"  • {a} — {t} ({e})")


# ------------------------------------------------------------------
# БЫСТРЫЙ ТЕСТ — проверить чистку на примере, без запросов к Genius
# ------------------------------------------------------------------
def _test_clean():
    sample = """[Припев]
На мне Chrome Hearts, и на нём по-тихой ice
Подойду один и сделаю ей surpri-ise
Она просто oh my! За неё я готов die!
На улице ща grim, но её глаза sunshine

[Куплет 1]
Я хочу с тобой wake up, хочу с тобой stay up
Everyday мы in the club, хоть мы и не ходим в club
Я твой emotional ****, ты моя afterparty swag
Давай дэнсить нон-стоп, давай дэнсить нон-стоп
Давай дэнсить нон-стоп
Для тебя нужны firefighters
Нас тянет так, да, это science
Я обниму тебя на silence, я обниму тебя на shh… (В тиши— в тишине)

[Припев]
На мне Chrome Hearts, и на нём по-тихой ice (У-у)
Подойду один и сделаю ей surpri-ise
Она просто oh my! За неё я готов die!
На улице ща grim, но её глаза sunshine

[Куплет 2]
А-а-а-а, блин, прости меня (Сорри)
Я high-key ненормальный, но ты так вовлечена
Я обниму тебя как ветер, похуй на соседей
Ты сёрвишь драму в ар-деко силуэте
You might also like
Madam 2
Kai Angel
STFU!
Kai Angel
does it hurt?
Kai Angel
[Преддроп]
Chrome Hearts, и на нём по-тихой ice
Подойду один, сделаю surprise
Не обижайся на меня, я просто angel in disguise
Я не хотел делать evil хуйню

[Дроп]
На мне Chrome Hearts, и на нём по-тихой ice (У-у)
Подойду один и сделаю ей surpri-ise
Она просто oh my! За неё я готов die!
На улице ща grim, но её глаза sunshine

[Аутро]
На мне Chrome Hearts, Chro-Chro-Chro-Chrome— Chrome Hearts
Chromе Hearts, и на нём по-тихой ice, по-тихой ice
Подойду один и сдела— подойду один
И сделаю ей surpri-isе, surpri-ise"""
    print(clean_lyrics(sample))



#_test_clean()
main()