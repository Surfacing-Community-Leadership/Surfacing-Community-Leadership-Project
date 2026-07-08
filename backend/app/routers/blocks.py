import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, or_, and_, select

from app.models import Block, Connection, Profile, User
from app.routers.deps import DB, CurrentUser
from app.schemas.block import BlockCreate, BlockRead, BlockedUser

router = APIRouter(prefix="/api/blocks", tags=["blocks"])


@router.get("", response_model=list[BlockedUser])
async def list_blocks(db: DB, user: CurrentUser):
    rows = (
        await db.execute(
            select(Block.blocked_id, Profile.display_name)
            .join(Profile, Profile.user_id == Block.blocked_id)
            .where(Block.blocker_id == user.id)
            .order_by(Block.created_at)
        )
    ).all()
    return [BlockedUser(blocked_id=bid, display_name=name) for bid, name in rows]


@router.post("", response_model=BlockRead, status_code=201)
async def block_user(payload: BlockCreate, db: DB, user: CurrentUser):
    if payload.blocked_id == user.id:
        raise HTTPException(status_code=422, detail="You cannot block yourself")
    if await db.get(User, payload.blocked_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await db.scalar(
        select(Block).where(
            Block.blocker_id == user.id, Block.blocked_id == payload.blocked_id
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already blocked")

    db.add(Block(blocker_id=user.id, blocked_id=payload.blocked_id))
    # Blocking severs any connection or pending request between the two.
    await db.execute(
        delete(Connection).where(
            or_(
                and_(
                    Connection.requester_id == user.id,
                    Connection.addressee_id == payload.blocked_id,
                ),
                and_(
                    Connection.requester_id == payload.blocked_id,
                    Connection.addressee_id == user.id,
                ),
            )
        )
    )
    await db.commit()
    return BlockRead(blocker_id=user.id, blocked_id=payload.blocked_id)


@router.delete("/{blocked_id}", status_code=204)
async def unblock_user(blocked_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    block = await db.scalar(
        select(Block).where(Block.blocker_id == user.id, Block.blocked_id == blocked_id)
    )
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    await db.delete(block)
    await db.commit()
