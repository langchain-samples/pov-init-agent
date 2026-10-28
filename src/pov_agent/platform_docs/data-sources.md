# Connecting data sources

## Adding a data source
Administrators add data sources from **Data Engineering → Data Sources → Add New Data Source**.
Supported types include S3-compatible object stores, NFS shares, and SQL databases and
lakehouse table formats (such as Iceberg and Delta Lake) queried through the built-in SQL
query engine. Credentials are entered once, at the data-source level, so individual users
never handle the storage keys.

## Using a data source
Once added, a data source is:
- browsable from the **Data Sources** page,
- mounted read-only in every notebook server under `/mnt/datasources/<data-source-name>`, and
- queryable with SQL from notebooks and dashboards through the query engine.

Members can use any configured data source but cannot add new ones; ask a platform
administrator to connect a new source.
