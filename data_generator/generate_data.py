"""Generate synthetic, deliberately messy charity contact data.

Same seed + same config => identical output files.
All data is fake. Do not add real personal data to this project.
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

import yaml
from faker import Faker


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def mess_postcode(pc, rng):
    """Return the postcode in a random messy format."""
    return rng.choice([
        pc.lower(),
        pc.replace(" ", ""),
        pc.replace(" ", "  "),
        " " + pc,
    ])


def typo(text, rng):
    """Drop one letter or swap two adjacent letters."""
    if len(text) < 4:
        return text
    i = rng.randrange(1, len(text) - 2)
    if rng.random() < 0.5:
        return text[:i] + text[i + 1:]
    return text[:i] + text[i + 1] + text[i] + text[i + 2:]


def random_date(rng, start, end):
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build_people(cfg, fake, rng):
    start = date.fromisoformat(cfg["start_date"])
    end = date.fromisoformat(cfg["end_date"])
    people = []
    for person_id in range(1, cfg["n_people"] + 1):
        first, last = fake.first_name(), fake.last_name()
        has_email = rng.random() >= cfg["missing_email_rate"]
        pc = fake.postcode()
        people.append({
            "person_id": person_id,
            "first_name": first,
            "last_name": last,
            "email": fake.unique.email() if has_email else "",
            "postcode": mess_postcode(pc, rng) if rng.random() < cfg["messy_postcode_rate"] else pc,
            "created_date": random_date(rng, start, end),
            "consent_email": "Y" if has_email and rng.random() < cfg["consent_email_rate"] else "N",
        })
    return people


def build_duplicates(cfg, people, rng):
    end = date.fromisoformat(cfg["end_date"])
    dupes = []
    for base in rng.sample(people, int(len(people) * cfg["duplicate_rate"])):
        d = dict(base)
        d["created_date"] = min(base["created_date"] + timedelta(days=rng.randint(1, 365)), end)
        variant = rng.choice(["name_typo", "email_case", "email_missing", "postcode"])
        if variant == "name_typo":
            d["last_name"] = typo(base["last_name"], rng)
        elif variant == "email_case":
            d["email"] = base["email"].upper()
        elif variant == "email_missing":
            d["email"] = ""
            d["consent_email"] = "N"
        else:
            d["postcode"] = mess_postcode(base["postcode"].strip().upper(), rng)
        dupes.append(d)
    return dupes


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="data_generator/config.yaml")
    cfg = load_config(parser.parse_args().config)

    rng = random.Random(cfg["seed"])
    Faker.seed(cfg["seed"])
    fake = Faker("en_GB")

    people = build_people(cfg, fake, rng)
    records = people + build_duplicates(cfg, people, rng)
    records.sort(key=lambda r: (r["created_date"], r["person_id"]))

    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    contacts, truth = [], []
    for n, r in enumerate(records, start=1):
        cid = f"C{n:06d}"
        contacts.append({
            "contact_id": cid, "first_name": r["first_name"], "last_name": r["last_name"],
            "email": r["email"], "postcode": r["postcode"],
            "created_date": r["created_date"].isoformat(), "consent_email": r["consent_email"],
        })
        truth.append({"contact_id": cid, "person_id": r["person_id"]})

    write_csv(out / "contacts.csv", contacts, list(contacts[0].keys()))
    # Ground truth for testing deduplication later. NOT a pipeline source.
    write_csv(out / "contacts_truth.csv", truth, ["contact_id", "person_id"])
    print(f"Wrote {len(contacts)} contact records for {cfg['n_people']} people to {out}/")


if __name__ == "__main__":
    main()