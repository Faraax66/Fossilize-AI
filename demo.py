import json
prs = json.load(open("data/raw/pull_requests.json"))
mine = [p for p in prs if p["author"] == "Faraax66"]
print(f"Found {len(mine)} PRs authored by Faraax66 in psf/black:\n")
for p in mine:
    print(f"#{p['number']}: {p['title']} (state={p['state']})")