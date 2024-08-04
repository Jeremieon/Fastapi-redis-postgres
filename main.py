from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas, auth, utils, database
from database import engine, SessionLocal, get_db
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from redis_config import lifespan
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from sqlalchemy.future import select

load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(lifespan=lifespan)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(lambda: app.state.redis),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = auth.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    # Check Redis cache
    token_key = f"user:{email}:token"
    cached_token = await redis_client.get(token_key)
    if cached_token and cached_token == token:
        query = await db.execute(select(models.User).filter(models.User.email == email))
        user = query.scalars().first()
        if user is None:
            raise credentials_exception
        return user
    else:
        raise credentials_exception


@app.post("/register", response_model=schemas.UserOut)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.User).filter(models.User.email == user.email)
    )
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = utils.hash_password(user.password)
    db_user = models.User(
        email=user.email, username=user.username, hashed_password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@app.post("/login")
async def login(
    request: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(database.get_db),
    redis_client: redis.Redis = Depends(lambda: app.state.redis),
):
    result = await db.execute(
        select(models.User).filter(models.User.email == request.username)
    )
    db_user = result.scalars().first()
    if not db_user or not utils.verify_password(
        request.password, db_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    access_token = auth.create_access_token(data={"sub": db_user.email})
    token_key = f"user:{db_user.email}:token"

    await redis_client.setex(
        token_key, auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60, access_token
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/users", response_model=schemas.UserList)
async def get_all_users(db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(models.User))
        users = result.scalars().all()
        users_list = [schemas.UserOut.from_orm(user) for user in users]
    return {"users": users_list}
