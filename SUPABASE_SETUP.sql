-- ============================================================================
-- Supabase Database Schema for RBC Metabolic Model
-- Complete Setup - Run this SQL in your Supabase SQL Editor
-- ============================================================================

-- ============================================================================
-- 1. CREATE TABLES
-- ============================================================================

-- Extended user information (complements Supabase Auth users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID REFERENCES auth.users(id) PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    organization TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    simulation_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role);
CREATE INDEX IF NOT EXISTS idx_user_profiles_created_at ON user_profiles(created_at);

-- Log all simulations for analytics and audit
CREATE TABLE IF NOT EXISTS simulation_history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    simulation_type TEXT NOT NULL CHECK (simulation_type IN ('basic', 'flux', 'sensitivity', 'bohr')),
    parameters JSONB,
    duration_seconds FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_simulation_history_user ON simulation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_simulation_history_date ON simulation_history(created_at);
CREATE INDEX IF NOT EXISTS idx_simulation_history_type ON simulation_history(simulation_type);

-- ============================================================================
-- 2. ENABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE simulation_history ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 3. SIGNUP FUNCTION (bypasses RLS with SECURITY DEFINER)
-- ============================================================================

CREATE OR REPLACE FUNCTION create_user_profile(
    user_id UUID,
    user_email TEXT,
    user_full_name TEXT DEFAULT '',
    user_organization TEXT DEFAULT ''
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result JSON;
BEGIN
    -- Verify caller is creating their own profile
    IF auth.uid() != user_id THEN
        RAISE EXCEPTION 'Unauthorized: Cannot create profile for another user';
    END IF;
    
    -- Insert profile (bypass RLS with SECURITY DEFINER)
    INSERT INTO user_profiles (
        id, email, full_name, organization, role, is_active, simulation_count, created_at
    )
    VALUES (
        user_id, user_email, user_full_name, user_organization, 'user', TRUE, 0, NOW()
    )
    RETURNING json_build_object(
        'id', id, 'email', email, 'full_name', full_name, 'organization', organization,
        'role', role, 'is_active', is_active, 'created_at', created_at
    ) INTO result;
    
    RETURN result;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'Profile already exists for this user';
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to create user profile: %', SQLERRM;
END;
$$;

GRANT EXECUTE ON FUNCTION create_user_profile TO authenticated;
GRANT EXECUTE ON FUNCTION create_user_profile TO anon;

-- ============================================================================
-- 4. RLS POLICIES - user_profiles
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;

CREATE POLICY "Users can view own profile"
ON user_profiles FOR SELECT
USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
ON user_profiles FOR UPDATE
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- ============================================================================
-- 5. RLS POLICIES - simulation_history
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own simulations" ON simulation_history;
DROP POLICY IF EXISTS "Users can insert own simulations" ON simulation_history;

CREATE POLICY "Users can insert own simulations"
ON simulation_history FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own simulations"
ON simulation_history FOR SELECT
USING (auth.uid() = user_id);

-- ============================================================================
-- 6. ADMIN FUNCTIONS (with SECURITY DEFINER to bypass RLS)
-- ============================================================================

-- Check if user is admin
CREATE OR REPLACE FUNCTION is_admin(check_user_id UUID DEFAULT NULL)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
    user_role TEXT;
    target_id UUID;
BEGIN
    target_id := COALESCE(check_user_id, auth.uid());
    SELECT role INTO user_role FROM user_profiles WHERE id = target_id;
    RETURN (user_role = 'admin');
END;
$$;

-- Get all users (admin only)
CREATE OR REPLACE FUNCTION get_all_users_admin()
RETURNS TABLE (
    id UUID, email TEXT, full_name TEXT, organization TEXT, role TEXT,
    is_active BOOLEAN, simulation_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE, last_login TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    IF NOT is_admin(auth.uid()) THEN
        RAISE EXCEPTION 'Access denied: Admin privileges required';
    END IF;
    RETURN QUERY
    SELECT up.id, up.email, up.full_name, up.organization, up.role,
           up.is_active, up.simulation_count, up.created_at, up.last_login
    FROM user_profiles up ORDER BY up.created_at DESC;
END;
$$;

-- Update user role (admin only)
CREATE OR REPLACE FUNCTION update_user_role_admin(target_user_id UUID, new_role TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    IF NOT is_admin(auth.uid()) THEN
        RAISE EXCEPTION 'Access denied: Admin privileges required';
    END IF;
    IF new_role NOT IN ('user', 'admin') THEN
        RAISE EXCEPTION 'Invalid role: must be user or admin';
    END IF;
    UPDATE user_profiles SET role = new_role WHERE id = target_user_id;
    RETURN TRUE;
END;
$$;

-- Deactivate user (admin only)
CREATE OR REPLACE FUNCTION deactivate_user_admin(target_user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    IF NOT is_admin(auth.uid()) THEN
        RAISE EXCEPTION 'Access denied: Admin privileges required';
    END IF;
    UPDATE user_profiles SET is_active = FALSE WHERE id = target_user_id;
    RETURN TRUE;
END;
$$;

-- Get all simulations (admin only)
CREATE OR REPLACE FUNCTION get_all_simulations_admin()
RETURNS TABLE (
    id INTEGER, user_id UUID, user_email TEXT, simulation_type TEXT,
    parameters JSONB, duration_seconds FLOAT,
    created_at TIMESTAMP WITH TIME ZONE, success BOOLEAN
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    IF NOT is_admin(auth.uid()) THEN
        RAISE EXCEPTION 'Access denied: Admin privileges required';
    END IF;
    RETURN QUERY
    SELECT sh.id, sh.user_id, up.email, sh.simulation_type,
           sh.parameters, sh.duration_seconds, sh.created_at, sh.success
    FROM simulation_history sh
    JOIN user_profiles up ON sh.user_id = up.id
    ORDER BY sh.created_at DESC;
END;
$$;

-- ============================================================================
-- 7. UTILITY FUNCTIONS
-- ============================================================================

-- Increment simulation count
CREATE OR REPLACE FUNCTION increment_simulation_count(user_id_param UUID)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
    UPDATE user_profiles SET simulation_count = simulation_count + 1
    WHERE id = user_id_param;
END;
$$;

-- Get user statistics
CREATE OR REPLACE FUNCTION get_user_stats(user_id_param UUID)
RETURNS TABLE (
    total_simulations INTEGER, simulations_by_type JSONB,
    avg_duration FLOAT, last_simulation TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER AS total_simulations,
        jsonb_object_agg(simulation_type, count) AS simulations_by_type,
        AVG(duration_seconds)::FLOAT AS avg_duration,
        MAX(created_at) AS last_simulation
    FROM (
        SELECT simulation_type, COUNT(*)::INTEGER AS count,
               duration_seconds, created_at
        FROM simulation_history
        WHERE user_id = user_id_param
        GROUP BY simulation_type, duration_seconds, created_at
    ) subquery
    GROUP BY ();
END;
$$;

-- ============================================================================
-- 8. MONITORING ALERT WORKFLOW PERSISTENCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS monitoring_alert_workflow_states (
    alert_id TEXT PRIMARY KEY,
    bag_id TEXT NOT NULL UNIQUE,
    workflow_status TEXT NOT NULL CHECK (workflow_status IN ('New', 'Acknowledged', 'In review', 'Escalated', 'Resolved')),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_states_bag_id
ON monitoring_alert_workflow_states(bag_id);

CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_states_updated_at
ON monitoring_alert_workflow_states(updated_at DESC);

CREATE TABLE IF NOT EXISTS monitoring_alert_workflow_history (
    transition_id BIGSERIAL PRIMARY KEY,
    alert_id TEXT NOT NULL,
    bag_id TEXT NOT NULL,
    previous_status TEXT NOT NULL CHECK (previous_status IN ('New', 'Acknowledged', 'In review', 'Escalated', 'Resolved')),
    next_status TEXT NOT NULL CHECK (next_status IN ('New', 'Acknowledged', 'In review', 'Escalated', 'Resolved')),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    note TEXT,
    updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_history_bag_id
ON monitoring_alert_workflow_history(bag_id);

CREATE INDEX IF NOT EXISTS idx_monitoring_alert_workflow_history_changed_at
ON monitoring_alert_workflow_history(changed_at DESC);

CREATE OR REPLACE FUNCTION upsert_monitoring_alert_workflow_state(
    p_bag_id TEXT,
    p_workflow_status TEXT,
    p_note TEXT DEFAULT NULL,
    p_updated_by TEXT DEFAULT NULL
)
RETURNS TABLE (
    alert_id TEXT,
    bag_id TEXT,
    workflow_status TEXT,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    updated_by TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_bag_id TEXT := UPPER(BTRIM(COALESCE(p_bag_id, '')));
    v_alert_id TEXT := 'ALERT-' || UPPER(BTRIM(COALESCE(p_bag_id, '')));
    v_now TIMESTAMP WITH TIME ZONE := NOW();
    v_existing monitoring_alert_workflow_states%ROWTYPE;
BEGIN
    IF v_bag_id = '' THEN
        RAISE EXCEPTION 'bag_id is required';
    END IF;

    IF p_workflow_status NOT IN ('New', 'Acknowledged', 'In review', 'Escalated', 'Resolved') THEN
        RAISE EXCEPTION 'workflow_status must be one of: New, Acknowledged, In review, Escalated, Resolved';
    END IF;

    SELECT *
    INTO v_existing
    FROM monitoring_alert_workflow_states
    WHERE monitoring_alert_workflow_states.alert_id = v_alert_id
       OR monitoring_alert_workflow_states.bag_id = v_bag_id
    LIMIT 1;

    IF FOUND THEN
        IF v_existing.workflow_status <> p_workflow_status THEN
            INSERT INTO monitoring_alert_workflow_history (
                alert_id, bag_id, previous_status, next_status, changed_at, note, updated_by
            )
            VALUES (
                v_existing.alert_id,
                v_existing.bag_id,
                v_existing.workflow_status,
                p_workflow_status,
                v_now,
                COALESCE(p_note, v_existing.note),
                COALESCE(p_updated_by, v_existing.updated_by)
            );
        END IF;

        RETURN QUERY
        UPDATE monitoring_alert_workflow_states
        SET
            bag_id = v_bag_id,
            workflow_status = p_workflow_status,
            note = COALESCE(p_note, monitoring_alert_workflow_states.note),
            updated_at = v_now,
            updated_by = COALESCE(p_updated_by, monitoring_alert_workflow_states.updated_by)
        WHERE monitoring_alert_workflow_states.alert_id = v_existing.alert_id
        RETURNING
            monitoring_alert_workflow_states.alert_id,
            monitoring_alert_workflow_states.bag_id,
            monitoring_alert_workflow_states.workflow_status,
            monitoring_alert_workflow_states.note,
            monitoring_alert_workflow_states.created_at,
            monitoring_alert_workflow_states.updated_at,
            monitoring_alert_workflow_states.updated_by;
        RETURN;
    END IF;

    IF p_workflow_status <> 'New' THEN
        INSERT INTO monitoring_alert_workflow_history (
            alert_id, bag_id, previous_status, next_status, changed_at, note, updated_by
        )
        VALUES (
            v_alert_id,
            v_bag_id,
            'New',
            p_workflow_status,
            v_now,
            p_note,
            p_updated_by
        );
    END IF;

    RETURN QUERY
    INSERT INTO monitoring_alert_workflow_states (
        alert_id, bag_id, workflow_status, note, created_at, updated_at, updated_by
    )
    VALUES (
        v_alert_id,
        v_bag_id,
        p_workflow_status,
        p_note,
        v_now,
        v_now,
        p_updated_by
    )
    RETURNING
        monitoring_alert_workflow_states.alert_id,
        monitoring_alert_workflow_states.bag_id,
        monitoring_alert_workflow_states.workflow_status,
        monitoring_alert_workflow_states.note,
        monitoring_alert_workflow_states.created_at,
        monitoring_alert_workflow_states.updated_at,
        monitoring_alert_workflow_states.updated_by;
END;
$$;

-- ============================================================================
-- 9. VIEWS (for analytics)
-- ============================================================================

CREATE OR REPLACE VIEW user_activity_summary AS
SELECT
    up.id, up.email, up.full_name, up.organization, up.role,
    up.simulation_count, up.created_at, up.last_login,
    COUNT(sh.id) AS total_simulations_logged,
    MAX(sh.created_at) AS last_simulation_date,
    AVG(sh.duration_seconds) AS avg_simulation_duration
FROM user_profiles up
LEFT JOIN simulation_history sh ON up.id = sh.user_id
GROUP BY up.id, up.email, up.full_name, up.organization, up.role,
         up.simulation_count, up.created_at, up.last_login;

-- ============================================================================
-- 10. VERIFICATION
-- ============================================================================

-- Verify tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('user_profiles', 'simulation_history');

-- Verify RLS enabled
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('user_profiles', 'simulation_history');

-- Verify policies
SELECT schemaname, tablename, policyname, cmd
FROM pg_policies 
WHERE tablename IN ('user_profiles', 'simulation_history')
ORDER BY tablename, policyname;

-- Verify functions
SELECT proname, prosecdef 
FROM pg_proc 
WHERE proname IN ('create_user_profile', 'is_admin', 'get_all_users_admin', 
                   'update_user_role_admin', 'deactivate_user_admin', 'get_all_simulations_admin');

-- ============================================================================
-- SETUP COMPLETE!
-- ============================================================================
-- Next steps:
-- 1. Configure .streamlit/secrets.toml with Supabase URL and anon_key
-- 2. Run the app and create your account via signup page
-- 3. Promote to admin: UPDATE user_profiles SET role = 'admin' WHERE email = 'your@email.com';
-- ============================================================================
