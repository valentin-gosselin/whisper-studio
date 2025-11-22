#!/usr/bin/env python3
"""
Update legal texts in database with the latest templates
Run this script to refresh legal texts after template modifications
"""
from database import SessionLocal
from models import LegalText
from rgpd_templates import PRIVACY_POLICY_TEMPLATE, TERMS_TEMPLATE, LEGAL_MENTIONS_TEMPLATE

def update_legal_texts():
    """Update legal texts in database with latest templates"""
    db = SessionLocal()

    try:
        # Update Privacy Policy
        privacy_text = db.query(LegalText).filter_by(key='privacy_policy').first()
        if privacy_text:
            privacy_text.content = PRIVACY_POLICY_TEMPLATE
            print("✓ Updated Privacy Policy")
        else:
            print("✗ Privacy Policy not found in database")

        # Update Terms
        terms_text = db.query(LegalText).filter_by(key='terms').first()
        if terms_text:
            terms_text.content = TERMS_TEMPLATE
            print("✓ Updated Terms of Service")
        else:
            print("✗ Terms not found in database")

        # Update Legal Mentions
        legal_text = db.query(LegalText).filter_by(key='legal_mentions').first()
        if legal_text:
            legal_text.content = LEGAL_MENTIONS_TEMPLATE
            print("✓ Updated Legal Mentions")
        else:
            print("✗ Legal Mentions not found in database")

        db.commit()
        print("\n✓ All legal texts updated successfully!")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error updating legal texts: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    print("Updating legal texts from templates...")
    update_legal_texts()
