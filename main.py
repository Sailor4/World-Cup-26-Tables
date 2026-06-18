from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DATA_URL = "https://fixturedownload.com/feed/json/fifa-world-cup-2026"


def get_base_data():
    """Helper to fetch raw data from the live feed safely"""
    try:
        response = requests.get(DATA_URL, timeout=10)
        return response.json()
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
    # Fetch all raw matches from the live feed
    matches = get_base_data()
    upcoming = []

    # Define the target Bulgarian dates we want to show on the dashboard
    today_bg_str = "2026-06-18"
    tomorrow_bg_str = "2026-06-19"

    for match in matches:
        if match.get("Group") and "Group" in match["Group"]:
            try:
                # Convert to Bulgarian time using the exact space format from the feed
                match_utc = datetime.strptime(match["DateUtc"][:16], "%Y-%m-%d %H:%M")
                match_bg = match_utc + timedelta(hours=3)
            except Exception:
                continue

            # Get the actual calendar date in Bulgaria
            match_date_bg = match_bg.strftime("%Y-%m-%d")

            # Check if this Bulgarian date falls into today or tomorrow
            if match_date_bg == today_bg_str or match_date_bg == tomorrow_bg_str:
                is_played = match["HomeTeamScore"] is not None and match["AwayTeamScore"] is not None

                # Format time display dynamically: show score if finished, Bulgarian time if upcoming
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

            # Stop once we have gathered our 8 matches
            if len(upcoming) == limit:
                break

    return upcoming


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Fetch the next 8 matches for the home dashboard
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

    uvicorn.run("main:app", reload=True)