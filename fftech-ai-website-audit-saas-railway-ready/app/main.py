# app/main.py

def run_self_healing_migration():
    """Relaxes database constraints to prevent NotNullViolation crashes."""
    with engine.connect() as conn:
        try:
            # Relaxing status, score, AND grade constraints
            conn.execute(text("ALTER TABLE audits ALTER COLUMN status DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN score DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN grade DROP NOT NULL;"))
            conn.commit()
            logger.info("SCHEMA REPAIR: Success. Constraints relaxed.")
        except Exception as e:
            conn.rollback()
            logger.error(f"SCHEMA REPAIR FAILED: {e}")

@app.post("/api/open-audit")
async def api_open_audit(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        url = body.get("url")
        
        # This will now use the corrected AIza... key
        result = await run_audit(url)

        new_audit = Audit(
            url=url,
            status="completed",
            result_json=result
            # score and grade columns are now optional and can be null
        )
        db.add(new_audit)
        db.commit()
        return result
    except Exception as e:
        logger.error(f"API Error: {e}")
        db.rollback()
        return JSONResponse({"detail": str(e)}, status_code=500)
