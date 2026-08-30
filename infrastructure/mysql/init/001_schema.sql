CREATE DATABASE IF NOT EXISTS gsmap_japan
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE gsmap_japan;

CREATE TABLE IF NOT EXISTS gsmap_grid_cells (
  grid_cell_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  grid_id CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  grid_row SMALLINT UNSIGNED NOT NULL,
  grid_column SMALLINT UNSIGNED NOT NULL,
  latitude DECIMAL(5, 2) NOT NULL,
  longitude DECIMAL(5, 2) NOT NULL,
  PRIMARY KEY (grid_cell_id),
  UNIQUE KEY uq_grid_id (grid_id),
  UNIQUE KEY uq_grid_position (grid_row, grid_column),
  KEY idx_latitude_longitude (latitude, longitude)
) ENGINE=InnoDB
  COMMENT='Original 0.1-degree GSMaP cells having positive-area overlap with Japanese land';

CREATE TABLE IF NOT EXISTS gsmap_hourly_rainfall (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  observation_time_utc DATETIME NOT NULL,
  observation_time_jst DATETIME NOT NULL,
  grid_cell_id SMALLINT UNSIGNED NOT NULL,
  rain_rate_mm_h FLOAT NOT NULL,
  PRIMARY KEY (id, observation_time_utc),
  UNIQUE KEY uq_utc_grid (observation_time_utc, grid_cell_id),
  KEY idx_grid_utc (grid_cell_id, observation_time_utc),
  KEY idx_jst_grid (observation_time_jst, grid_cell_id),
  CONSTRAINT chk_jst_offset CHECK (
    observation_time_jst = DATE_ADD(observation_time_utc, INTERVAL 9 HOUR)
  ),
  CONSTRAINT chk_rain_value CHECK (
    rain_rate_mm_h >= -2 OR rain_rate_mm_h IN (-4, -8, -99)
  )
) ENGINE=InnoDB
  COMMENT='Japan-only GSMaP hourly rainfall; grid_cell_id logically references gsmap_grid_cells'
PARTITION BY RANGE COLUMNS (observation_time_utc) (
  PARTITION p2014 VALUES LESS THAN ('2015-01-01'),
  PARTITION p2015 VALUES LESS THAN ('2016-01-01'),
  PARTITION p2016 VALUES LESS THAN ('2017-01-01'),
  PARTITION p2017 VALUES LESS THAN ('2018-01-01'),
  PARTITION p2018 VALUES LESS THAN ('2019-01-01'),
  PARTITION p2019 VALUES LESS THAN ('2020-01-01'),
  PARTITION p2020 VALUES LESS THAN ('2021-01-01'),
  PARTITION p2021 VALUES LESS THAN ('2022-01-01'),
  PARTITION p2022 VALUES LESS THAN ('2023-01-01'),
  PARTITION p2023 VALUES LESS THAN ('2024-01-01'),
  PARTITION p2024 VALUES LESS THAN ('2025-01-01'),
  PARTITION p2025 VALUES LESS THAN ('2026-01-01'),
  PARTITION p2026 VALUES LESS THAN ('2027-01-01'),
  PARTITION p2027 VALUES LESS THAN ('2028-01-01'),
  PARTITION p2028 VALUES LESS THAN ('2029-01-01'),
  PARTITION p2029 VALUES LESS THAN ('2030-01-01'),
  PARTITION p2030 VALUES LESS THAN ('2031-01-01'),
  PARTITION p_future VALUES LESS THAN (MAXVALUE)
);

CREATE TABLE IF NOT EXISTS gsmap_import_files (
  file_path VARCHAR(512) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  observation_date DATE NOT NULL,
  file_size BIGINT UNSIGNED NOT NULL,
  file_mtime_ns BIGINT UNSIGNED NOT NULL,
  expected_rows INT UNSIGNED NOT NULL,
  imported_rows INT UNSIGNED NULL,
  import_status ENUM('loading', 'completed', 'failed') NOT NULL,
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP NULL,
  error_message VARCHAR(1000) NULL,
  PRIMARY KEY (file_path),
  KEY idx_import_date_status (observation_date, import_status)
) ENGINE=InnoDB;

CREATE OR REPLACE VIEW v_gsmap_hourly_rainfall AS
SELECT
  rainfall.id,
  rainfall.observation_time_utc,
  rainfall.observation_time_jst,
  grid.grid_id,
  grid.grid_row,
  grid.grid_column,
  grid.latitude,
  grid.longitude,
  rainfall.rain_rate_mm_h
FROM gsmap_hourly_rainfall AS rainfall
JOIN gsmap_grid_cells AS grid
  ON grid.grid_cell_id = rainfall.grid_cell_id;
