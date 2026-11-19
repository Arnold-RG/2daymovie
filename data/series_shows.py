"""Curated TV series with on-site official trailer embeds."""

from __future__ import annotations

SERIES_SHOWS: list[dict] = [
    {"title": 'Neon Genesis Evangelion', "start": 1995, "end": 1995},
    {"title": 'Cowboy Bebop', "start": 1998, "end": 1999},
    {"title": 'One Piece', "start": 1999, "end": None},
    {"title": 'Curb Your Enthusiasm', "start": 2000, "end": 2024},
    {"title": 'Gilmore Girls', "start": 2000, "end": 2007},
    {"title": '24', "start": 2001, "end": 2010},
    {"title": 'Six Feet Under', "start": 2001, "end": 2005},
    {"title": 'The Shield', "start": 2002, "end": 2008},
    {"title": 'The Wire', "start": 2002, "end": 2008},
    {"title": 'Arrested Development', "start": 2003, "end": 2019},
    {"title": 'Deadwood', "start": 2004, "end": 2006},
    {"title": 'Lost', "start": 2004, "end": 2010},
    {"title": 'Friday Night Lights', "start": 2006, "end": 2011},
    {"title": 'Midnight Diner', "start": 2009, "end": 2019},
    {"title": 'Bino and Fino', "start": 2010, "end": None},
    {"title": 'Borgen', "start": 2010, "end": 2022},
    {"title": 'Sherlock', "start": 2010, "end": 2017},
    {"title": 'Empresses in the Palace', "start": 2011, "end": 2012},
    {"title": 'The Bridge', "start": 2011, "end": 2018},
    {"title": 'Line of Duty', "start": 2012, "end": 2021},
    {"title": 'Broadchurch', "start": 2013, "end": 2017},
    {"title": 'Peaky Blinders', "start": 2013, "end": 2022},
    {"title": 'Happy Valley', "start": 2014, "end": 2023},
    {"title": 'Call My Agent!', "start": 2015, "end": 2020},
    {"title": 'Club de Cuervos', "start": 2015, "end": 2019},
    {"title": 'Narcos', "start": 2015, "end": 2017},
    {"title": 'Nirvana in Fire', "start": 2015, "end": 2015},
    {"title": 'Reply 1988', "start": 2015, "end": 2016},
    {"title": '3%', "start": 2016, "end": 2020},
    {"title": 'Fleabag', "start": 2016, "end": 2019},
    {"title": 'Westworld', "start": 2016, "end": 2022},
    {"title": 'Babylon Berlin', "start": 2017, "end": None},
    {"title": 'Dark', "start": 2017, "end": 2020},
    {"title": 'Money Heist', "start": 2017, "end": 2021},
    {"title": 'Killing Eve', "start": 2018, "end": 2022},
    {"title": 'Mr. Sunshine', "start": 2018, "end": 2018},
    {"title": 'My Mister', "start": 2018, "end": 2018},
    {"title": 'Sacred Games', "start": 2018, "end": 2019},
    {"title": 'Sky Castle', "start": 2018, "end": 2019},
    {"title": 'Story of Yanxi Palace', "start": 2018, "end": 2018},
    {"title": 'Chernobyl', "start": 2019, "end": 2019},
    {"title": 'Crash Landing on You', "start": 2019, "end": 2020},
    {"title": 'Delhi Crime', "start": 2019, "end": None},
    {"title": 'Demon Slayer: Kimetsu no Yaiba', "start": 2019, "end": None},
    {"title": 'Kingdom', "start": 2019, "end": 2021},
    {"title": 'Kota Factory', "start": 2019, "end": 2021},
    {"title": 'Made in Heaven', "start": 2019, "end": None},
    {"title": 'Alice in Borderland', "start": 2020, "end": None},
    {"title": 'Blood & Water', "start": 2020, "end": None},
    {"title": 'Dark Desire', "start": 2020, "end": 2022},
    {"title": 'Followers', "start": 2020, "end": 2020},
    {"title": "It's Okay to Not Be Okay", "start": 2020, "end": 2020},
    {"title": "Kings of Jo'burg", "start": 2020, "end": None},
    {"title": 'Queen Sono', "start": 2020, "end": 2020},
    {"title": 'D.P.', "start": 2021, "end": 2023},
    {"title": 'Hellbound', "start": 2021, "end": None},
    {"title": 'Lupin', "start": 2021, "end": None},
    {"title": 'Move to Heaven', "start": 2021, "end": 2021},
    {"title": 'Squid Game', "start": 2021, "end": None},
    {"title": 'Vincenzo', "start": 2021, "end": 2021},
    {"title": 'Yellowjackets', "start": 2021, "end": 2026},
    {"title": 'All of Us Are Dead', "start": 2022, "end": None},
    {"title": 'Extraordinary Attorney Woo', "start": 2022, "end": None},
    {"title": 'The Glory', "start": 2022, "end": 2023},
    {"title": 'Tokyo Vice', "start": 2022, "end": 2024},
    {"title": 'Shōgun', "start": 2024, "end": None},
    {"title": 'A Knight of the Seven Kingdoms', "start": 2026, "end": None},
    {"title": 'Blade Runner 2099', "start": 2026, "end": None},
    {"title": 'Carrie', "start": 2026, "end": None},
    {"title": 'Crystal Lake', "start": 2026, "end": None},
    {"title": 'Pride & Prejudice', "start": 2026, "end": None},
    {"title": 'VisionQuest', "start": 2026, "end": None},
]


def all_series() -> list[dict]:
    return list(SERIES_SHOWS)


def total_series() -> int:
    return len(SERIES_SHOWS)


def years_span_label(show: dict) -> str:
    start = show.get("start")
    end = show.get("end")
    if not start:
        return ""
    if end is None:
        return f"{start}–"
    if end == start:
        return str(start)
    return f"{start}–{end}"
