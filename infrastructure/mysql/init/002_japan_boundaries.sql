USE gsmap_japan;

CREATE TABLE IF NOT EXISTS japan_boundary_datasets (
  dataset_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  dataset_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  source_archive VARCHAR(255) NOT NULL,
  source_layer VARCHAR(128) NOT NULL,
  source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  reference_date DATE NOT NULL,
  source_feature_count INT UNSIGNED NOT NULL,
  imported_feature_count INT UNSIGNED NULL,
  minimum_longitude DOUBLE NULL,
  minimum_latitude DOUBLE NULL,
  maximum_longitude DOUBLE NULL,
  maximum_latitude DOUBLE NULL,
  import_status ENUM('loading', 'completed', 'failed') NOT NULL,
  imported_at TIMESTAMP NULL,
  error_message VARCHAR(1000) NULL,
  PRIMARY KEY (dataset_id),
  UNIQUE KEY uq_boundary_dataset_key (dataset_key)
) ENGINE=InnoDB
  COMMENT='Provenance and verification metadata for Japanese administrative boundary datasets';

CREATE TABLE IF NOT EXISTS japan_land_polygons (
  polygon_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  dataset_id SMALLINT UNSIGNED NOT NULL,
  source_record_number INT UNSIGNED NOT NULL,
  prefecture_code CHAR(5) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  prefecture_name VARCHAR(20) NOT NULL,
  source_attributes JSON NOT NULL,
  geometry GEOMETRY NOT NULL SRID 4326,
  PRIMARY KEY (polygon_id),
  UNIQUE KEY uq_boundary_source_record (dataset_id, source_record_number),
  KEY idx_boundary_prefecture (prefecture_code, dataset_id),
  SPATIAL KEY spx_boundary_geometry (geometry),
  CONSTRAINT fk_boundary_dataset
    FOREIGN KEY (dataset_id) REFERENCES japan_boundary_datasets (dataset_id)
) ENGINE=InnoDB
  COMMENT='N03 polygon features used to select GSMaP cells overlapping Japanese land';

CREATE OR REPLACE VIEW v_japan_land_polygons AS
SELECT
  polygon.polygon_id,
  dataset.dataset_key,
  dataset.reference_date,
  polygon.source_record_number,
  polygon.prefecture_code,
  polygon.prefecture_name,
  polygon.source_attributes,
  polygon.geometry
FROM japan_land_polygons AS polygon
JOIN japan_boundary_datasets AS dataset
  ON dataset.dataset_id = polygon.dataset_id
WHERE dataset.import_status = 'completed';
