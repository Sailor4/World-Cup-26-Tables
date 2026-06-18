from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DATA_URL = "https://api.football-data.org/v4/competitions/WC/matches"
API_KEY = os.getenv("FOOTBALL_API_KEY", "")


def get_base_data():
    """Helper to fetch raw data from football-data.org and map it to the old format"""
    try:
        clean_key = str(API_KEY).strip()
        headers = {
            "X-Auth-Token": clean_key,
            "Accept": "application/json"
        }

        response = requests.get(DATA_URL, headers=headers, timeout=5)
        response.raise_for_status()
        raw_data = response.json()

        new_matches = raw_data.get("matches", [])
        mapped_matches = []

        for match in new_matches:
            # 1. Вземаме сигурни данни за отборите
            home_team_obj = match.get("homeTeam")
            away_team_obj = match.get("awayTeam")

            # Ако изобщо липсва структурата за отборите, прескачаме
            if not home_team_obj or not away_team_obj:
                continue

            home_name = home_team_obj.get("name")
            away_name = away_team_obj.get("name")

            # 2. ЖЕЛЕЗНА ЗАЩИТА: Ако името е празно, None или съдържа служебни празни стрингове, прескачаме!
            if not home_name or not away_name or home_name == "None" or away_name == "None":
                continue

            # 3. Проверка за групата: Ако няма група (защото е елиминация), прескачаме!
            # Махаме "Group A" по подразбиране, за да не пълним Група А с боклуци
            raw_group = match.get("group")
            if not raw_group:
                continue

            # Превръщаме служебното "GROUP_A" в "Group A"
            clean_group = raw_group.replace("_", " ").title()

            # Extract scores safely
            score_data = match.get("score", {})
            full_time = score_data.get("fullTime", {})
            home_score = full_time.get("home")
            away_score = full_time.get("away")

            # Map the new API structure to the old keys that your code expects
            mapped_match = {
                "Group": clean_group,
                "DateUtc": match.get("utcDate", "").replace("Z", "").replace("T", " "),
                "HomeTeam": home_name,
                "AwayTeam": away_name,
                "HomeTeamScore": home_score if match.get("status") == "FINISHED" else None,
                "AwayTeamScore": away_score if match.get("status") == "FINISHED" else None,
            }
            mapped_matches.append(mapped_match)

        return mapped_matches

    except Exception as e:
        print(f"Error fetching live data: {e}")
        return []


def get_live_world_cup_data():
    matches = get_base_data()
    groups = {}

    for match in matches:
        if match.get("Group") and "Group" in match["Group"]:
            group_name = match["Group"]
            if group_name not in groups:
                groups[group_name] = {"teams": {}, "matches": []}

            score = "-:-"
            if match["HomeTeamScore"] is not None and match["AwayTeamScore"] is not None:
                score = f"{match['HomeTeamScore']}:{match['AwayTeamScore']}"

            groups[group_name]["matches"].append({
                "date": match["DateUtc"][:10],
                "time": match["DateUtc"][11:16],
                "teams": f"{match['HomeTeam']} - {match['AwayTeam']}",
                "result": score
            })

            h_team = match["HomeTeam"]
            a_team = match["AwayTeam"]

            if h_team not in groups[group_name]["teams"]:
                groups[group_name]["teams"][h_team] = {"name": h_team, "played": 0, "points": 0}
            if a_team not in groups[group_name]["teams"]:
                groups[group_name]["teams"][a_team] = {"name": a_team, "played": 0, "points": 0}

            if match["HomeTeamScore"] is not None and match["AwayTeamScore"] is not None:
                groups[group_name]["teams"][h_team]["played"] += 1
                groups[group_name]["teams"][a_team]["played"] += 1

                if match["HomeTeamScore"] > match["AwayTeamScore"]:
                    groups[group_name]["teams"][h_team]["points"] += 3
                elif match["AwayTeamScore"] > match["HomeTeamScore"]:
                    groups[group_name]["teams"][a_team]["points"] += 3
                else:
                    groups[group_name]["teams"][h_team]["points"] += 1
                    groups[group_name]["teams"][a_team]["points"] += 1

    final_data = {}
    for g_name, g_data in groups.items():
        sorted_teams = sorted(g_data["teams"].values(), key=lambda x: x["points"], reverse=True)
        final_data[g_name] = {"teams": sorted_teams, "matches": g_data["matches"]}

    return dict(sorted(final_data.items()))


def get_upcoming_matches(limit=8):
    matches = get_base_data()
    upcoming = []

    today_bg_str = "2026-06-18"
    tomorrow_bg_str = "2026-06-19"

    for match in matches:
        if match.get("Group") and "Group" in match["Group"]:
            try:
                match_utc = datetime.strptime(match["DateUtc"][:16], "%Y-%m-%d %H:%M")
                match_bg = match_utc + timedelta(hours=3)
            except Exception:
                continue

            match_date_bg = match_bg.strftime("%Y-%m-%d")

            if match_date_bg == today_bg_str or match_date_bg == tomorrow_bg_str:
                is_played = match["HomeTeamScore"] is not None and match["AwayTeamScore"] is not None

                if is_played:
                    time_display = f"{match['HomeTeamScore']}:{match['AwayTeamScore']}"
                else:
                    time_display = f"{match_bg.strftime('%H:%M')} ч."

                upcoming.append({
                    "group": match.get("Group", "World Cup"),
                    "date": match_date_bg,
                    "time": time_display,
                    "teams": f"{match['HomeTeam']} - {match['AwayTeam']}"
                })

            if len(upcoming) == limit:
                break

    return upcoming


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    next_matches = get_upcoming_matches(limit=8)
    return templates.TemplateResponse(request, "index.html", {"request": request, "upcoming": next_matches})


@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    live_groups = get_live_world_cup_data()
    return templates.TemplateResponse(request, "groups.html", {"request": request, "groups": live_groups})


@app.get("/eliminations", response_class=HTMLResponse)
async def eliminations_page(request: Request):
    return templates.TemplateResponse(request, "eliminations.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    # Пускаме го отново на 0.0.0.0, за да е достъпен през мрежата
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)