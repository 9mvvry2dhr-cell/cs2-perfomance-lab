import os
from typing import List, Dict, Any, Optional
from demoparser2 import DemoParser as RawDemoParser

from src.parsing.dto import ParsedMatch, ParsedPlayer, ParsedRound
from src.metrics.utility import calculate_utility_metrics
from src.metrics.entry import calculate_entry_metrics
from src.metrics.clutch import calculate_clutches


class DemoParser:
    """
    Класс-обертка над demoparser2 для извлечения и нормализации данных CS2 демо-файла.
    """

    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл демо не найден по пути: {file_path}")
        self.file_path = file_path
        self.raw_parser = RawDemoParser(file_path)

    def parse(self) -> ParsedMatch:
        """
        Основной метод парсинга. Возвращает валидированный ParsedMatch DTO.
        """
        match_id = os.path.splitext(os.path.basename(self.file_path))[0]
        header = self.raw_parser.parse_header()
        map_name = header.get("map_name", "unknown") if header else "unknown"

        rounds = self._parse_rounds()
        players = self._parse_players()

        # Если раундов нет, матч считается невалидным
        is_valid = len(rounds) > 0
        rounds_played = len(rounds)

        # Расчет итогового счета
        score_ct = sum(1 for r in rounds if r.winner_side == "CT")
        score_t = sum(1 for r in rounds if r.winner_side == "T")

        # Обогащаем игроков дополнительными расчитанными метриками (Utility, Entry, Clutch)
        self._enrich_player_metrics(players, rounds_played)

        return ParsedMatch(
            match_id=match_id,
            map_name=map_name,
            rounds_played=rounds_played,
            score_ct=score_ct,
            score_t=score_t,
            is_valid=is_valid,
            rounds=rounds,
            players=players,
        )

    def _parse_rounds(self) -> List[ParsedRound]:
        """
        Извлекает нормализованный список раундов без хардкода 24 раундов.
        """
        round_events = self.raw_parser.parse_events(["round_end"])
        if not round_events:
            return []

        df_rounds = round_events[0][1] if isinstance(round_events, list) else round_events
        if df_rounds.empty:
            return []

        # Находим финальный тик матча (если есть cs_win_panel_match)
        match_end_tick = None
        try:
            win_panel = self.raw_parser.parse_events(["cs_win_panel_match"])
            if win_panel:
                df_win = win_panel[0][1] if isinstance(win_panel, list) else win_panel
                if not df_win.empty:
                    match_end_tick = df_win["tick"].max()
        except Exception:
            match_end_tick = None

        # Фильтруем раунды, отсекая все, что было после официального завершения
        if match_end_tick is not None:
            df_valid_rounds = df_rounds[df_rounds["tick"] <= match_end_tick].copy()
        else:
            df_valid_rounds = df_rounds.copy()

        parsed_rounds = []
        for idx, row in df_valid_rounds.iterrows():
            parsed_rounds.append(
                ParsedRound(
                    round_num=int(row.get("round", idx + 1)),
                    winner_side=str(row["winner"]),
                    win_reason=str(row.get("reason", "unknown")),
                    end_tick=int(row["tick"]),
                )
            )

        return parsed_rounds

    def _parse_players(self) -> List[ParsedPlayer]:
        """
        Извлекает базовую статистику игроков из финальных эвентов или таблицы игроков.
        """
        death_events = self.raw_parser.parse_events(["player_death"])
        df_deaths = death_events[0][1] if death_events else None

        try:
            player_info = self.raw_parser.parse_player_info()
        except Exception:
            player_info = []

        players_dict: Dict[str, Dict[str, Any]] = {}

        if player_info is not None and not (hasattr(player_info, 'empty') and player_info.empty):
            for _, p in player_info.iterrows():
                steam_id = str(p.get("steamid", p.get("steam_id", "")))
                name = str(p.get("name", p.get("user_name", "Unknown")))
                if steam_id and steam_id != "0":
                    players_dict[steam_id] = {
                        "name": name,
                        "kills": 0,
                        "deaths": 0,
                        "assists": 0,
                        "damage": 0,
                        "headshots": 0,
                    }

        if df_deaths is not None and not df_deaths.empty:
            for _, row in df_deaths.iterrows():
                attacker_id = str(row.get("attacker_steamid", ""))
                user_id = str(row.get("user_steamid", ""))
                assistant_id = str(row.get("assistant_steamid", ""))
                headshot = bool(row.get("headshot", False))

                if attacker_id in players_dict and attacker_id != user_id:
                    players_dict[attacker_id]["kills"] += 1
                    if headshot:
                        players_dict[attacker_id]["headshots"] += 1

                if user_id in players_dict:
                    players_dict[user_id]["deaths"] += 1

                if assistant_id in players_dict and assistant_id != user_id:
                    players_dict[assistant_id]["assists"] += 1

        hurt_events = self.raw_parser.parse_events(["player_hurt"])
        if hurt_events:
            df_hurt = hurt_events[0][1] if isinstance(hurt_events, list) else hurt_events
            if not df_hurt.empty:
                for _, row in df_hurt.iterrows():
                    attacker_id = str(row.get("attacker_steamid", ""))
                    dmg = int(row.get("dmg_health", 0))
                    user_id = str(row.get("user_steamid", ""))

                    if attacker_id in players_dict and attacker_id != user_id:
                        players_dict[attacker_id]["damage"] += dmg

        parsed_players = []
        for steam_id, data in players_dict.items():
            parsed_players.append(
                ParsedPlayer(
                    steam_id=steam_id,
                    nickname=data["name"],
                    kills=data["kills"],
                    deaths=data["deaths"],
                    assists=data["assists"],
                    damage=data["damage"],
                    headshots=data["headshots"],
                )
            )

        return parsed_players

    def _enrich_player_metrics(self, players: List[ParsedPlayer], rounds_played: int) -> None:
        """
        Расчитывает и записывает продвинутые метрики (Utility, Entry, Clutch) напрямую в DTO игроков.
        """
        steam_ids = [p.steam_id for p in players]

        utility_stats = calculate_utility_metrics(self.raw_parser, steam_ids)
        entry_stats = calculate_entry_metrics(self.raw_parser, steam_ids)
        clutch_stats = calculate_clutches(self.raw_parser, steam_ids)

        for p in players:
            sid = p.steam_id

            u_data = utility_stats.get(sid, {})
            p.he_damage = u_data.get("he_damage", 0)
            p.inferno_damage = u_data.get("inferno_damage", 0)
            p.enemies_flashed = u_data.get("enemies_flashed", 0)
            p.flash_duration = u_data.get("flash_duration", 0.0)

            e_data = entry_stats.get(sid, {})
            p.entry_kills = e_data.get("entry_kills", 0)
            p.entry_deaths = e_data.get("entry_deaths", 0)

            p.clutches_won = clutch_stats.get(sid, 0)