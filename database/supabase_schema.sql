-- ==============================================
-- SUPABASE CLOUD DATABASE SETUP SCRIPT
-- Vidyalaya AI Startup Edition
-- ==============================================

-- 1. Organizations Table (Each School's Account)
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    camera_index TEXT DEFAULT '0',
    recognition_threshold NUMERIC DEFAULT 1.2,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Default Super Admin Account
INSERT INTO organizations (id, name, email, password) 
VALUES (1, 'Vidyalaya Main', 'admin@vidyalaya.ai', 'admin123') 
ON CONFLICT (id) DO NOTHING;

-- 2. Users Table (Students & Teachers Registered)
CREATE TABLE users (
    id SERIAL PRIMARY KEY, 
    name TEXT NOT NULL,
    role TEXT DEFAULT 'Student',
    class_name TEXT DEFAULT 'N/A',
    parent_phone TEXT DEFAULT 'N/A',
    org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Cameras Table (Multiple Camera Sources Per School)
CREATE TABLE cameras (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    label TEXT DEFAULT 'New Camera',
    is_active INTEGER DEFAULT 0
);

-- 4. Attendance Table (Daily Scans)
CREATE TABLE attendance (
    record_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    time TIME NOT NULL,
    status TEXT DEFAULT 'Present',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Basic Security (Row Level Security logic can be added later)
