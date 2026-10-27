# Rashal Energies — Compliance Management System

Tracks statutory compliance (EWURA, NEMC, Fire, OSHA, TRA and others) across
every petrol station: dates, statuses, certificates, payment receipts, and the
alerts that stop a licence lapsing unnoticed.

Django 5.2 · PostgreSQL · Beem Africa SMS

---

## Quick start

```bash
pip install -r requirements.txt
copy .env.example .env          # Windows;  cp .env.example .env  on Linux
python manage.py migrate
python manage.py bootstrap_roles
python manage.py seed_demo
python manage.py runserver
```

Then open http://127.0.0.1:8000/django-admin/

| Login     | Password        | Role               | Sees                             |
|-----------|-----------------|--------------------|----------------------------------|
| `admin`   | `ChangeMe2026!` | Super admin        | all 13 stations                  |
| `officer` | `ChangeMe2026!` | Compliance officer | all 13 stations                  |
| `john`    | `ChangeMe2026!` | Station manager    | Singida only                     |
| `neema`   | `ChangeMe2026!` | Station manager    | 5 Singida-region stations        |
| `juma`    | `ChangeMe2026!` | Station manager    | Liwale, Nachingwea, Ruangwa      |
| `amina`   | `ChangeMe2026!` | Station manager    | Masasi, Newala                   |
| `baraka`  | `ChangeMe2026!` | Station manager    | Karatu only                      |

`seed_demo` builds 14 types × 13 stations = 182 obligations and ~516 periods.

### The 13 stations

| Code | Station | Region | District |
|---|---|---|---|
| RSH-ITG-01 | Itigi | Singida | Itigi |
| RSH-KRT-02 | Karatu | Arusha | Karatu |
| RSH-LWL-03 | Liwale | Lindi | Liwale |
| RSH-MNY-04 | Manyoni | Singida | Manyoni |
| RSH-MSS-05 | Masasi | Mtwara | Masasi |
| RSH-MKL-06 | Mkalama | Singida | Mkalama |
| RSH-MLB-07 | Mlimba | Morogoro | Mlimba |
| RSH-NCH-08 | Nachingwea | Lindi | Nachingwea |
| RSH-NWL-09 | Newala | Mtwara | Newala |
| RSH-RNG-10 | Ruangwa | Lindi | Ruangwa |
| RSH-SHL-11 | Shelui | Singida | Iramba |
| RSH-SGD-12 | Singida | Singida | Singida Urban |
| RSH-UTT-13 | Utete | Pwani | Rufiji |

Five stations sit in Singida region, three in Lindi, two in Mtwara — so
`station_user` being many-to-many is not theoretical here: one manager
realistically covers the whole Singida cluster.

**The GPS coordinates in the seed are district-centre approximations.**
Replace each one with the station's real reading before the map goes in
front of anyone.

Switch to PostgreSQL by setting `DB_ENGINE=postgres` in `.env`. SQLite is the
default only so the project runs the moment you clone it.

---

## The one structural idea

Dates are **not** on the station and **not** on the compliance type. They live
on the intersection, and each renewal creates a new row rather than editing the
old one:

```
ComplianceType      "EWURA exists"                        ~14 rows
StationCompliance   "Kariakoo must hold EWURA"  permanent ~196 rows
CompliancePeriod    "Kariakoo's EWURA, Mar26–Mar27"       grows forever
ComplianceDocument  the certificate / the receipt         never deleted
```

Every station therefore has its own dates for every compliance — 196
independent windows, four possible statuses each. `default_validity_months` on
the type only *pre-fills* the renewal form; the real dates are per period and
are always overridable, because EWURA sometimes issues a 6-month licence.

**"Old receipts" is not a feature.** It is what happens when you never delete.
A renewal adds a period; the previous one becomes `superseded` and keeps its
own files forever.

---

## Rules that must not be broken

**1. Urgency comes from `core/bands.py`. Nowhere else.**

If you write `if days < 90` anywhere outside that module, the UI and the alerts
will disagree within a month. The card, the matrix cell, the map pin, the SMS
and the digest all call `band_for()`.

| Days left | Band | Meaning |
|---|---|---|
| < 0 | `expired` | operating unlicensed **right now** |
| 0–90 | `critical` | start the process today |
| 91–180 | `warning` | start planning |
| 181–365 | `active` | fine |
| > 365 | `safe` | invisible, needs no attention |
| — | `processing` | renewal in flight, not on the urgency scale |

`expired` and `critical` are separate on purpose. A licence with 80 days left is
**not expired** — telling a manager it is teaches him the word means nothing.

**2. Never touch `Model.objects` in a view.**

Django has no global scope. Always `.for_user(request.user)`, and put it *inside*
the lookup, not in an `if` afterwards.

**Watch the mixin trap.** Defining `get_queryset()` on a view *replaces*
`ScopedQuerysetMixin.get_queryset()` — it does not extend it. Inheriting the
mixin and then overriding the method silently drops the scope, and every page
still returns 200 while leaking. `ObligationDetailView` shipped that bug once
and a station manager could read another station's certificates. If you override
`get_queryset()`, apply `for_user()` inside it yourself.

```python
doc = get_object_or_404(
    ComplianceDocument.objects.for_user(request.user), pk=pk
)
```

Use the mixins in `core/mixins.py` so the safe path is the only path you type.
Forget it once and a Mwanza manager reads Kariakoo's certificates.

**3. Status is derived, never typed.**

The only automatic transition is `active → expired` when the date passes
(`compliance.services.expire_lapsed_periods`). Everything else happens because a
human uploaded something. If a person can set "Active" independently of the
expiry date, you will ship a green badge on a licence that lapsed a year ago.

**4. Documents are private.**

`MEDIA_URL` is `None` and there is no media route in `config/urls.py` — on
purpose. Files stream only through `compliance.views.serve_document`, which
checks station scope first. Do not point nginx at `MEDIA_ROOT`.

**5. The map is decorative, not geographic.**

No tiles, no Leaflet, no lat/lng on screen. Pins sit at hand-placed
positions on a 460x400 canvas (`dashboard.views.HomeView.MAP_XY`) that echo
the real shape of the network. Adding a station without a MAP_XY entry lays
it out on a spare arc rather than dropping it — a station missing from the
map is worse than one in a slightly odd place.

Pins pulse **only** when something needs action. If everything blinked, the
blinking would carry no information. A calm map means a calm estate.

**6. Pins get one bit of meaning, not five.**

`Station.worst_band()` is worst-of-14 and is pessimistic by construction —
a well-run station usually has *something* in the warning band, so a
worst-of pin goes orange permanently and stops carrying information.

Use `Station.map_band()` for the pin. It answers one question: **is this
station legally operating right now?** Expired → red. Nothing lapsed but
something due inside 90 days → orange. Otherwise → green. Deliberately
blind to the warning band. The counts belong in the popup, not the dot.

**7. Two palettes, never mixed.**

- **Brand** — green, orange, white. Sidebar, header, buttons, table headers,
  chips, rules. All chrome.
- **Status** — red, amber, green, blue. Pills, cell fills, day counts,
  numbered badges. Compliance state and nothing else.

A colour on any page either identifies Rashal or reports a state. Never both.
This is why compliance types carry no colour and no icon: type identity is
the short code set large. Give EWURA a green brand colour and FIRE a red one
and the FIRE card is alarming while all 13 stations are compliant — then red
stops meaning anything anywhere.

Do not give EWURA a green brand colour and Fire a red one. A permanently-red
FIRE card is alarming when all 14 stations are compliant, and then red stops
meaning anything. Type identity is `ComplianceType.icon`.

**8. Never delete a `NotificationLog` row.**

It is the dedupe guard *and* the audit record. Without it a compliance sitting
at 85 days trips the 90-day rung every morning for three months, everyone mutes
the system, and the alert that mattered is ignored too. **A muted system is
worse than no system** — it gives false confidence.

---

## Alerts

```bash
python manage.py scan_compliance --dry-run     # see what would go out
python manage.py scan_compliance               # send
python manage.py scan_compliance --date 2026-09-01   # pretend it is a date
```

Cron (no Celery — for a daily walk across 196 rows, cron is the right answer):

```
0 6 * * * cd /srv/rashal && python manage.py scan_compliance
```

Rungs are **per type** (`ComplianceType.alert_thresholds`) because Fire needs 30
days notice and EWURA needs six months. Escalation shape: at 12 months only the
person doing the work hears; at 30 days the boss hears. That is what gives it
teeth.

Suppression, all deliberate:

- only `is_current` periods on active stations (`CompliancePeriod.objects.alertable()`)
- perpetual types (TRA TIN) never alert
- `superseded` periods never alert — otherwise every archived 2019 certificate
  screams on day one of go-live
- SMS is dropped while a renewal is `processing` — somebody is already on it
- SMS only at 90 days and below; rungs 7 and 0 repeat daily, the rest fire once

**SMS:** keep `SMS_BACKEND=log` everywhere except production.
Apply for your Beem sender ID **now** — approval takes days and can be
rejected, and it is the one part of this project not in your control.
Verify Beem's payload shape against their current docs before going live;
the adapter in `alerts/channels.py` isolates it either way.

---

## The two-truths case

A station can be `processing` *and* operating unlicensed. `StationCompliance.band`
deliberately stays `expired` while a renewal is in flight — an in-flight renewal
does not soften the band. `is_in_processing` and `lapsed_period` expose the
second fact separately, so the screen can show both:

```
● EXPIRED 28 days ago          ⏳ renewal processing since 03 Feb
```

Collapse them into one and the manager relaxes while the station is illegal.

---

## Layout

```
config/       settings, urls
core/         bands.py ← the band function; mixins, roles, base model
accounts/     User (custom, M2M to stations), phone normalisation
stations/     Station + auto-provision signal
compliance/   the four models, services.py (transitions), private file serving
alerts/       NotificationLog (dedupe), channels (Beem adapter), scan command
dashboard/    views only, no models
```

`stations/signals.py` and `compliance/signals.py` keep the 196-cell grid
complete. They are signals rather than services because Setup is done in the
Django admin, which saves models directly — no view of ours runs.

---

## Known gaps (next phase)

- **Renewal wizard.** "Start renewal" currently links into the Django admin.
  The services are done and tested; the four-step screen is not built.
- **Document upload from the front end.** Upload happens in the admin for now.
  Viewing and downloading work everywhere, scoped.
- **Daily SMS cap per recipient.** A manager with 6 expiring items should get
  one SMS with a count, not six. Currently un-batched — with 36 expired
  obligations the scan sends ~200 SMS/day. Build this before turning
  `SMS_BACKEND=beem` on.
- **Weekly digest** (`send_digest` command) — Monday 07:00, scoped per user.
  Send it even when everything is green; a digest that only arrives with bad
  news trains people to fear the email.
- **Audit trail** for document views and downloads.
- **Renewal wizard** UI (the services are done and tested).
- Log the SMS subscription's own renewal date as an obligation. A compliance
  tracker whose alerting lapses unnoticed is a specific kind of embarrassing.
