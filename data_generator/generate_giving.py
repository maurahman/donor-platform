"""Generate campaigns, donations and gift_aid from contacts.csv.

Run generate_data.py first. Same seed + config => identical output.
All data is fake.
"""
import argparse
import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import yaml

CHANNELS = ["Online", "Direct Mail", "Events", "Telephone", "Street"]
APPEALS = ["Winter Appeal", "Spring Appeal", "Summer Fund",
           "Autumn Drive", "Emergency Appeal", "Christmas Appeal"]
APPEAL_MONTHS = [1, 4, 7, 10, 11, 12]
AMOUNTS = [5, 10, 15, 20, 25, 50, 100, 250]
WEIGHTS = [10, 25, 10, 20, 12, 12, 8, 3]


def read_contacts(raw):
    created = {}
    with open(raw / "contacts.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            created[r["contact_id"]] = date.fromisoformat(r["created_date"])
    people = defaultdict(list)
    with open(raw / "contacts_truth.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            people[int(r["person_id"])].append(r["contact_id"])
    return created, people


def build_campaigns(cfg, rng):
    start = date.fromisoformat(cfg["start_date"])
    end = date.fromisoformat(cfg["end_date"])
    out = []
    for year in range(start.year, end.year + 1):
        for appeal, month in zip(APPEALS, APPEAL_MONTHS):
            s = date(year, month, 1)
            e = min(s + timedelta(days=rng.randint(45, 120)), end)
            name = f"{appeal} {year}"
            if rng.random() < 0.10:          # messy name
                name = name.lower() + " "
            out.append({
                "campaign_id": f"CMP{len(out) + 1:03d}",
                "name": name,
                "start_date": s,
                "end_date": e,
                "channel": rng.choice(CHANNELS),
            })
    return out


def pick_campaign(campaigns, d, rng):
    active = [c for c in campaigns if c["start_date"] <= d <= c["end_date"]]
    return rng.choice(active or campaigns)


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (v.isoformat() if isinstance(v, date) else v)
                        for k, v in r.items()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="data_generator/config.yaml")
    with open(parser.parse_args().config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    g = cfg["giving"]

    rng = random.Random(cfg["seed"] + 1)
    raw = Path(cfg["output_dir"])
    end = date.fromisoformat(cfg["end_date"])

    created, people = read_contacts(raw)
    campaigns = build_campaigns(cfg, rng)

    donations, gift_aid = [], []
    donor_ids = sorted(rng.sample(sorted(people), int(len(people) * g["donor_rate"])))

    for pid in donor_ids:
        ids = sorted(people[pid])
        first = min(created[c] for c in ids)
        if first >= end:
            continue

        if rng.random() < g["regular_rate"]:
            kind = "regular"
            amount = rng.choices(AMOUNTS, WEIGHTS)[0]
            months = rng.randint(6, 36)
            gifts = [(first + timedelta(days=30 * m), amount) for m in range(months)]
            gifts = [(d, a) for d, a in gifts if d <= end]
        else:
            kind = "single"
            n = rng.choices([1, 2, 3, 4, 5], [50, 25, 13, 8, 4])[0]
            span = (end - first).days
            gifts = [(first + timedelta(days=rng.randint(0, span)),
                      rng.choices(AMOUNTS, WEIGHTS)[0]) for _ in range(n)]

        for d, amount in gifts:
            camp = pick_campaign(campaigns, d, rng)
            donations.append({
                "contact_id": rng.choice(ids),   # may be a duplicate record
                "amount": amount,
                "donation_date": d,
                "campaign_id": camp["campaign_id"],
                "channel": camp["channel"],
                "type": kind,
            })

        if rng.random() < g["gift_aid_rate"]:
            first_gift = min(d for d, _ in gifts)
            decl = min(first_gift + timedelta(days=rng.randint(-30, 60)), end)
            gift_aid.append({
                "contact_id": ids[0],
                "declaration_date": decl,
                "status": rng.choices(["Active", "Cancelled"], [90, 10])[0],
            })

    # Inject mess
    messy = []
    for d in donations:
        if rng.random() < g["bad_amount_rate"]:
            d["amount"] = rng.choice([0, -d["amount"]])
        if rng.random() < g["future_date_rate"]:
            d["donation_date"] = end + timedelta(days=rng.randint(30, 400))
        if rng.random() < g["orphan_rate"]:
            d["contact_id"] = f"C{rng.randint(900000, 999999)}"
        if rng.random() < g["channel_case_mess_rate"]:
            d["channel"] = d["channel"].upper()
        messy.append(d)
        if rng.random() < g["duplicate_row_rate"]:
            messy.append(dict(d))                # double-posted gift

    messy.sort(key=lambda r: (r["donation_date"], r["contact_id"]))
    for n, d in enumerate(messy, start=1):
        d["donation_id"] = f"D{n:07d}"

    write_csv(raw / "campaigns.csv", campaigns,
              ["campaign_id", "name", "start_date", "end_date", "channel"])
    write_csv(raw / "donations.csv", messy,
              ["donation_id", "contact_id", "amount", "donation_date",
               "campaign_id", "channel", "type"])
    write_csv(raw / "gift_aid.csv", gift_aid,
              ["contact_id", "declaration_date", "status"])
    print(f"Wrote {len(campaigns)} campaigns, {len(messy)} donations, "
          f"{len(gift_aid)} gift aid declarations to {raw}/")


if __name__ == "__main__":
    main()