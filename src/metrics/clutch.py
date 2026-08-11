import pandas as pd
from demoparser2 import DemoParser as RawDemoParser


def calculate_clutch_metrics(raw_parser: RawDemoParser) -> dict:
  """Возвращает словарь с количеством выигранных клатчей (1vX) по steamid."""
  stats = {}

  def _init_player(sid):
    if sid and sid not in stats:
      stats[sid] = {"clutches_won": 0}

  try:
    death_events = raw_parser.parse_events(["player_death"])
    round_events = raw_parser.parse_events(["round_end"])

    df_deaths = (
        death_events[0][1] if isinstance(death_events, list) else death_events
    )
    df_rounds = (
        round_events[0][1] if isinstance(round_events, list) else round_events
    )

    if (
        df_deaths is not None
        and not df_deaths.empty
        and df_rounds is not None
        and not df_rounds.empty
    ):
      df_valid_rounds = df_rounds[
          df_rounds["winner"].isin([2, 3, "2", "3", "CT", "T"])
      ].sort_values("tick")
      round_ticks = df_valid_rounds["tick"].tolist()
      if len(round_ticks) > 24:
        round_ticks = round_ticks[-24:]

      def _assign_round(tick):
        for r_idx, r_tick in enumerate(round_ticks):
          if tick <= r_tick:
            return r_idx + 1
        return len(round_ticks) + 1

      df_deaths["calc_round"] = df_deaths["tick"].apply(_assign_round)

      for round_num, group in df_deaths.groupby("calc_round"):
        if round_num > len(df_valid_rounds):
          continue

        round_info = df_valid_rounds.iloc[round_num - 1]
        winner_raw = str(round_info.get("winner", ""))
        winner_side = "3" if winner_raw in ["3", "CT"] else "2"

        round_players = {}
        for _, r in group.iterrows():
          v_id, v_team_raw = str(r.get("user_steamid", "")), str(
              r.get("user_team", "")
          )
          a_id, a_team_raw = str(r.get("attacker_steamid", "")), str(
              r.get("attacker_team", "")
          )

          if v_id and v_id not in ["0", "None"]:
            round_players[v_id] = (
                "3" if v_team_raw in ["3", "CT"] else "2"
            )
          if a_id and a_id not in ["0", "None"]:
            round_players[a_id] = (
                "3" if a_team_raw in ["3", "CT"] else "2"
            )

        alive_players = dict(round_players)
        clutch_candidates = {}

        for _, row in group.sort_values("tick").iterrows():
          victim = str(row.get("user_steamid", ""))
          if victim in alive_players:
            del alive_players[victim]

          ct_alive = [
              sid for sid, team in alive_players.items() if team == "3"
          ]
          t_alive = [
              sid for sid, team in alive_players.items() if team == "2"
          ]

          if len(ct_alive) == 1 and len(t_alive) >= 1:
            clutch_candidates[ct_alive[0]] = "3"

          if len(t_alive) == 1 and len(ct_alive) >= 1:
            clutch_candidates[t_alive[0]] = "2"

        for player_id, p_team in clutch_candidates.items():
          if p_team == winner_side:
            _init_player(player_id)
            stats[player_id]["clutches_won"] += 1

  except Exception as e:
    print(f"⚠️ Ошибка при парсинге Clutches: {e}")

  return stats