# =============================================================================
# Utilitaire MinIO – Lecture / Écriture dans le Data Lake
# Utilise boto3 pour communiquer avec MinIO via le protocole S3.
# =============================================================================

import os
import json
import boto3
from botocore.client import Config


def get_minio_client():
    """
    Crée et retourne un client S3 (boto3) configuré pour MinIO.
    
    Les variables d'environnement utilisées :
      - MINIO_ENDPOINT : adresse du serveur MinIO (ex: minio:9000)
      - MINIO_ACCESS_KEY : clé d'accès
      - MINIO_SECRET_KEY : clé secrète
    """
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minio_user")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minio_password")

    client = boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",  # requis par boto3, ignoré par MinIO
    )
    return client


def list_objects(bucket: str, prefix: str = "") -> list:
    """
    Liste les objets dans un bucket MinIO.
    
    Args:
        bucket: Nom du bucket (raw, clean, curated)
        prefix: Préfixe pour filtrer (ex: "documents/")
    
    Returns:
        Liste de clés d'objets trouvés
    """
    client = get_minio_client()
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = response.get("Contents", [])
        return [obj["Key"] for obj in objects]
    except Exception as e:
        print(f"[MinIO] Erreur lors du listage de {bucket}/{prefix} : {e}")
        return []


def download_file(bucket: str, key: str, local_path: str) -> str:
    """
    Télécharge un fichier depuis MinIO vers le système local.
    
    Args:
        bucket: Nom du bucket source
        key: Clé de l'objet dans le bucket
        local_path: Chemin local de destination
    
    Returns:
        Chemin local du fichier téléchargé
    """
    client = get_minio_client()
    client.download_file(bucket, key, local_path)
    print(f"[MinIO] Téléchargé : s3://{bucket}/{key} -> {local_path}")
    return local_path


def upload_file(bucket: str, key: str, local_path: str) -> str:
    """
    Upload un fichier local vers MinIO.
    
    Args:
        bucket: Nom du bucket destination
        key: Clé de l'objet dans le bucket
        local_path: Chemin local du fichier à uploader
    
    Returns:
        Clé S3 de l'objet uploadé
    """
    client = get_minio_client()
    client.upload_file(local_path, bucket, key)
    print(f"[MinIO] Uploadé : {local_path} -> s3://{bucket}/{key}")
    return key


def upload_json(bucket: str, key: str, data: dict) -> str:
    """
    Upload un dictionnaire Python en tant que fichier JSON dans MinIO.
    
    Args:
        bucket: Nom du bucket destination
        key: Clé de l'objet (doit finir en .json)
        data: Dictionnaire Python à sérialiser en JSON
    
    Returns:
        Clé S3 de l'objet uploadé
    """
    client = get_minio_client()
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_bytes,
        ContentType="application/json",
    )
    print(f"[MinIO] JSON uploadé : s3://{bucket}/{key} ({len(json_bytes)} bytes)")
    return key


def download_json(bucket: str, key: str) -> dict:
    """
    Télécharge et parse un fichier JSON depuis MinIO.
    
    Args:
        bucket: Nom du bucket source
        key: Clé de l'objet JSON
    
    Returns:
        Dictionnaire Python avec le contenu du JSON
    """
    client = get_minio_client()
    response = client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    data = json.loads(content)
    print(f"[MinIO] JSON téléchargé : s3://{bucket}/{key}")
    return data


def get_file_bytes(bucket: str, key: str) -> bytes:
    """
    Télécharge le contenu brut d'un fichier depuis MinIO (en mémoire).
    
    Args:
        bucket: Nom du bucket source
        key: Clé de l'objet
    
    Returns:
        Contenu brut en bytes
    """
    client = get_minio_client()
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()
