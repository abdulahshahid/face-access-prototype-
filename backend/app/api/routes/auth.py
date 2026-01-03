@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Exchanges admin username/password for a JWT token.
    """

    if (
        form_data.username != settings.ADMIN_USER
        or form_data.password != settings.ADMIN_PASSWORD
    ):
        logger.warning("Failed admin login attempt")
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    access_token = create_access_token(
        data={
            "sub": form_data.username,
            "role": "admin"
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
