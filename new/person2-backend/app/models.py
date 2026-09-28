from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Infrastructure-only base. New domain models must follow the new contracts."""
