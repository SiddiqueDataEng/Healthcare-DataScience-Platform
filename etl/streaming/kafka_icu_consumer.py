"""
Real-Time Streaming Pipeline: ICU Vitals + Wearable Data
Uses Kafka + Spark Structured Streaming

Architecture:
  ICU Monitors → Kafka Topic → Spark Streaming → 
  Delta Lake (raw) → Feature Store → ML Model → Alerts

Alert rules implemented:
  - Critical HR (<40 or >150 bpm)
  - Hypoxia (SpO2 < 88%)
  - Hypotension (MAP < 65 mmHg)
  - Fever (Temp > 39.5°C)
  - Bradypnea/Tachypnea

Usage:
    python etl/streaming/kafka_icu_consumer.py
"""

import json
import os
from datetime import datetime
from loguru import logger

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        StructType, StructField, StringType, IntegerType,
        DoubleType, BooleanType, TimestampType
    )
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    logger.warning("PySpark not available — showing streaming pipeline design only.")

try:
    from confluent_kafka import Producer, Consumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False


# ─── Schemas ─────────────────────────────────────────────────────────

ICU_VITALS_SCHEMA = StructType([
    StructField("patient_id",              StringType(),  True),
    StructField("hospital_id",             StringType(),  True),
    StructField("bed_id",                  StringType(),  True),
    StructField("timestamp",               StringType(),  True),
    StructField("heart_rate",              IntegerType(), True),
    StructField("blood_pressure_sys",      IntegerType(), True),
    StructField("blood_pressure_dia",      IntegerType(), True),
    StructField("mean_arterial_pressure",  IntegerType(), True),
    StructField("spo2",                    DoubleType(),  True),
    StructField("respiration_rate",        IntegerType(), True),
    StructField("temperature",             DoubleType(),  True),
    StructField("on_ventilator",           BooleanType(), True),
    StructField("fio2",                    DoubleType(),  True),
    StructField("alarm_triggered",         BooleanType(), True),
    StructField("alarm_type",              StringType(),  True),
    StructField("device_id",               StringType(),  True),
]) if SPARK_AVAILABLE else None


# ─── Alert Definitions ───────────────────────────────────────────────

ALERT_RULES = {
    "CRITICAL_TACHYCARDIA":  ("heart_rate", ">", 150, "CRITICAL"),
    "CRITICAL_BRADYCARDIA":  ("heart_rate", "<", 40,  "CRITICAL"),
    "HYPOXIA_CRITICAL":      ("spo2",       "<", 88,  "CRITICAL"),
    "HYPOXIA_WARNING":       ("spo2",       "<", 92,  "WARNING"),
    "HYPOTENSION_CRITICAL":  ("mean_arterial_pressure", "<", 65, "CRITICAL"),
    "HYPERTENSION_CRITICAL": ("blood_pressure_sys",     ">", 200, "CRITICAL"),
    "FEVER_HIGH":            ("temperature", ">", 39.5, "WARNING"),
    "HYPOTHERMIA":           ("temperature", "<", 35.0, "CRITICAL"),
    "TACHYPNEA":             ("respiration_rate", ">", 30, "WARNING"),
    "BRADYPNEA":             ("respiration_rate", "<", 8,  "CRITICAL"),
}


def build_alert_condition(df, rule_name, field, operator, threshold, severity):
    """Build a streaming alert condition."""
    if operator == ">":
        condition = F.col(field) > threshold
    elif operator == "<":
        condition = F.col(field) < threshold
    else:
        condition = F.lit(False)

    return (
        df
        .filter(condition & F.col(field).isNotNull())
        .withColumn("alert_type",     F.lit(rule_name))
        .withColumn("alert_severity", F.lit(severity))
        .withColumn("alert_value",    F.col(field).cast(DoubleType()))
        .withColumn("threshold",      F.lit(float(threshold)))
        .withColumn("alert_time",     F.current_timestamp())
        .withColumn("alert_message",
            F.concat(
                F.lit(f"[{severity}] {rule_name}: "),
                F.col(field).cast(StringType()),
                F.lit(f" (threshold: {threshold})")
            )
        )
    )


def create_icu_streaming_pipeline(spark, kafka_servers: str, input_topic: str, output_path: str):
    """
    Create Spark Structured Streaming pipeline for ICU vitals.
    
    Reads from Kafka, applies transforms, writes to Delta Lake.
    Fires alerts for critical vital signs.
    """
    # ── Read from Kafka ───────────────────────────────────────────
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_servers)
        .option("subscribe", input_topic)
        .option("startingOffsets", "latest")
        .option("maxOffsetsPerTrigger", 100000)  # backpressure
        .option("failOnDataLoss", "false")
        .load()
    )

    # ── Parse JSON payload ────────────────────────────────────────
    parsed_df = (
        kafka_df
        .select(
            F.from_json(F.col("value").cast("string"), ICU_VITALS_SCHEMA).alias("data"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.col("partition"),
            F.col("offset"),
        )
        .select("data.*", "kafka_timestamp", "partition", "offset")
        .withColumn("event_timestamp", F.to_timestamp("timestamp"))
    )

    # ── Derived vital features ────────────────────────────────────
    enriched_df = (
        parsed_df
        .withColumn("pulse_pressure",
            F.col("blood_pressure_sys") - F.col("blood_pressure_dia"))
        .withColumn("shock_index",
            F.col("heart_rate") / F.when(
                F.col("blood_pressure_sys") > 0, F.col("blood_pressure_sys")
            ).otherwise(F.lit(1.0)))
        .withColumn("is_critical_vitals",
            (F.col("heart_rate") < 40) | (F.col("heart_rate") > 150) |
            (F.col("spo2") < 88) |
            (F.col("mean_arterial_pressure") < 65) |
            (F.col("temperature") > 40.0) | (F.col("temperature") < 35.0)
        )
        .withColumn("ingestion_timestamp", F.current_timestamp())
    )

    # ── Write raw stream to Delta Lake (append mode) ──────────────
    raw_stream = (
        enriched_df.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{output_path}/checkpoints/icu_vitals_raw")
        .partitionBy("hospital_id")
        .trigger(processingTime="10 seconds")  # micro-batch every 10s
        .start(f"{output_path}/delta/icu_vitals")
    )

    # ── Alert stream: filter critical events ─────────────────────
    critical_df = enriched_df.filter(F.col("is_critical_vitals") == True)

    # Build individual alert streams
    alert_streams = []
    for rule_name, (field, op, threshold, severity) in ALERT_RULES.items():
        alert_df = build_alert_condition(enriched_df, rule_name, field, op, threshold, severity)
        alert_streams.append(alert_df)

    if alert_streams:
        from functools import reduce
        all_alerts = reduce(lambda a, b: a.union(b.select(a.columns)), alert_streams)

        # Write alerts to separate Delta table + trigger notifications
        alert_stream = (
            all_alerts
            .select("patient_id", "hospital_id", "bed_id", "event_timestamp",
                    "alert_type", "alert_severity", "alert_value", "threshold", "alert_message")
            .writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", f"{output_path}/checkpoints/icu_alerts")
            .trigger(processingTime="5 seconds")   # faster for critical alerts
            .foreachBatch(notify_alert_batch)       # custom alert notification
            .start(f"{output_path}/delta/icu_alerts")
        )

    # ── 5-minute rolling aggregations ────────────────────────────
    windowed_stats = (
        enriched_df
        .withWatermark("event_timestamp", "10 minutes")
        .groupBy(
            F.window("event_timestamp", "5 minutes", "1 minute"),
            "patient_id", "hospital_id", "bed_id"
        )
        .agg(
            F.avg("heart_rate").alias("avg_hr"),
            F.min("heart_rate").alias("min_hr"),
            F.max("heart_rate").alias("max_hr"),
            F.avg("spo2").alias("avg_spo2"),
            F.min("spo2").alias("min_spo2"),
            F.avg("mean_arterial_pressure").alias("avg_map"),
            F.avg("respiration_rate").alias("avg_rr"),
            F.avg("temperature").alias("avg_temp"),
            F.sum(F.col("alarm_triggered").cast("int")).alias("alarm_count"),
            F.sum(F.col("is_critical_vitals").cast("int")).alias("critical_count"),
            F.count("*").alias("reading_count"),
        )
    )

    windowed_stream = (
        windowed_stats.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{output_path}/checkpoints/icu_windowed")
        .trigger(processingTime="1 minute")
        .start(f"{output_path}/delta/icu_vitals_windowed_5min")
    )

    return raw_stream


def notify_alert_batch(batch_df, batch_id):
    """
    Called for each micro-batch of critical alerts.
    In production: send to PagerDuty / hospital alert system / SMS.
    """
    if batch_df.count() == 0:
        return

    critical_alerts = batch_df.filter(F.col("alert_severity") == "CRITICAL")
    n_critical = critical_alerts.count()

    if n_critical > 0:
        logger.warning(f"Batch {batch_id}: {n_critical} CRITICAL alerts!")
        # TODO: integrate with hospital alert system
        # requests.post(ALERT_WEBHOOK_URL, json={"alerts": critical_alerts.collect()})
        # boto3.client("sns").publish(...)


class KafkaProducerSimulator:
    """Simulate ICU device data producer for development/testing."""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "healthcare.icu.vitals"):
        self.topic = topic
        self.producer = None
        if KAFKA_AVAILABLE:
            self.producer = Producer({"bootstrap.servers": bootstrap_servers})

    def generate_vital_reading(self, patient_id: str, hospital_id: str) -> dict:
        import random
        return {
            "patient_id":             patient_id,
            "hospital_id":            hospital_id,
            "bed_id":                 f"ICU-BED-{random.randint(1,20):03d}",
            "timestamp":              datetime.now().isoformat(),
            "heart_rate":             int(random.gauss(78, 18)),
            "blood_pressure_sys":     int(random.gauss(118, 20)),
            "blood_pressure_dia":     int(random.gauss(76, 12)),
            "mean_arterial_pressure": int(random.gauss(90, 15)),
            "spo2":                   round(random.gauss(97.2, 1.8), 1),
            "respiration_rate":       int(random.gauss(16, 4)),
            "temperature":            round(random.gauss(37.0, 0.6), 2),
            "on_ventilator":          random.random() < 0.25,
            "fio2":                   None,
            "alarm_triggered":        random.random() < 0.05,
            "alarm_type":             None,
            "device_id":              f"ICU-MONITOR-{random.randint(1000,9999)}",
        }

    def produce_readings(self, patient_ids: list, n_readings: int = 1000):
        """Continuously produce simulated ICU readings to Kafka."""
        import random
        import time

        logger.info(f"Producing {n_readings} ICU readings to {self.topic} ...")
        for i in range(n_readings):
            patient_id = random.choice(patient_ids)
            reading = self.generate_vital_reading(patient_id, "H001")

            if self.producer:
                self.producer.produce(
                    self.topic,
                    key=patient_id.encode(),
                    value=json.dumps(reading).encode(),
                )
                if i % 100 == 0:
                    self.producer.flush()
            else:
                if i % 100 == 0:
                    logger.info(f"[Kafka not available] Simulated {i} readings ...")

            time.sleep(0.005)  # simulate 5-second cadence (200 msg/sec for demo)

        if self.producer:
            self.producer.flush()
        logger.success("Producer complete.")


if __name__ == "__main__":
    if SPARK_AVAILABLE:
        spark = SparkSession.builder \
            .appName("ICU Streaming") \
            .master("local[*]") \
            .config("spark.sql.streaming.schemaInference", "true") \
            .getOrCreate()

        kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        output_path = "./data/streaming"

        logger.info("Starting ICU vitals streaming pipeline ...")
        stream = create_icu_streaming_pipeline(
            spark, kafka_servers, "healthcare.icu.vitals", output_path
        )
        stream.awaitTermination()
    else:
        logger.info("Demonstrating Kafka producer (no Spark) ...")
        sim = KafkaProducerSimulator()
        sim.produce_readings(
            patient_ids=[f"P{i:07d}" for i in range(100)],
            n_readings=100,
        )
