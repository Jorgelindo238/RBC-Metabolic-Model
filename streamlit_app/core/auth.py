"""
Authentication module using Supabase
Handles user authentication, authorization, and session management.

Author: RBC Metabolic Model Team
Date: 2025-11-22
"""
import streamlit as st
from typing import Optional, Dict, Callable
import time
from datetime import datetime

# Conditional import of supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None


class AuthManager:
    """Manage authentication with Supabase"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase: Optional[Client] = None
        
        if not SUPABASE_AVAILABLE:
            st.warning("⚠️ Supabase not installed. Install with: `pip install supabase`")
            return
        
        try:
            # Check if secrets are configured
            if "supabase" not in st.secrets:
                st.warning("⚠️ Supabase credentials not configured in secrets")
                return
            
            self.supabase = create_client(
                st.secrets["supabase"]["url"],
                st.secrets["supabase"]["anon_key"]
            )
        except Exception as e:
            st.error(f"❌ Failed to connect to authentication service: {e}")
            self.supabase = None
    
    def is_configured(self) -> bool:
        """Check if authentication is properly configured"""
        return self.supabase is not None
    
    def sign_up(self, email: str, password: str, full_name: str = "", 
                organization: str = "") -> Dict:
        """
        Register new user
        
        Args:
            email: User email address
            password: User password (min 8 characters)
            full_name: User's full name
            organization: User's organization
            
        Returns:
            Dict with success status and user data or error message
        """
        if not self.is_configured():
            return {"success": False, "error": "Authentication not configured"}
        
        try:
            # Create auth user
            auth_response = self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                # Create user profile using RPC function (bypasses RLS)
                try:
                    self.supabase.rpc("create_user_profile", {
                        "user_id": auth_response.user.id,
                        "user_email": email,
                        "user_full_name": full_name,
                        "user_organization": organization
                    }).execute()
                except Exception as profile_error:
                    # If profile creation fails, try to clean up auth user
                    try:
                        # Note: Supabase doesn't allow deleting auth users via client
                        # Admin will need to manually clean up if needed
                        pass
                    except Exception:
                        pass
                    raise Exception(f"Profile creation failed: {str(profile_error)}")
                
                return {
                    "success": True, 
                    "user": auth_response.user,
                    "message": "Account created! Please check your email to verify."
                }
            
            return {"success": False, "error": "Sign up failed"}
        
        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower():
                return {"success": False, "error": "This email is already registered"}
            return {"success": False, "error": f"Registration failed: {error_msg}"}
    
    def sign_in(self, email: str, password: str) -> Dict:
        """
        Sign in user
        
        Args:
            email: User email address
            password: User password
            
        Returns:
            Dict with success status, user data, and session
        """
        if not self.is_configured():
            return {"success": False, "error": "Authentication not configured"}
        
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Update last login timestamp
                try:
                    self.supabase.table("user_profiles")\
                        .update({"last_login": datetime.utcnow().isoformat()})\
                        .eq("id", response.user.id)\
                        .execute()
                except Exception:
                    pass  # Non-critical if update fails
                
                return {
                    "success": True,
                    "user": response.user,
                    "session": response.session
                }
            
            return {"success": False, "error": "Invalid credentials"}
        
        except Exception as e:
            error_msg = str(e)
            if "invalid login credentials" in error_msg.lower():
                return {"success": False, "error": "Invalid email or password"}
            return {"success": False, "error": f"Login failed: {error_msg}"}
    
    def sign_out(self) -> bool:
        """
        Sign out current user
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured():
            return False
        
        try:
            self.supabase.auth.sign_out()
            return True
        except Exception:
            return False
    
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get user profile from database
        
        Args:
            user_id: User UUID
            
        Returns:
            User profile dict or None
        """
        if not self.is_configured():
            return None
        
        try:
            response = self.supabase.table("user_profiles")\
                .select("*")\
                .eq("id", user_id)\
                .single()\
                .execute()
            
            return response.data if response.data else None
        except Exception:
            return None
    
    def is_admin(self, user_id: str) -> bool:
        """
        Check if user has admin role
        
        Args:
            user_id: User UUID
            
        Returns:
            True if user is admin, False otherwise
        """
        if not self.is_configured():
            return False
        
        try:
            # Use RPC function to check admin status
            response = self.supabase.rpc("is_admin", {"check_user_id": user_id}).execute()
            return response.data if response.data else False
        except Exception:
            # Fallback to profile check
            profile = self.get_user_profile(user_id)
            return profile and profile.get("role") == "admin"
    
    def get_all_users(self) -> list:
        """
        Get all users (admin only)
        
        Returns:
            List of user profile dicts
        """
        if not self.is_configured():
            return []
        
        try:
            # Use RPC function to avoid RLS recursion
            response = self.supabase.rpc("get_all_users_admin").execute()
            return response.data if response.data else []
        except Exception as e:
            # Fallback: try direct query (for backwards compatibility)
            try:
                response = self.supabase.table("user_profiles")\
                    .select("*")\
                    .order("created_at", desc=True)\
                    .execute()
                return response.data if response.data else []
            except Exception:
                return []
    
    def update_user_role(self, user_id: str, new_role: str) -> bool:
        """
        Update user role (admin only)
        
        Args:
            user_id: User UUID
            new_role: New role ('user' or 'admin')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured():
            return False
        
        if new_role not in ["user", "admin"]:
            return False
        
        try:
            # Use RPC function to avoid RLS issues
            self.supabase.rpc("update_user_role_admin", {
                "target_user_id": user_id,
                "new_role": new_role
            }).execute()
            return True
        except Exception:
            return False
    
    def deactivate_user(self, user_id: str) -> bool:
        """
        Deactivate user account (admin only)
        
        Args:
            user_id: User UUID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured():
            return False
        
        try:
            # Use RPC function to avoid RLS issues
            self.supabase.rpc("deactivate_user_admin", {
                "target_user_id": user_id
            }).execute()
            return True
        except Exception:
            return False
    
    def log_simulation(self, user_id: str, sim_type: str, 
                      parameters: Dict, duration: float) -> bool:
        """
        Log simulation for analytics
        
        Args:
            user_id: User UUID
            sim_type: Type of simulation ('basic', 'flux', 'sensitivity')
            parameters: Simulation parameters dict
            duration: Simulation duration in seconds
            
        Returns:
            True if logged successfully, False otherwise
        """
        if not self.is_configured():
            return False
        
        try:
            data = {
                "user_id": user_id,
                "simulation_type": sim_type,
                "parameters": parameters,
                "duration_seconds": duration,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("simulation_history").insert(data).execute()
            
            # Increment user simulation count
            profile = self.get_user_profile(user_id)
            if profile:
                current_count = profile.get("simulation_count", 0)
                self.supabase.table("user_profiles")\
                    .update({"simulation_count": current_count + 1})\
                    .eq("id", user_id)\
                    .execute()
            
            return True
        except Exception as e:
            st.warning(f"Failed to log simulation: {e}")
            return False
    
    def get_user_simulations(self, user_id: str, limit: int = 50) -> list:
        """
        Get user's simulation history
        
        Args:
            user_id: User UUID
            limit: Maximum number of records to return
            
        Returns:
            List of simulation records
        """
        if not self.is_configured():
            return []
        
        try:
            response = self.supabase.table("simulation_history")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
        except Exception:
            return []


def require_auth(admin_only: bool = False) -> Callable:
    """
    Decorator to require authentication for a page
    
    Args:
        admin_only: If True, require admin role
        
    Returns:
        Decorated function
        
    Example:
        @require_auth()
        def simulation_page():
            st.title("Simulation")
            # ... page content
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Check if authenticated
            if "authenticated" not in st.session_state or not st.session_state.authenticated:
                st.warning("⚠️ Please log in to access this page")
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🔑 Go to Login", use_container_width=True):
                        st.switch_page("pages/0_Login.py")
                
                st.stop()
            
            # Check if admin is required
            if admin_only and not st.session_state.get("is_admin", False):
                st.error("🔒 Admin access required")
                st.info("This page is restricted to administrators only.")
                st.stop()
            
            # Check if user is active
            if not st.session_state.get("is_active", True):
                st.error("🚫 Account deactivated")
                st.info("Your account has been deactivated. Please contact an administrator.")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def init_session_state():
    """Initialize session state variables for authentication"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "user" not in st.session_state:
        st.session_state.user = None
    
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = None
    
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    
    if "is_active" not in st.session_state:
        st.session_state.is_active = True


def get_user_email() -> Optional[str]:
    """Get current user's email"""
    if st.session_state.get("user"):
        return st.session_state.user.email
    return None


def get_user_id() -> Optional[str]:
    """Get current user's ID"""
    if st.session_state.get("user"):
        return st.session_state.user.id
    return None


def get_user_name() -> Optional[str]:
    """Get current user's full name"""
    if st.session_state.get("user_profile"):
        return st.session_state.user_profile.get("full_name", "User")
    return "User"


def check_page_auth(require_admin: bool = False) -> bool:
    """
    Check authentication and show login prompt if needed.
    Call this at the top of protected pages instead of the repetitive pattern.
    
    Usage:
        from core.auth import init_session_state, check_page_auth
        init_session_state()
        if not check_page_auth():
            st.stop()
    
    Args:
        require_admin: If True, also check for admin role
        
    Returns:
        True if authenticated (and admin if required), False otherwise
    """
    # Check basic authentication
    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.warning("⚠️ Please log in to access this page")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔑 Go to Login", use_container_width=True):
                st.switch_page("pages/0_Login.py")
        return False
    
    # Check admin requirement
    if require_admin and not st.session_state.get("is_admin", False):
        st.error("🔒 Admin access required")
        st.info("This page is restricted to administrators only.")
        return False
    
    # Check if user is active
    if not st.session_state.get("is_active", True):
        st.error("🚫 Account deactivated")
        st.info("Your account has been deactivated. Please contact an administrator.")
        return False
    
    return True
