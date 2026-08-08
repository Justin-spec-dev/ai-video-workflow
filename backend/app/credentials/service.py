"""CredentialService: Fernet-encrypted secrets, masked API responses (SPEC §5.4)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decrypt_secret, encrypt_secret, mask_secret
from ..models.orm import Credential
from ..providers.video.base import CredentialInfo


class CredentialService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def to_api_dict(c: Credential, *, reveal_mask: str | None = None) -> dict:
        if reveal_mask is None:
            try:
                reveal_mask = mask_secret(decrypt_secret(c.secret_encrypted))
            except ValueError:
                reveal_mask = "****"
        return {
            "id": c.id,
            "name": c.name,
            "kind": c.kind,
            "provider": c.provider,
            "base_url": c.base_url,
            "is_default": c.is_default,
            "masked_secret": reveal_mask,
            "created_at": c.created_at,
        }

    async def list(self, kind: str | None = None) -> list[Credential]:
        q = select(Credential).order_by(Credential.created_at)
        if kind:
            q = q.where(Credential.kind == kind)
        return list((await self.session.execute(q)).scalars())

    async def get(self, credential_id: str) -> Credential | None:
        return await self.session.get(Credential, credential_id)

    async def create(self, *, name: str, kind: str, provider: str, api_key: str,
                     base_url: str | None = None, is_default: bool = False) -> Credential:
        if is_default:
            await self._clear_default(kind, provider)
        c = Credential(
            name=name, kind=kind, provider=provider, base_url=base_url,
            secret_encrypted=encrypt_secret(api_key), is_default=is_default,
        )
        self.session.add(c)
        await self.session.commit()
        return c

    async def update(self, credential_id: str, *, name=None, base_url=None,
                     api_key=None, is_default=None) -> Credential | None:
        c = await self.get(credential_id)
        if c is None:
            return None
        if name is not None:
            c.name = name
        if base_url is not None:
            c.base_url = base_url
        if api_key:  # 空白 = 不变
            c.secret_encrypted = encrypt_secret(api_key)
        if is_default is not None:
            if is_default:
                await self._clear_default(c.kind, c.provider)
            c.is_default = is_default
        await self.session.commit()
        return c

    async def delete(self, credential_id: str) -> bool:
        c = await self.get(credential_id)
        if c is None:
            return False
        await self.session.delete(c)
        await self.session.commit()
        return True

    async def _clear_default(self, kind: str, provider: str) -> None:
        q = select(Credential).where(Credential.kind == kind, Credential.provider == provider,
                                     Credential.is_default.is_(True))
        for other in (await self.session.execute(q)).scalars():
            other.is_default = False

    async def resolve(self, credential_id: str | None, *, kind: str,
                      provider: str | None = None) -> CredentialInfo:
        """Resolve a credential_id (or the default for kind+provider) to decrypted CredentialInfo."""
        c: Credential | None = None
        if credential_id:
            c = await self.get(credential_id)
            if c is None:
                raise ValueError(f"Credential 不存在: {credential_id}")
        else:
            q = select(Credential).where(Credential.kind == kind, Credential.is_default.is_(True))
            if provider:
                q = q.where(Credential.provider == provider)
            c = (await self.session.execute(q)).scalars().first()
            if c is None:
                raise ValueError(f"未配置 credential_id，且没有 {kind}/{provider or '*'} 的默认 Credential")
        return CredentialInfo(
            id=c.id, name=c.name, kind=c.kind, provider=c.provider,
            base_url=c.base_url, api_key=decrypt_secret(c.secret_encrypted),
        )
