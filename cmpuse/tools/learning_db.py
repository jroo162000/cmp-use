"""
Learning Database Tool - Persistent learning from user interactions and corrections
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Any, Dict

from ..tool_registry import Tool, register

# Database location
DB_PATH = os.path.expanduser("~/.cmpuse/learning.db")

def _init_db():
    """Initialize the learning database"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # User preferences table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(category, key)
        )
    ''')

    # Corrections table (learn from mistakes)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_input TEXT NOT NULL,
            wrong_interpretation TEXT,
            correct_interpretation TEXT,
            context TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # Patterns table (recurring user requests)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_used TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # User facts table (things learned about the user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_type TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            source TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(fact_type, fact_value)
        )
    ''')

    conn.commit()
    conn.close()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "get_preference")

    if action == "set_preference":
        return {"preview": f"Store user preference", "args": args}
    elif action == "get_preference":
        return {"preview": f"Retrieve user preference", "args": args}
    elif action == "learn_correction":
        return {"preview": "Learn from user correction", "args": args}
    elif action == "learn_fact":
        return {"preview": "Learn fact about user", "args": args}
    elif action == "get_patterns":
        return {"preview": "Get learned patterns", "args": args}
    elif action == "record_pattern":
        return {"preview": "Record usage pattern", "args": args}
    else:
        return {"preview": f"Learning action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    def _strip_highlight_markup(value):
        if isinstance(value, str):
            return value.replace("⟦HL⟧", "").replace("⟦/HL⟧", "")
        if isinstance(value, dict):
            return {k: _strip_highlight_markup(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_strip_highlight_markup(v) for v in value]
        return value

    args = _strip_highlight_markup(args)

    if dry_run:
        return {"status": "dry-run", "message": "Would perform learning operation", "plan": _plan(args)}

    _init_db()
    action = args.get("action", "get_preference")

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = lambda b: _strip_highlight_markup(b.decode())
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        if action == "set_preference":
            category = args.get("category", "general")
            key = args.get("key")
            value = args.get("value")
            confidence = args.get("confidence", 1.0)

            if not key or not value:
                return {"status": "error", "message": "key and value required"}

            cursor.execute('''
                INSERT OR REPLACE INTO preferences (category, key, value, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (category, key, value, confidence, now, now))

            conn.commit()
            return {"status": "ok", "message": f"Preference stored: {category}.{key} = {value}"}

        elif action == "get_preference":
            category = args.get("category", "general")
            key = args.get("key")

            if key:
                cursor.execute('SELECT value, confidence FROM preferences WHERE category = ? AND key = ?', (category, key))
                result = cursor.fetchone()
                if result:
                    return {"status": "ok", "value": result[0], "confidence": result[1]}
                else:
                    return {"status": "ok", "value": None, "message": "Preference not found"}
            else:
                # Get all preferences in category
                cursor.execute('SELECT key, value, confidence FROM preferences WHERE category = ?', (category,))
                results = cursor.fetchall()
                prefs = {row[0]: {"value": row[1], "confidence": row[2]} for row in results}
                return {"status": "ok", "preferences": prefs, "count": len(prefs)}

        elif action == "learn_correction":
            user_input = args.get("user_input")
            wrong = args.get("wrong_interpretation")
            correct = args.get("correct_interpretation")
            context = args.get("context", "")

            cursor.execute('''
                INSERT INTO corrections (user_input, wrong_interpretation, correct_interpretation, context, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_input, wrong, correct, context, now))

            conn.commit()
            return {"status": "ok", "message": "Correction learned"}

        elif action == "learn_fact":
            fact_type = args.get("fact_type")
            fact_value = args.get("fact_value")
            confidence = args.get("confidence", 1.0)
            source = args.get("source", "conversation")

            cursor.execute('''
                INSERT OR REPLACE INTO user_facts (fact_type, fact_value, confidence, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (fact_type, fact_value, confidence, source, now, now))

            conn.commit()
            return {"status": "ok", "message": f"Learned: {fact_type} = {fact_value}"}

        elif action == "get_facts":
            fact_type = args.get("fact_type")

            if fact_type:
                cursor.execute('SELECT fact_value, confidence, source FROM user_facts WHERE fact_type = ?', (fact_type,))
                results = cursor.fetchall()
                facts = [{"value": r[0], "confidence": r[1], "source": r[2]} for r in results]
            else:
                cursor.execute('SELECT fact_type, fact_value, confidence FROM user_facts ORDER BY confidence DESC')
                results = cursor.fetchall()
                facts = [{"type": r[0], "value": r[1], "confidence": r[2]} for r in results]

            return {"status": "ok", "facts": facts, "count": len(facts)}

        elif action == "record_pattern":
            pattern_type = args.get("pattern_type")
            pattern_data = args.get("pattern_data")

            # Check if pattern exists
            cursor.execute('SELECT id, frequency FROM patterns WHERE pattern_type = ? AND pattern_data = ?',
                         (pattern_type, json.dumps(pattern_data)))
            existing = cursor.fetchone()

            if existing:
                # Increment frequency
                cursor.execute('UPDATE patterns SET frequency = ?, last_used = ? WHERE id = ?',
                             (existing[1] + 1, now, existing[0]))
            else:
                # New pattern
                cursor.execute('''
                    INSERT INTO patterns (pattern_type, pattern_data, frequency, last_used, created_at)
                    VALUES (?, ?, 1, ?, ?)
                ''', (pattern_type, json.dumps(pattern_data), now, now))

            conn.commit()
            return {"status": "ok", "message": "Pattern recorded"}

        elif action == "get_patterns":
            pattern_type = args.get("pattern_type")
            limit = args.get("limit", 10)

            if pattern_type:
                cursor.execute('''
                    SELECT pattern_data, frequency, last_used
                    FROM patterns
                    WHERE pattern_type = ?
                    ORDER BY frequency DESC, last_used DESC
                    LIMIT ?
                ''', (pattern_type, limit))
            else:
                cursor.execute('''
                    SELECT pattern_type, pattern_data, frequency
                    FROM patterns
                    ORDER BY frequency DESC
                    LIMIT ?
                ''', (limit,))

            results = cursor.fetchall()
            patterns = [{"data": json.loads(r[0]) if pattern_type else r[1], "frequency": r[1] if pattern_type else r[2]} for r in results]
            return {"status": "ok", "patterns": patterns, "count": len(patterns)}

        elif action == "stats":
            # Get database statistics
            cursor.execute('SELECT COUNT(*) FROM preferences')
            prefs_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM corrections')
            corrections_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM patterns')
            patterns_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM user_facts')
            facts_count = cursor.fetchone()[0]

            return {
                "status": "ok",
                "message": "Learning database statistics",
                "stats": {
                    "preferences": prefs_count,
                    "corrections": corrections_count,
                    "patterns": patterns_count,
                    "user_facts": facts_count,
                    "db_path": DB_PATH
                }
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Learning database error: {str(e)}"}
    finally:
        conn.close()

TOOL = Tool(
    name="learning_db",
    summary="Persistent learning - store preferences, learn from corrections, track patterns, remember user facts",
    plan=_plan,
    run=_run,
    permissions={"confirm": False}  # Learning is non-destructive
)

register(TOOL)
