"""Service de feature flags com cache curto (60s) para reduzir hits ao DB.

Uso:
    ff = await get_feature_flags()
    if await ff.is_enabled("conciliacao_multi_modelo", {"org_id": str(org)}):
        ...

Avaliacao de rollout_rules (JSONB):
- {"orgs": ["uuid1", "uuid2"]}      -> habilita so para essas orgs
- {"planos": ["pro", "enterprise"]} -> habilita por plano
- {"percent": 25}                   -> habilita 25% (hash do org_id)
- {} ou ausente                     -> usa `enabled` direto

Quando `enabled=false`, NUNCA habilita (kill switch). Quando `enabled=true`,
rollout_rules pode filtrar mais (whitelist) — vazio = todo mundo.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.db.models import FeatureFlag

log = logging.getLogger("orgconc.featureflags")

_CACHE_TTL_S = 60.0


@dataclass
class _Snapshot:
    flags: dict[str, dict[str, Any]]   # key -> {enabled, rules}
    ts: float


class FeatureFlagsService:
    def __init__(self) -> None:
        self._cache: _Snapshot | None = None

    async def _carregar(self) -> _Snapshot:
        if not DB_DISPONIVEL or SessionLocal is None:
            return _Snapshot(flags={}, ts=time.time())
        async with SessionLocal() as db:
            rows = await db.execute(select(FeatureFlag))
            flags: dict[str, dict[str, Any]] = {}
            for ff in rows.scalars().all():
                try:
                    rules = json.loads(ff.rollout_rules) if ff.rollout_rules else {}
                except json.JSONDecodeError:
                    rules = {}
                flags[ff.key] = {"enabled": ff.enabled, "rules": rules}
        return _Snapshot(flags=flags, ts=time.time())

    async def _snap(self) -> _Snapshot:
        if self._cache is None or (time.time() - self._cache.ts) > _CACHE_TTL_S:
            self._cache = await self._carregar()
        return self._cache

    async def is_enabled(self, key: str, context: dict[str, str] | None = None) -> bool:
        snap = await self._snap()
        flag = snap.flags.get(key)
        if flag is None or not flag["enabled"]:
            return False
        rules = flag["rules"]
        if not rules:
            return True

        ctx = context or {}
        if "orgs" in rules:
            if ctx.get("org_id") not in rules["orgs"]:
                return False
        if "planos" in rules:
            if ctx.get("plano") not in rules["planos"]:
                return False
        if "percent" in rules:
            pct = int(rules["percent"])
            seed = ctx.get("org_id") or ctx.get("sub") or "anon"
            bucket = int(hashlib.md5(f"{key}:{seed}".encode()).hexdigest(), 16) % 100
            if bucket >= pct:
                return False
        return True

    def invalidar_cache(self) -> None:
        self._cache = None


_singleton: FeatureFlagsService | None = None


async def get_feature_flags() -> FeatureFlagsService:
    global _singleton
    if _singleton is None:
        _singleton = FeatureFlagsService()
    return _singleton
