import functools
import os
import re
from collections import namedtuple
from datetime import datetime, time

from flask import Flask, request, render_template, jsonify, redirect

from raven.contrib.flask.utils import get_data_from_request

from dateutil.parser import parse as parse_datetime

import requests

from pyquery import PyQuery

import pytz


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
            "Brooklyn Nets", "BKN", "GoNets",
            "http://espn.go.com/nba/team/_/name/bkn/brooklyn-nets",
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
            "Chicago Bulls", "CHI", "chicagobulls",
            "http://espn.go.com/nba/team/_/name/chi/chicago-bulls"
        ),
        Team(
            "Cleveland Cavaliers", "CLE", "clevelandcavs",
            "http://espn.go.com/nba/team/_/name/cle/cleveland-cavaliers"
        ),
        Team(
            "Detroit Pistons", "DET", "DetroitPistons",
            "http://espn.go.com/nba/team/_/name/det/detroit-pistons"
        ),
        Team(
            "Indiana Pacers", "IND", "IndianaPacers",
            "http://espn.go.com/nba/team/_/name/ind/indiana-pacers"
        ),
        Team(
            "Milwaukee Bucks", "MIL", "mkebucks",
            "http://espn.go.com/nba/team/_/name/mil/milwaukee-bucks"
        ),
    ]),
    Division("Southeast", [
        Team(
            "Atlanta Hawks", "ATL", "AtlantaHawks",
            "http://espn.go.com/nba/team/_/name/atl/atlanta-hawks"
        ),
        Team(
            "Charlotte Bobcats", "CHA", "CharlotteBobcats",
            "http://espn.go.com/nba/team/_/name/cha/charlotte-bobcats"
        ),
        Team(
            "Miami Heat", "MIA", "heat",
            "http://espn.go.com/nba/team/_/name/mia/miami-heat"
        ),
        Team(
            "Orlando Magic", "ORL", "orlandomagic",
            "http://espn.go.com/nba/team/_/name/orl/orlando-magic"
        ),
        Team(
            "Washington Wizards", "WAS", "washingtonwizards",
            "http://espn.go.com/nba/team/_/name/wsh/washington-wizards"
        ),
    ]),
    Division("Pacific", [
        Team(
            "Golden State Warriors", "GSW", "warriors",
            "http://espn.go.com/nba/team/_/name/gs/golden-state-warriors"
        ),
        Team(
            "Los Angeles Clippers", "LAC", "LAClippers",
            "http://espn.go.com/nba/team/_/name/lac/los-angeles-clippers"
        ),
        Team(
            "Los Angeles Lakers", "LAL", "lakers",
            "http://espn.go.com/nba/team/_/name/lal/los-angeles-lakers"
        ),
        Team(
            "Phoenix Suns", "PHX", "PhoenixSuns",
            "http://espn.go.com/nba/team/_/name/phx/phoenix-suns"
        ),
        Team(
            "Sacramento Kings", "SAC", "kings",
            "http://espn.go.com/nba/team/_/name/sac/sacramento-kings"
        ),
    ]),
    Division("Southwest", [
        Team(
            "Dallas Mavericks", "DAL", "Mavericks",
            "http://espn.go.com/nba/team/_/name/dal/dallas-mavericks"
        ),
        Team(
            "Houston Rockets", "HOU", "houstonrockets",
            "http://espn.go.com/nba/team/_/name/hou/houston-rockets"
        ),
        Team(
            "Memphis Grizzlies", "MEM", "memphisgrizzlies",
            "http://espn.go.com/nba/team/_/name/mem/memphis-grizzlies"
        ),
        Team(
            "New Orleans Hornets", "NOH", "Hornets",
            "http://espn.go.com/nba/team/_/name/no/new-orleans-hornets"
        ),
        Team(
            "San Antonio Spurs", "SAS", "NBASpurs",
            "http://espn.go.com/nba/team/_/name/sa/san-antonio-spurs"
        ),
    ]),
    Division("Northwest", [
        Team(
            "Denver Nuggets", "DEN", "denvernuggets",
            "http://espn.go.com/nba/team/_/name/den/denver-nuggets"
        ),
        Team(
            "Minnesota Timberwolves", "MIN", "timberwolves",
            "http://espn.go.com/nba/team/_/name/min/minnesota-timberwolves"
        ),
        Team(
            "Oklahoma City Thunder", "OKC", "Thunder",
            "http://espn.go.com/nba/team/_/name/okc/oklahoma-city-thunder"
        ),
        Team(
            "Portland Trail Blazers", "POR", "ripcity",
            "http://espn.go.com/nba/team/_/name/por/portland-trail-blazers"
        ),
        Team(
            "Utah Jazz", "UTA", "UtahJazz",
            "http://espn.go.com/nba/team/_/name/utah/utah-jazz"
        ),
    ]),
]

CBS_SHORTCODE_MAP = {
    "NYK": "NY",
    "PHX": "PHO",
    "NJN": "NJ",
    "SAS": "SA",
    "NOH": "NO",
    "GSW": "GS",
}


def get_team(shortcode):
    for div in DIVISIONS:
        for team in div.teams:
            if team.shortcode == shortcode:
                return team
    raise LookupError


@app.route("/")
def home():
    return render_template("home.html", divisions=DIVISIONS)


@app.route("/reddit-stream/")
def reddit_stream():
    if request.referrer is None:
        return "This link works via magic. Click it from the normal comment page."
    return redirect(re.sub("reddit.com", "reddit-stream.com", request.referrer))


NBA_URL = "http://www.nba.com/games/{year}{month}{day}/{away.shortcode}{home.shortcode}/gameinfo.html"
CBS_URL = "http://www.cbssports.com/nba/gametracker/preview/NBA_{year}{month}{day}_{away}@{home}"


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
            if sentry is None:
                raise
            sentry.client.capture('Exception',
                data=get_data_from_request(request),
                extra={
                    'app': app,
                },
            )
            return error("Uh oh. Something went wrong on our end. We've "
                "dispatched trained monkeys to investigate.")
    return inner

NBA_RECORD_RE = re.compile(r"\((?P<wins>\d+)-(?P<losses>\d+)\)")


def find_espn_record(team):
    r = requests.get(team.espn_url)
    r.raise_for_status()
    page = PyQuery(r.text)
    text = page("#sub-branding").find(".sub-title").text()
    record = text.split(",", 1)[0]
    return record.split("-")


@app.route("/generate/", methods=["POST"])
@handle_errors
def generate():
    try:
        away = get_team(request.form["away"])
        home = get_team(request.form["home"])
    except LookupError:
        return error("Please select a team.")

    today = pytz.timezone("US/Mountain").fromutc(datetime.utcnow()).date()
    nba_url = NBA_URL.format(
        year=today.year,
        month=str(today.month).zfill(2),
        day=str(today.day).zfill(2),
        away=away,
        home=home,
    )
    cbs_away_shortcode = CBS_SHORTCODE_MAP.get(away.shortcode, away.shortcode)
    cbs_home_shortcode = CBS_SHORTCODE_MAP.get(home.shortcode, home.shortcode)
    cbs_url = CBS_URL.format(
        year=today.year,
        month=str(today.month).zfill(2),
        day=str(today.day).zfill(2),
        away=cbs_away_shortcode,
        home=cbs_home_shortcode,
    )

    r = requests.get(nba_url)
    if r.status_code == 404:
        return error("These teams don't seem to be playing each other tonight.")
    r.raise_for_status()

    nba_page = PyQuery(r.text)
    info = nba_page("#nbaGIStation").find(".nbaGITime").text()
    if info is None:
        return error("It looks like you reversed the home and the away team.")
    gametime, stadium = info.split("-")
    gametime = parse_datetime(gametime.strip()).time()
    gametimes = {
        "est": sub_hours(gametime, 0),
        "cst": sub_hours(gametime, 1),
        "mst": sub_hours(gametime, 2),
        "pst": sub_hours(gametime, 3),
    }
    stadium = stadium.strip()
    records = nba_page("#nbaGITeamStats thead th")
    if records and len(records) == 2:
        [away_rec, home_rec] = records
        home_rec = NBA_RECORD_RE.search(home_rec.text_content()).groups()
        away_rec = NBA_RECORD_RE.search(away_rec.text_content()).groups()
    else:
        home_rec = find_espn_record(home)
        away_rec = find_espn_record(away)

    r = requests.get(cbs_url, allow_redirects=False)
    r.raise_for_status()

    cbs_page = PyQuery(r.text)
    tvs = []
    for loc in ["National", "Away", "Home"]:
        tv = cbs_page("td b:contains('{}:')".format(loc)).parent()
        if tv:
            tvs.append(tv[0].text_content())

    return jsonify(
        title=render_template("title.txt",
            away=away, away_rec=away_rec,
            home=home, home_rec=home_rec,
            today=today),
        body=render_template("gamethread.txt",
            away=away, home=home, tv=", ".join(tvs),
            gametimes=gametimes, stadium=stadium, nba_url=nba_url,
            host=request.host,
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
