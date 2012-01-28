import functools
import os
from collections import namedtuple
from datetime import date, time, timedelta

from flask import Flask, request, render_template, jsonify

from dateutil.parser import parse as parse_datetime

import requests

from pyquery import PyQuery



app = Flask(__name__)


Division = namedtuple("Division", ["name", "teams"])
Team = namedtuple("Team", ["name", "shortcode", "subreddit", "espn_url"])

DIVISIONS = [
    Division("Atlantic", [
        Team(
            "Boston Celtics", "BOS", "bostonceltics",
            "http://espn.go.com/nba/team/_/name/bos/boston-celtics",
        ),
        Team(
            "New Jersey Nets", "NJN", "GoNets",
            "http://espn.go.com/nba/team/_/name/nj/new-jersey-nets",
        ),
        Team(
            "New York Knicks", "NYK", "NYKnicks",
            "http://espn.go.com/nba/team/_/name/ny/new-york-knicks",
        ),
        Team(
            "Philadelphia 76ers", "PHI", "sixers",
            "http://espn.go.com/nba/team/_/name/phi/philadelphia-76ers",
        ),
        Team(
            "Toronto Raptors", "TOR", "torontoraptors",
            "http://espn.go.com/nba/team/_/name/tor/toronto-raptors"
        ),
    ]),
    Division("Central", [
        Team(
            "Chicago Bulls", "CHI", None, None),
        Team(
            "Cleveland Cavaliers", "CLE", None, None),
        Team(
            "Detroit Pistons", "DET", "DetroitPistons",
            "http://espn.go.com/nba/team/_/name/det/detroit-pistons"
        ),
        Team(
            "Indiana Pacers", "IND", None, None
        ),
        Team(
            "Milwaukee Bucks", "MIL", None, None
        ),
    ]),
    Division("Southeast", [
        Team(
            "Atlanta Hawks", "ATL", None, None
        ),
        Team(
            "Charlotte Bobcats", "CHA", None, None
        ),
        Team(
            "Miami Heat", "MIA", None, None
        ),
        Team(
            "Orlando Magic", "ORL", None, None
        ),
        Team(
            "Washington Wizards", "WAS", None, None
        ),
    ]),
    Division("Pacific", [
        Team(
            "Golden State Warriors", "GSW", None, None
        ),
        Team(
            "Los Angeles Clippers", "LAC", None, None
        ),
        Team(
            "Los Angeles Lakers", "LAL", None, None
        ),
        Team(
            "Phoenix Suns", "PHX", None, None
        ),
        Team(
            "Sacramento Kings", "SAC", None, None
        ),
    ]),
    Division("Southwest", [
        Team(
            "Dallas Mavericks", "DAL", None, None
        ),
        Team(
            "Houston Rockets", "HOU", None, None
        ),
        Team(
            "Memphis Grizzlies", "MEM", None, None
        ),
        Team(
            "New Orleans Hornets", "NOH", None, None
        ),
        Team(
            "San Antonio Spurs", "SAS", None, None
        ),
    ]),
    Division("Northwest", [
        Team(
            "Denver Nuggets", "DEN", None, None
        ),
        Team(
            "Minnesota Timberwolves", "MIN", None, None
        ),
        Team(
            "Oklahoma City Thunder", "OKC", None, None
        ),
        Team(
            "Portland Trail Blazers", "POR", None, None
        ),
        Team(
            "Utah Jazz", "UTA", None, None
        ),
    ]),
]

def get_team(shortcode):
    for div in DIVISIONS:
        for team in div.teams:
            if team.shortcode == shortcode:
                return team
    raise LookupError

@app.route("/")
def home():
    return render_template("home.html", divisions=DIVISIONS)


NBA_URL = "http://www.nba.com/games/{year}{month}{day}/{away.shortcode}{home.shortcode}/gameinfo.html"

def find_record(team):
    r = requests.get(team.espn_url)
    assert r.status_code == 200
    page = PyQuery(r.text)
    text = page("#sub-branding").find(".sub-title").text()
    record = text.split(",", 1)[0]
    wins, losses = record.split("-")
    return int(wins), int(losses)

def sub_hours(orig_time, hours):
    return time(orig_time.hour - hours, orig_time.minute).strftime("%I:%M")

def error(msg):
    return jsonify(error=msg)

def handle_errors(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            raise
            # LOG ERROR TO SENTRY
            return error("Uh oh. Something went wrong on our end. We've "
                "dispatched trained monkeys to investigate.")
    return inner

@app.route("/generate/", methods=["POST"])
@handle_errors
def generate():
    try:
        away = get_team(request.form["away"])
        home = get_team(request.form["home"])
    except LookupError:
        return error("Please select a team.")

    today = date.today()
    nba_url = NBA_URL.format(
        year=today.year,
        month=str(today.month).zfill(2),
        day=str(today.day).zfill(2),
        away=away,
        home=home
    )

    away_wins, away_losses = find_record(away)
    home_wins, home_losses = find_record(home)

    r = requests.get(nba_url)
    if r.status_code == 404:
        return error("These teams don't seem to be playing tonight.")
    r.raise_for_status()

    nba_page = PyQuery(r.text)
    info = nba_page("#nbaGIStation").find(".nbaGITime").text()
    gametime, stadium = info.split("-")
    gametime = parse_datetime(gametime.strip()).time()
    gametimes = {
        "est": sub_hours(gametime, 0),
        "cst": sub_hours(gametime, 1),
        "mst": sub_hours(gametime, 2),
        "pst": sub_hours(gametime, 3),
    }
    stadium = stadium.strip()

    return jsonify(
        title=render_template("title.txt",
            away=away, away_wins=away_wins, away_losses=away_losses,
            home=home, home_wins=home_wins, home_losses=home_losses,
            today=today),
        body=render_template("gamethread.txt",
            away=away,
            home=home,
            gametimes=gametimes, stadium=stadium, nba_url=nba_url,
        ),
    )

def configure_raven(app):
    if 'SENTRY_DSN' in os.environ:
        import raven
        from raven.contrib.flask import Sentry

        raven.load(os.environ['SENTRY_DSN'], app.config)
        sentry = Sentry(app)
        return sentry

sentry = configure_raven(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
