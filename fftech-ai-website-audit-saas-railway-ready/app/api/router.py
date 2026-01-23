@router.post('/open-audit')
async def open_audit(body: OpenAuditRequest, request: Request):
    settings = get_settings()
    ip = (request.client.host if request and request.client else 'anon')

    import time
    now = int(time.time())
    window = now // 3600
    key = f"{ip}:{window}"

    if not hasattr(open_audit, 'RATE_TRACK'):
        open_audit.RATE_TRACK = {}

    count = open_audit.RATE_TRACK.get(key, 0)
    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, 'Rate limit exceeded for open audits. Please try later or sign in.')

    open_audit.RATE_TRACK[key] = count + 1

    # Convert HttpUrl to str before running audit
    url_str = str(body.url)
    result = await run_audit(url_str) if hasattr(run_audit, '__await__') else run_audit(url_str)
    return result


@router.post('/audit', response_model=AuditOut)
async def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')

    settings = get_settings()
    if user.plan == 'free' and user.audit_count >= settings.FREE_AUDIT_LIMIT:
        raise HTTPException(403, f'Free plan limit reached ({settings.FREE_AUDIT_LIMIT} audits)')

    url_str = str(body.url)
    result = await run_audit(url_str) if hasattr(run_audit, '__await__') else run_audit(url_str)

    audit = Audit(user_id=user.id, url=url_str, result_json=result)
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit
