# api/validators.py
import re

from django.core.exceptions import ValidationError

# Patterns that are unlikely to appear in normal prose but typical in SQL injection
DANGEROUS_PATTERNS = [
    r";\s*--",  # stacked statement + inline comment
    r"--\s*$",  # trailing comment
    r"/\*.*?\*/",  # /* ... */
    r"\bUNION\b\s+\bSELECT\b",  # UNION SELECT
    r"\bSELECT\b\s+.+\s+\bFROM\b",  # SELECT ... FROM ...
    r"\bDROP\b\s+\bTABLE\b",  # DROP TABLE
    r"\bDELETE\b\s+\bFROM\b",  # DELETE FROM
    r"\bINSERT\b\s+\bINTO\b",  # INSERT INTO
    r"\bUPDATE\b\s+.+\s+\bSET\b",  # UPDATE ... SET ...
    r"\bEXEC(?:UTE)?\b",  # EXEC / EXECUTE
    r"\bxp_\w+\b",  # xp_*
    r"\bsp_\w+\b",  # sp_*
]

# IGNORECASE applies to all, DOTALL lets /* ... */ span lines
dangerous_re = re.compile("|".join(DANGEROUS_PATTERNS), re.IGNORECASE | re.DOTALL)


def validate_no_sql_injection(value: str):
    """Block only clearly dangerous SQL-shaped inputs; allow normal prose."""
    if not value:
        return value
    if dangerous_re.search(value):
        raise ValidationError("Invalid input detected")
    return value


def sanitize_input(value):
    """Sanitize user input to prevent XSS and injection attacks"""
    if not value:
        return value

    # Remove any HTML tags
    import re

    value = re.sub("<.*?>", "", value)

    # Escape special characters
    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    value = value.replace('"', "&quot;")
    value = value.replace("'", "&#x27;")

    return value
