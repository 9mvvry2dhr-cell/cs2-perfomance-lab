import pandas as pd
from demoparser2 import DemoParser as RawDemoParser


def calculate_entry_metrics(raw_parser: RawDemoParser) -> dict:
  """Возвращает словарь с точной Entry-статистикой (ровно 1 First Kill на раунд)."""
  stats = {}

  def _init_player(sid):
    if sid and sid not in stats:
      stats[sid] = {"entry_kills": 0, "entry_deaths": 0}

  try:
    death_events = raw_parser.parse_events(["player_death"])
    df_deaths = None
    if isinstance(death_events, pd.DataFrame):
      df_deaths = death_events
    elif isinstance(death_events, list) and len(death_events) > 0:
      df_deaths = (
          death_events[0][1]
          if isinstance(death_events[0], tuple)
          else death_events[0]
      )

    round_events = raw_parser.parse_events(["round_end"])
    df_rounds = None
    if isinstance(round_events, pd.DataFrame):
      df_rounds = round_events
    elif isinstance(round_events, list) and len(round_events) > 0:
      df_rounds = (
          round_events[0][1]
          if isinstance(round_events[0], tuple)
          else round_events[0]
      )

    if df_deaths is not None and not df_deaths.empty:
      df_deaths = df_deaths.sort_values("tick").copy()

      # Вариант 1: В событиях есть явный номер раунда
      if "round" in df_deaths.columns and df_deaths["round"].nunique() > 1:
        first_deaths = df_deaths.groupby("round").first()

      # Вариант 2: Привязка тиков смертей к тикам round_end
      elif df_rounds is not None and not df_rounds.empty:
        df_valid_rounds = df_rounds[
            df_rounds["winner"].isin([2, 3, "2", "3", "CT", "T"])
        ]
        round_ticks = sorted(df_valid_rounds["tick"].tolist())
        if len(round_ticks) > 24:
          round_ticks = round_ticks[-24:]

        def _assign_round(tick):
          for r_idx, r_tick in enumerate(round_ticks):
            if tick <= r_tick:
              return r_idx + 1
          return len(round_ticks) + 1

        df_deaths["calc_round"] = df_deaths["tick"].apply(_assign_round)
        first_deaths = df_deaths.groupby("calc_round").first()

      else:
        df_deaths["calc_round"] = (df_deaths["tick"].diff() > 2500).cumsum()
        first_deaths = df_deaths.groupby("calc_round").first()

      for _, row in first_deaths.iterrows():
        killer = str(row.get("attacker_steamid", ""))
        victim = str(row.get("user_steamid", ""))

        if killer and killer not in ["0", "None"] and killer != victim:
          _init_player(killer)
          stats[killer]["entry_kills"] += 1

        if victim and victim not in ["0", "None"]:
          _init_player(victim)
          stats[victim]["entry_deaths"] += 1

  except Exception as e:
    print(f"⚠️ Ошибка при парсинге Entry Kills: {e}")

  return stats