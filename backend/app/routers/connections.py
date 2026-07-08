import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, func, or_, select

from app.models import Connection, Profile, User
from app.routers.deps import DB, CurrentUser, blocked_either_way
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionFriend,
    ConnectionRead,
    ConnectionUpdate,
)

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _pair_clause(user_a: uuid.UUID, user_b: uuid.UUID):
    return or_(
        and_(Connection.requester_id == user_a, Connection.addressee_id == user_b),
        and_(Connection.requester_id == user_b, Connection.addressee_id == user_a),
    )


@router.get("", response_model=list[ConnectionFriend])
async def list_connections(db: DB, user: CurrentUser):
    other_id = func.coalesce(
        func.nullif(Connection.requester_id, user.id),
        func.nullif(Connection.addressee_id, user.id),
    )
    rows = (
        await db.execute(
            select(Connection.id, Profile.user_id, Profile.display_name, Profile.avatar_key)
            .join(Profile, Profile.user_id == other_id)
            .where(
                Connection.status == "accepted",
                or_(Connection.requester_id == user.id, Connection.addressee_id == user.id),
            )
            .order_by(Profile.display_name)
        )
    ).all()
    return [
        ConnectionFriend(id=cid, user_id=uid, display_name=name, avatar_key=avatar)
        for cid, uid, name, avatar in rows
    ]


@router.get("/requests", response_model=list[ConnectionRead])
async def list_requests(db: DB, user: CurrentUser):
    return (
        await db.scalars(
            select(Connection)
            .where(
                Connection.status == "pending",
                or_(Connection.requester_id == user.id, Connection.addressee_id == user.id),
            )
            .order_by(Connection.created_at)
        )
    ).all()


@router.post("", response_model=ConnectionRead, status_code=201)
async def request_connection(payload: ConnectionCreate, db: DB, user: CurrentUser):
    if payload.addressee_id == user.id:
        raise HTTPException(status_code=422, detail="You cannot connect with yourself")
    if await db.get(User, payload.addressee_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if await blocked_either_way(db, user.id, payload.addressee_id):
        raise HTTPException(status_code=403, detail="You cannot connect with this user")
    existing = await db.scalar(
        select(Connection).where(_pair_clause(user.id, payload.addressee_id))
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already connected or pending")

    connection = Connection(requester_id=user.id, addressee_id=payload.addressee_id)
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.patch("/{connection_id}", response_model=ConnectionRead)
async def accept_connection(
    connection_id: uuid.UUID, payload: ConnectionUpdate, db: DB, user: CurrentUser
):
    connection = await db.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if connection.addressee_id != user.id:
        raise HTTPException(status_code=403, detail="Only the addressee may accept")
    if connection.status == "accepted":
        raise HTTPException(status_code=409, detail="Already accepted")

    connection.status = payload.status
    connection.responded_at = func.now()
    await db.commit()
    await db.refresh(connection)
    return connection


@router.delete("/{connection_id}", status_code=204)
async def remove_connection(connection_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    connection = await db.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if user.id not in (connection.requester_id, connection.addressee_id):
        raise HTTPException(status_code=403, detail="Not part of this connection")
    await db.delete(connection)
    await db.commit()
