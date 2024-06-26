from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

import polars as pl

from airflow.providers.apprise.notifications.apprise import send_apprise_notification
from apprise import NotifyType

from airflow.providers.google.cloud.operators.functions import CloudFunctionInvokeFunctionOperator

from google.oauth2 import service_account
import google.auth.transport.requests

default_args = {
    'owner': 'mehdizarria',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}


def print_df(ti=None, **kwargs):
    lazy_df = ti.xcom_pull(task_ids='read_files')
    print(lazy_df.collect().head())


def generate_token(path, target_audience):
    creds = service_account.IDTokenCredentials.from_service_account_file(
        path,
        target_audience=target_audience)
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    return creds.token


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
    df.sink_parquet(path, compression='snappy')


def statistics_calculator(source_path: str, target_path: str) -> None:
    df = pl.scan_csv(source_path)
    metrics = calculate_metrics(df)
    write_parquets(
        metrics, target_path)


with DAG(
    default_args=default_args,
    dag_id='metrics_calculator',
    description='calculate metrics per year',
    start_date=datetime.now(),
    schedule_interval='@daily',
    catchup=False,
    on_success_callback=send_apprise_notification(
        title="Airflow Dag Succeed",
        body_format='markdown',
        body="This is the body of your message. It can contain multiple lines and paragraphs for a detailed explanation.\n[Click Here for Logs]({{ task_instance.log_url }})",
        notify_type=NotifyType.SUCCESS,
        apprise_conn_id='apprise_conn_id',
        tag='alerts'
    )
) as calculate_metrics_dag:

    start_empty_task = EmptyOperator(task_id='start_job')

    cloud_function_task = CloudFunctionInvokeFunctionOperator(
        task_id='cloud_function_task',
        gcp_conn_id='gcp_connection',
        function_id='function-1',
        location='europe-west1',
        project_id='mz-data-manipulation',
        input_data={}
    )

    end_empty_task = EmptyOperator(task_id='end_job')

    start_empty_task >> cloud_function_task >> end_empty_task
