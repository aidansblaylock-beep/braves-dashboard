from datetime import date
from data import load_todays_games, today_eastern, _braves_games

print("Today (Eastern):", today_eastern())
print("Games today:", load_todays_games(today_eastern()))

# Also try the Braves' most recent finished game, so we can see real data
finals = [g for g in _braves_games(today_eastern().year) if g["final"]]
last_day = date.fromisoformat(finals[-1]["date"])
print("Testing with", last_day)
for game in load_todays_games(last_day):
    print(game)