"""
LoL maç takip: arkadaşın maça girdiğinde ntfy ile telefona bildirim yollar.
GitHub Actions her ~5 dakikada bir bu dosyayı çalıştırır.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_KEY = os.environ["RIOT_API_KEY"].strip()
RIOT_ID = os.environ["RIOT_ID"].strip()            # örnek: "Kevin#EUW"
PLATFORM = os.environ.get("PLATFORM", "euw1").strip().lower()   # euw1, tr1, eun1...
REGION = os.environ.get("REGION", "europe").strip().lower()     # europe, americas, asia
NTFY_TOPIC = os.environ["NTFY_TOPIC"].strip()
STATE_FILE = "state.json"


def riot_get(url):
    req = urllib.request.Request(url, headers={"X-Riot-Token": API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # oyunda değil
        if e.code in (401, 403):
            raise SystemExit("Riot API anahtarı geçersiz veya süresi dolmuş.")
        raise


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def champion_names():
    try:
        with urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json", timeout=20) as r:
            version = json.load(r)[0]
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.load(r)["data"]
        return {int(c["key"]): c["name"] for c in data.values()}
    except Exception:
        return {}


def notify(title, message, click=None):
    payload = {"topic": NTFY_TOPIC, "title": title, "message": message, "priority": 4, "tags": ["video_game"]}
    if click:
        payload["click"] = click
    req = urllib.request.Request(
        "https://ntfy.sh",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=20).read()


QUEUES = {420: "Solo/Duo", 440: "Flex", 400: "Normal Draft", 430: "Blind", 450: "ARAM",
          490: "Quickplay", 1700: "Arena", 1900: "URF", 900: "ARURF"}


def main():
    name, tag = RIOT_ID.split("#", 1)
    state = load_state()

    puuid = state.get("puuid") if state.get("riot_id") == RIOT_ID else None
    if not puuid:
        acc = riot_get(
            f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
            f"{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
        )
        if not acc:
            raise SystemExit(f"Riot ID bulunamadı: {RIOT_ID}")
        puuid = acc["puuid"]
        state.update({"riot_id": RIOT_ID, "puuid": puuid})

    game = riot_get(f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}")

    if not game:
        print("Oyunda değil.")
        save_state(state)
        return

    game_id = game["gameId"]
    if state.get("last_game_id") == game_id:
        print("Bu maç için zaten bildirim gönderildi.")
        save_state(state)
        return

    champ = "?"
    me = next((p for p in game.get("participants", []) if p.get("puuid") == puuid), None)
    if me:
        champ = champion_names().get(me.get("championId"), "?")
    mode = QUEUES.get(game.get("gameQueueConfigId"), game.get("gameMode", "Oyun"))

    opgg_region = PLATFORM.rstrip("0123456789")
    opgg_url = f"https://op.gg/lol/summoners/{opgg_region}/{urllib.parse.quote(name)}-{urllib.parse.quote(tag)}/ingame"

    notify(f"{name} maçta! 🎮", f"Mod: {mode}\nŞampiyon: {champ}", click=opgg_url)
    print(f"Bildirim gönderildi: {mode} / {champ}")

    state["last_game_id"] = game_id
    save_state(state)


if __name__ == "__main__":
    main()
