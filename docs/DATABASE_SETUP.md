# Setting up the database (PostgreSQL)

From M2 the app keeps its data in PostgreSQL instead of JSON files. You do this once per computer.

## 1. Install PostgreSQL (Windows)

1. Download the Windows installer from https://www.postgresql.org/download/windows/ (the "EDB" installer). Pick the newest version.
2. Run it and keep the defaults, with two exceptions:
   - **Password for the `postgres` user:** choose one and write it down. This is the database administrator account, separate from the app's own account.
   - **Stack Builder** at the end: untick it. Nothing from it is needed.
3. The installer is signed by its publisher, so Smart App Control should allow it. If Windows blocks it anyway, tell me.

Mac: `brew install postgresql@17 && brew services start postgresql@17`. Ubuntu: `sudo apt install postgresql`.

## 2. Create the app's database

Open **SQL Shell (psql)** from the Start menu. Press Enter to accept each default (server, database, port, username) and type the `postgres` password when asked. Then paste:

```sql
CREATE USER empoweredcare PASSWORD 'empoweredcare';
CREATE DATABASE empoweredcare OWNER empoweredcare;
\q
```

The password here is `empoweredcare`. That's fine on your own PC; use a strong one on any shared or server machine.

## 3. Tell the app where it is

In `.env`, using the password from step 2:
```
DATABASE_URL=postgresql+psycopg://empoweredcare:empoweredcare@localhost:5432/empoweredcare
```

## 4. Create the tables

In the project folder, with `(.venv)` active:
```
pip install -r requirements.txt
alembic upgrade head
```
✅ The last line says `Running upgrade -> ..., initial schema`.

`alembic` is the tool that creates and updates tables. When a later update changes the tables, run `alembic upgrade head` again after pulling. It only applies what's new and keeps your data.

## 5. Copy your existing reports into the database

The reports you had in `models/outbreak_data.json` move over with one command. It's safe to run more than once: reports already copied are skipped, and the JSON file isn't changed.
```
python scripts\migrate_json.py --dry-run
python scripts\migrate_json.py
```
✅ It ends with `The database now holds N reports.`

From now on the app reads and writes reports in the database only.

Reports whose AI analysis failed are flagged in the database. Re-run them when you have AI quota; the backend can stay running:
```
python scripts\reprocess_failed.py --dry-run
python scripts\reprocess_failed.py
```

## 6. Load Ethiopia's official boundaries (OCHA)

These give the app the official list of regions, zones and woredas with their codes (P-codes). Two things depend on it: the geocoder, which turns "Jimma zone, Seka Chekorsa" into a woreda code, and the M5 map.

1. In your browser, open https://data.humdata.org/dataset/cod-ab-eth and download the boundary files: the shapefile zip(s) for admin levels 1, 2 and 3. If one zip holds all levels, extract it and use the level 1/2/3 `.shp` files.
2. Optionally, download the population table from https://data.humdata.org/dataset/cod-ps-eth (a CSV with `ADM3_PCODE` and a total-population column).
3. Check first, then load. Use your file names:
   ```
   python scripts\load_boundaries.py --adm1 eth_admbnda_adm1.zip --adm2 eth_admbnda_adm2.zip --adm3 eth_admbnda_adm3.zip --population eth_admpop_adm3.csv --dry-run
   python scripts\load_boundaries.py --adm1 eth_admbnda_adm1.zip --adm2 eth_admbnda_adm2.zip --adm3 eth_admbnda_adm3.zip --population eth_admpop_adm3.csv
   ```
   ✅ It reports how many regions, zones and woredas it loaded, and how many neighbouring pairs it found.
4. Attach codes to the reports already stored, then restart the backend so new reports get codes too:
   ```
   python scripts\geocode_signals.py
   ```

If a place name fits more than one woreda (some woreda names repeat across regions), it's **flagged as ambiguous** with the candidates listed. It is never guessed. If the loader says it can't find `ADM3_PCODE` / `ADM3_EN` columns, send me the column list it prints.

## 7. Check it (optional)

```
python -m pytest tests -q
```
This uses a throwaway in-memory database, so it doesn't touch your data. To run the same tests against PostgreSQL, first create a second, empty database called `empoweredcare_test`, the same way as in step 2. Then:
```
$env:TEST_DATABASE_URL="postgresql+psycopg://empoweredcare:empoweredcare@localhost:5432/empoweredcare_test"
python -m pytest tests -q
```

## If something goes wrong

| Message | Meaning | Fix |
|---|---|---|
| `connection refused` / `could not connect to server` | PostgreSQL isn't running | Start menu → **Services** → `postgresql-x64-NN` → Start |
| `password authentication failed for user "empoweredcare"` | The password in `DATABASE_URL` doesn't match step 2 | Fix `.env`, or run `ALTER USER empoweredcare PASSWORD '...';` in SQL Shell |
| `database "empoweredcare" does not exist` | Step 2 wasn't completed | Run the `CREATE DATABASE` line |
| `No module named psycopg` | Packages not installed in this `.venv` | `pip install -r requirements.txt` with `(.venv)` active |

## What's in the database

These tables are created by `alembic upgrade head`. Their definitions are in `db/models.py`, and the reasons for them are in SYSTEM_SPEC section 3.

| Table | Holds |
|---|---|
| `org_units` | Regions, zones and woredas with official OCHA codes (P-codes), parents, population and other spellings |
| `org_unit_adjacency` | Which units share a border, used to see how outbreaks spread to neighbours |
| `boundary_crosswalk` | Old units mapped to new ones (for example the SNNPR split), so old data stays usable |
| `indicator_counts` | Weekly case counts per unit and disease (PHEM / DHIS2) |
| `immunization` | Monthly measles vaccination per unit |
| `campaigns` | Vaccination campaigns |
| `signals` | Every submitted report, upload or field alert, with the AI's reading and its review status |
| `alerts` | Tiered alerts (red/orange/yellow), from M5 |
| `risk_scores` | Monthly measles risk per unit, from M3 |
| `evaluations` | Results of model testing runs, from M3 |
