"""Credentials API (SPEC §5.4/§6). Responses never contain plaintext secrets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..credentials.service import CredentialService
from ..models.schemas import CredentialCreate, CredentialUpdate
from ..providers import get_llm_provider, get_video_provider

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get("")
async def list_credentials(kind: str | None = None, session: AsyncSession = Depends(get_session)):
    svc = CredentialService(session)
    return [CredentialService.to_api_dict(c) for c in await svc.list(kind)]


@router.post("", status_code=201)
async def create_credential(body: CredentialCreate, session: AsyncSession = Depends(get_session)):
    svc = CredentialService(session)
    c = await svc.create(name=body.name, kind=body.kind, provider=body.provider,
                         api_key=body.api_key, base_url=body.base_url, is_default=body.is_default)
    return CredentialService.to_api_dict(c)


@router.put("/{credential_id}")
async def update_credential(credential_id: str, body: CredentialUpdate,
                            session: AsyncSession = Depends(get_session)):
    svc = CredentialService(session)
    c = await svc.update(credential_id, name=body.name, base_url=body.base_url,
                         api_key=body.api_key, is_default=body.is_default)
    if c is None:
        raise HTTPException(404, "Credential 不存在")
    return CredentialService.to_api_dict(c)


@router.delete("/{credential_id}", status_code=204)
async def delete_credential(credential_id: str, session: AsyncSession = Depends(get_session)):
    if not await CredentialService(session).delete(credential_id):
        raise HTTPException(404, "Credential 不存在")


@router.post("/{credential_id}/test")
async def test_credential(credential_id: str, session: AsyncSession = Depends(get_session)):
    svc = CredentialService(session)
    c = await svc.get(credential_id)
    if c is None:
        raise HTTPException(404, "Credential 不存在")
    try:
        info = await svc.resolve(credential_id, kind=c.kind, provider=c.provider)
        if c.kind == "llm":
            ok, message = await get_llm_provider(c.provider).test_connection(info, base_url=c.base_url)
        else:
            ok, message = await get_video_provider(c.provider).test_connection(info)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # 测试失败不应崩溃
        return {"ok": False, "message": f"测试出错: {e}"}
    return {"ok": ok, "message": message}
