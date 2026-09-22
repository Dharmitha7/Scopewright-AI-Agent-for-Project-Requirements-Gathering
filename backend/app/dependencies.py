"""Shared FastAPI dependencies.

https://fastapi.tiangolo.com/tutorial/bigger-applications/#dependencies
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import read_session_account_id

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentAccountId = Annotated[UUID, Depends(read_session_account_id)]
