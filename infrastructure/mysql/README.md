# GSMaP Japan MySQL

MySQL 8.4 LTS stores the Japan-only hourly GSMaP time series. The fact table is partitioned by UTC year and keeps both UTC and JST timestamps. Adminer provides a browser GUI, while port 3306 is available to MySQL CLI, Workbench, DBeaver, and other clients on the trusted LAN.

The source CSV directory is not mounted into the database container. The Python importer opens it locally for reading and sends rows with `LOAD DATA LOCAL`; successful daily imports are recorded so re-running is safe.

## Start

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure/mysql/start_mysql.ps1
```

Run the firewall setup once from an **Administrator PowerShell**:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure/mysql/configure_firewall.ps1
```

## Import

Preview completed daily CSVs without connecting to MySQL:

```powershell
python backend/scripts/import_gsmap_csv_to_mysql.py --start 2014-01-01 --end today --dry-run
```

Import all completed days. Days without 24 source hours are excluded by default, and unchanged completed files are skipped:

```powershell
python backend/scripts/import_gsmap_csv_to_mysql.py --start 2014-01-01 --end today
```

Use `--limit 1` for a one-day validation. Do not use `--include-incomplete` for the production table.

## Japan boundary polygons

Import the exact N03 prefecture polygon layer used to create the GSMaP land-overlap mask:

```powershell
python backend/scripts/import_japan_boundaries_to_mysql.py
```

Export all stored polygons as GeoJSON, or add `--prefecture-code 13000` for Tokyo only:

```powershell
python backend/scripts/export_japan_boundaries_from_mysql.py downloads/japan-land.geojson
```

The geometry column is restricted to SRID 4326 and has a spatial index. Dataset provenance, source SHA-256, record counts and bounds are stored in `japan_boundary_datasets`.

## Verify and remove large source files

After the complete rainfall import, verify without deleting:

```powershell
python backend/scripts/verify_and_cleanup_gsmap_sources.py --start 2014-01-01 --end today
```

After every count and signature check passes, delete only the two large `standard` trees:

```powershell
python backend/scripts/verify_and_cleanup_gsmap_sources.py --start 2014-01-01 --end today --yes
```

This retains the small `_mask` cache and the N03 archive for future incremental downloads.
## Access from another PC

- Adminer: `http://192.168.11.2:8081/`
- MySQL host/port: `192.168.11.2:3306`
- Database: `gsmap_japan`
- Read-only user: `gsmap_reader`
- Password: `MYSQL_READER_PASSWORD` in the ignored `.env.mysql` file

CLI example (the client prompts for the password):

```powershell
mysql -h 192.168.11.2 -P 3306 -u gsmap_reader -p gsmap_japan
```

The web GUI uses plain HTTP and is intentionally bound only to the trusted private LAN. Do not forward ports 3306 or 8081 from the internet router.

## Tables

- `gsmap_grid_cells`: 5,062 Japanese-land-overlapping GSMaP grid cells.
- `gsmap_hourly_rainfall`: UTC/JST time, grid reference, rain rate, numeric ID.
- `gsmap_import_files`: resumable/idempotent daily import history.
- `v_gsmap_hourly_rainfall`: joined view including grid ID and coordinates.

Persistent database files are stored in `D:/HomeServer/data/gsmap-mysql`.

Stop without deleting database files:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure/mysql/stop_mysql.ps1
```

Do not use `docker compose down -v`; the database is intentionally persisted at `MYSQL_DATA_DIR`.