import pytest

from app.create_librarian import create_account


@pytest.mark.asyncio
async def test_create_librarian_password_and_identity_validation():
    with pytest.raises(SystemExit, match="at least 10"):
        await create_account(
            "librarian@life.edu.ph", "Head Librarian", "librarian", "123456789"
        )
    with pytest.raises(SystemExit, match="valid name and email"):
        await create_account("invalid", "Head Librarian", "librarian", "1234567890")
