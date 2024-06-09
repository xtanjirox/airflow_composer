import polars as pl
import gcsfs


def calculate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    metrics = df.group_by(
        pl.col('date').cast(pl.Date),
        pl.col('date').cast(pl.Date).dt.year().alias('year'),
        pl.col('date').cast(pl.Date).dt.month().alias('month'),
        pl.col('date').cast(pl.Date).dt.day().alias('day'),
        pl.col('model')
    ).agg(pl.sum("failure").alias('failure_count'))
    return metrics


def write_parquets(df: pl.LazyFrame, path: str) -> None:
    df = df.collect()
    fs = gcsfs.GCSFileSystem(project='mz-data-manipulation')
    with fs.open(path, mode='wb') as f:
        df.write_parquet(f)


def statistics_calculator(source_path: str, target_path: str) -> None:
    df = pl.scan_parquet(source_path)
    metrics = calculate_metrics(df)
    write_parquets(
        metrics, target_path)


def execute_function(request):
    source_path = 'gs://mz-data-bucket/2013/source/*.parquet'
    target_path = 'gs://mz-data-bucket/2013/target/metrics.parquet'
    statistics_calculator(source_path, target_path)
    print('done Mehdi')
    return {'data': 200}
