from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Official reliable live feed for WC 2026 schedule and results (JSON format)
DATA_URL = "https://fixturedownload.com/feed/json/fifa-world-cup-2026"


def get_live_world_cup_data():
    try:
        response = requests.get(DATA_URL, timeout=10)
        matches = response.json()
    except Exception as e:
        print(f"Error fetching live data: {e}")
        return {}

    groups = {}

    # 1. Sort matches into their respective groups
    for match in matches:
        # Check if the match belongs to a group stage and the field is not None
        if match.get("Group") and "Group" in match["Group"]:
            group_name = match["Group"]
            if group_name not in groups:
                groups[group_name] = {"teams": {}, "matches": []}

            # Format the match score
            score = "-:-"
            if match["HomeTeamScore"] is not None and match["AwayTeamScore"] is not None:
                score = f"{match['HomeTeamScore']}:{match['AwayTeamScore']}"

            # Append match details to the group
            groups[group_name]["matches"].append({
                "date": match["DateUtc"][:10],  # Extract YYYY-MM-DD
                "time": match["DateUtc"][11:16],  # Extract HH:MM
                "teams": f"{match['HomeTeam']} - {match['AwayTeam']}",
                "result": score
            })

            # Initialize teams in the standing dictionary if not already present
            for team in [match["HomeTeam"], match["AwayTeam"]]:
                if team not in groups[group_name]["teams"]:
                    groups[group_name]["teams"][team] = {"name": team, "played": 0, "points": 0}

            # 2. Dynamically calculate standing stats based on played matches
            if match["HomeTeamScore"] is not None and match["AwayTeamScore"] is not None:
                home_score = match["HomeTeamScore"]
                away_score = match["AwayTeamScore"]

                groups[group_name]["teams"][match["HomeTeam"]]["played"] += 1
                groups[group_name]["teams"][match["AwayTeam"]]["played"] += 1

                if home_score > away_score:
                    groups[group_name]["teams"][match["HomeTeam"]]["points"] += 3
                elif away_score > home_score:
                    groups[group_name]["teams"][match["AwayTeam"]]["points"] += 3
                else:
                    groups[group_name]["teams"][match["HomeTeam"]]["points"] += 1
                    groups[group_name]["teams"][match["AwayTeam"]]["points"] += 1

    # 3. Convert teams dict to a sorted list based on points (descending)
    final_data = {}
    for g_name, g_data in groups.items():
        sorted_teams = sorted(g_data["teams"].values(), key=lambda x: x["points"], reverse=True)
        final_data[g_name] = {
            "teams": sorted_teams,
            "matches": g_data["matches"]
        }

    return final_data


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    # Fetch fresh live data upon every page reload
    live_groups = get_live_world_cup_data()
    return templates.TemplateResponse(request, "groups.html", {"groups": live_groups})


@app.get("/eliminations", response_class=HTMLResponse)
async def eliminations_page(request: Request):
    return templates.TemplateResponse(request, "eliminations.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", reload=True)