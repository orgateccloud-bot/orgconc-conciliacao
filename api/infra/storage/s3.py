"""S3StorageGateway — Supabase Storage / AWS S3 / MinIO / etc.

Configuracao via env:
- ORGCONC_STORAGE_BACKEND=s3       (toggle)
- S3_BUCKET                         (obrigatorio)
- S3_PREFIX                         (default: "orgconc/")
- S3_ENDPOINT_URL                   (Supabase: https://<proj>.supabase.co/storage/v1/s3, MinIO: http://minio:9000)
- S3_REGION                         (default: us-east-1)
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY   (boto3 padrao)

Keys no S3:
- {prefix}/datasets/{rid}.json
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException


class S3StorageGateway:
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "orgconc",
        endpoint_url: str | None = None,
        region: str = "us-east-1",
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    @classmethod
    def from_env(cls) -> "S3StorageGateway":
        bucket = os.environ.get("S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("S3_BUCKET obrigatorio quando ORGCONC_STORAGE_BACKEND=s3")
        return cls(
            bucket=bucket,
            prefix=os.environ.get("S3_PREFIX", "orgconc").strip("/"),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
            region=os.environ.get("S3_REGION", "us-east-1"),
        )

    def _key(self, rid: str) -> str:
        return f"{self.prefix}/datasets/{rid}.json"

    def salvar_dataset(
        self,
        extratos: list[dict],
        anomalias: list[dict],
        relatorio: str,
        owner_sub: str | None = None,
    ) -> str:
        rid = uuid.uuid4().hex[:12]
        payload = {
            "extratos": extratos,
            "anomalias": anomalias,
            "relatorio": relatorio,
            "owner_sub": owner_sub,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._client.put_object(
            Bucket=self.bucket,
            Key=self._key(rid),
            Body=body,
            ContentType="application/json; charset=utf-8",
            CacheControl="private, max-age=300",
            Metadata={
                "owner_sub": owner_sub or "anonymous",
            },
        )
        return rid

    def carregar_dataset(self, rid: str, verify_sub: str | None = None) -> dict[str, Any]:
        if not re.fullmatch(r"[a-f0-9]{12}", rid):
            raise HTTPException(status_code=400, detail="ID invalido")
        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=self._key(rid))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise HTTPException(status_code=404, detail="Relatorio nao encontrado") from exc
            raise HTTPException(status_code=502, detail=f"Storage error: {code}") from exc

        data = json.loads(obj["Body"].read())
        if verify_sub and data.get("owner_sub") != verify_sub:
            raise HTTPException(status_code=403, detail="Acesso negado a este relatorio")
        return data
