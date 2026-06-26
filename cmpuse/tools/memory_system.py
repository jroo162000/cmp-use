"""
Memory System Tool - Persistent memory and learning for AVA
"""

from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List
from datetime import datetime
import sqlite3
from pathlib import Path

from ..tool_registry import Tool, register
from ..config import Config

# Memory database path
MEMORY_DB = Path.home() / ".cmpuse" / "ava_memory.db"

def init_memory_db():
    """Initialize the memory database"""
    MEMORY_DB.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    
    # Conversations table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_message TEXT,
        ava_response TEXT,
        context TEXT,
        session_id TEXT,
        tools_used TEXT
    )
    ''')
    
    # User preferences table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        preference_key TEXT UNIQUE,
        preference_value TEXT,
        learned_from TEXT,
        confidence REAL DEFAULT 0.5,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # User facts table (things AVA learns about the user)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fact_type TEXT,
        fact_value TEXT,
        context TEXT,
        confidence REAL DEFAULT 0.5,
        learned_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Interaction patterns table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interaction_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_type TEXT,
        pattern_data TEXT,
        frequency INTEGER DEFAULT 1,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "store")
    
    if action == "store":
        return {"preview": "Store conversation in memory", "args": args}
    elif action == "recall":
        query = args.get("query", "")
        return {"preview": f"Search memory for: {query}", "args": args}
    elif action == "learn":
        return {"preview": "Learn user preferences/facts", "args": args}
    elif action == "get_context":
        return {"preview": "Get conversation context", "args": args}
    elif action == "summary":
        return {"preview": "Get memory summary", "args": args}
    else:
        return {"preview": f"Memory operation: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform memory operation", "plan": _plan(args)}
    
    try:
        init_memory_db()
        action = args.get("action", "store")
        
        if action == "store":
            return store_conversation(args)
        elif action == "recall":
            return recall_memory(args)
        elif action == "learn":
            return learn_user_info(args)
        elif action == "get_context":
            return get_conversation_context(args)
        elif action == "summary":
            return get_memory_summary(args)
        else:
            return {"status": "error", "message": f"Unknown memory action: {action}"}
            
    except Exception as e:
        return {"status": "error", "message": f"Memory system error: {str(e)}"}

def store_conversation(args: Dict[str, Any]) -> Dict[str, Any]:
    """Store a conversation in memory"""
    user_message = args.get("user_message", "")
    ava_response = args.get("ava_response", "")
    context = args.get("context", "")
    session_id = args.get("session_id", f"session_{int(time.time())}")
    tools_used = json.dumps(args.get("tools_used", []))
    
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO conversations (user_message, ava_response, context, session_id, tools_used)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_message, ava_response, context, session_id, tools_used))
    
    conversation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "status": "ok",
        "message": "Conversation stored in memory",
        "conversation_id": conversation_id
    }

def recall_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search memory for relevant conversations"""
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    
    # Search in user messages and AVA responses
    cursor.execute('''
    SELECT timestamp, user_message, ava_response, context
    FROM conversations
    WHERE user_message LIKE ? OR ava_response LIKE ? OR context LIKE ?
    ORDER BY timestamp DESC
    LIMIT ?
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
    
    results = cursor.fetchall()
    conn.close()
    
    memories = []
    for row in results:
        memories.append({
            "timestamp": row[0],
            "user_message": row[1],
            "ava_response": row[2],
            "context": row[3]
        })
    
    return {
        "status": "ok",
        "message": f"Found {len(memories)} relevant memories",
        "memories": memories,
        "query": query
    }

def learn_user_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Learn and store user preferences or facts"""
    fact_type = args.get("fact_type", "general")  # name, preference, skill, etc.
    fact_value = args.get("fact_value", "")
    context = args.get("context", "")
    confidence = args.get("confidence", 0.8)
    
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    
    # Check if we already know this fact
    cursor.execute('''
    SELECT id, confidence FROM user_facts 
    WHERE fact_type = ? AND fact_value = ?
    ''', (fact_type, fact_value))
    
    existing = cursor.fetchone()
    
    if existing:
        # Update confidence if we're more sure now
        new_confidence = min(1.0, (existing[1] + confidence) / 2)
        cursor.execute('''
        UPDATE user_facts SET confidence = ?, context = ?, learned_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (new_confidence, context, existing[0]))
        
        message = f"Updated existing fact (confidence: {new_confidence:.2f})"
    else:
        # Store new fact
        cursor.execute('''
        INSERT INTO user_facts (fact_type, fact_value, context, confidence)
        VALUES (?, ?, ?, ?)
        ''', (fact_type, fact_value, context, confidence))
        
        message = f"Learned new fact about user"
    
    conn.commit()
    conn.close()
    
    return {
        "status": "ok",
        "message": message,
        "fact_type": fact_type,
        "fact_value": fact_value,
        "confidence": confidence
    }

def get_conversation_context(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent conversation context"""
    session_id = args.get("session_id")
    limit = args.get("limit", 5)
    
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    
    if session_id:
        cursor.execute('''
        SELECT timestamp, user_message, ava_response
        FROM conversations
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (session_id, limit))
    else:
        cursor.execute('''
        SELECT timestamp, user_message, ava_response
        FROM conversations
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (limit,))
    
    results = cursor.fetchall()
    conn.close()
    
    context = []
    for row in results:
        context.append({
            "timestamp": row[0],
            "user": row[1],
            "ava": row[2]
        })
    
    return {
        "status": "ok",
        "message": f"Retrieved {len(context)} recent conversations",
        "context": list(reversed(context))  # Reverse to chronological order
    }

def get_memory_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get a summary of what AVA knows"""
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    
    # Count conversations
    cursor.execute('SELECT COUNT(*) FROM conversations')
    conv_count = cursor.fetchone()[0]
    
    # Get user facts
    cursor.execute('''
    SELECT fact_type, fact_value, confidence 
    FROM user_facts 
    ORDER BY confidence DESC, learned_at DESC
    LIMIT 20
    ''')
    facts = cursor.fetchall()
    
    # Get recent conversations
    cursor.execute('''
    SELECT timestamp FROM conversations 
    ORDER BY timestamp DESC 
    LIMIT 1
    ''')
    last_conversation = cursor.fetchone()
    
    conn.close()
    
    user_facts = []
    for fact in facts:
        user_facts.append({
            "type": fact[0],
            "value": fact[1],
            "confidence": fact[2]
        })
    
    return {
        "status": "ok",
        "message": "Memory summary retrieved",
        "summary": {
            "total_conversations": conv_count,
            "last_conversation": last_conversation[0] if last_conversation else None,
            "known_facts": user_facts[:10],  # Top 10 facts
            "memory_initialized": True
        }
    }

TOOL = Tool(
    name="memory_system",
    summary="Persistent memory and learning - remember conversations, learn user preferences",
    plan=_plan,
    run=_run,
    permissions={"confirm": False}  # Auto-confirm for memory operations
)

register(TOOL)