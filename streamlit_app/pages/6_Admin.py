"""
Admin Dashboard
User management, analytics, and system configuration.

Author: RBC Metabolic Model Team
Date: 2025-11-22
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add core directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.auth import AuthManager, init_session_state, require_auth, get_user_name
from core.styles import apply_global_styles, render_page_header

st.set_page_config(
    page_title="Admin Dashboard - RBC Model",
    page_icon="⚙️",
    layout="wide"
)

# Apply global styles
apply_global_styles()

# Initialize session state
init_session_state()

# Require admin authentication
@require_auth(admin_only=True)
def admin_page():
    """Main admin dashboard"""
    
    auth = AuthManager()
    
    # Header
    render_page_header(
        "Admin Dashboard",
        "Manage user access, review workspace usage, and monitor operational activity for the RBC modeling platform.",
        "⚙️"
    )
    st.caption(f"Welcome back, {get_user_name()}!")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Users",
        "📊 Analytics",
        "📜 Activity Log",
        "⚙️ Settings"
    ])
    
    # ========================================================================
    # TAB 1: USER MANAGEMENT
    # ========================================================================
    with tab1:
        st.subheader("User Management")
        
        # Get all users
        users = auth.get_all_users()
        
        if not users:
            st.info("No users found in the database")
        else:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_users = len(users)
            active_users = sum(1 for u in users if u.get("is_active", True))
            admin_users = sum(1 for u in users if u.get("role") == "admin")
            total_simulations = sum(u.get("simulation_count", 0) for u in users)
            
            with col1:
                st.metric("Total Users", total_users)
            
            with col2:
                st.metric("Active Users", active_users)
            
            with col3:
                st.metric("Admins", admin_users)
            
            with col4:
                st.metric("Total Simulations", total_simulations)
            
            st.markdown("---")
            
            # User table
            st.markdown("### All Users")
            
            # Prepare DataFrame
            df = pd.DataFrame(users)
            
            # Select and reorder columns
            display_cols = [
                "email", "full_name", "organization", "role",
                "simulation_count", "is_active", "created_at", "last_login"
            ]
            
            # Filter to only existing columns
            display_cols = [col for col in display_cols if col in df.columns]
            df = df[display_cols]
            
            # Format dates
            if "created_at" in df.columns:
                df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            
            if "last_login" in df.columns:
                df["last_login"] = pd.to_datetime(df["last_login"], errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
            
            # Rename columns for display
            df = df.rename(columns={
                "email": "Email",
                "full_name": "Name",
                "organization": "Organization",
                "role": "Role",
                "simulation_count": "Simulations",
                "is_active": "Active",
                "created_at": "Joined",
                "last_login": "Last Login"
            })
            
            # Display with search
            search = st.text_input("🔍 Search users", placeholder="Email, name, or organization...")
            
            if search:
                mask = df.astype(str).apply(
                    lambda x: x.str.contains(search, case=False, na=False)
                ).any(axis=1)
                df = df[mask]
            
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Active": st.column_config.CheckboxColumn("Active"),
                    "Simulations": st.column_config.NumberColumn("Simulations", format="%d")
                }
            )
            
            st.markdown("---")
            
            # User management actions
            st.markdown("### User Management Actions")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Update User Role")
                
                user_emails = [u["email"] for u in users]
                selected_email = st.selectbox(
                    "Select User",
                    user_emails,
                    key="role_user_select"
                )
                
                new_role = st.selectbox(
                    "New Role",
                    ["user", "admin"],
                    key="new_role_select"
                )
                
                if st.button("Update Role", type="primary", use_container_width=True):
                    user_id = next(u["id"] for u in users if u["email"] == selected_email)
                    
                    if auth.update_user_role(user_id, new_role):
                        st.success(f"✅ Updated {selected_email} to {new_role}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update role")
            
            with col2:
                st.markdown("#### Deactivate User")
                
                selected_email_deactivate = st.selectbox(
                    "Select User to Deactivate",
                    user_emails,
                    key="deactivate_user_select"
                )
                
                st.warning("⚠️ This will prevent the user from logging in")
                
                if st.button("Deactivate User", type="secondary", use_container_width=True):
                    user_id = next(u["id"] for u in users if u["email"] == selected_email_deactivate)
                    
                    if auth.deactivate_user(user_id):
                        st.success(f"✅ Deactivated {selected_email_deactivate}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to deactivate user")
    
    # ========================================================================
    # TAB 2: ANALYTICS
    # ========================================================================
    with tab2:
        st.subheader("Usage Analytics")
        
        if not users:
            st.info("No data available")
        else:
            # User registration over time
            st.markdown("### User Registrations")
            
            df_users = pd.DataFrame(users)
            if "created_at" in df_users.columns:
                df_users["created_at"] = pd.to_datetime(df_users["created_at"])
                df_users["date"] = df_users["created_at"].dt.date
                
                registrations_by_day = df_users.groupby("date").size().reset_index(name="count")
                registrations_by_day["cumulative"] = registrations_by_day["count"].cumsum()
                
                st.line_chart(
                    registrations_by_day.set_index("date")["cumulative"],
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # Simulations by user
            st.markdown("### Top Users by Simulations")
            
            top_users = sorted(users, key=lambda x: x.get("simulation_count", 0), reverse=True)[:10]
            
            if top_users:
                top_df = pd.DataFrame([
                    {
                        "User": u.get("full_name", u["email"]),
                        "Email": u["email"],
                        "Simulations": u.get("simulation_count", 0)
                    }
                    for u in top_users
                ])
                
                st.bar_chart(
                    top_df.set_index("User")["Simulations"],
                    use_container_width=True
                )
                
                st.dataframe(
                    top_df,
                    use_container_width=True,
                    hide_index=True
                )
            
            st.markdown("---")
            
            # Role distribution
            st.markdown("### User Role Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                role_counts = df_users["role"].value_counts()
                st.bar_chart(role_counts, use_container_width=True)
            
            with col2:
                active_counts = df_users["is_active"].value_counts()
                st.bar_chart(active_counts, use_container_width=True)
    
    # ========================================================================
    # TAB 3: ACTIVITY LOG
    # ========================================================================
    with tab3:
        st.subheader("Recent Activity")
        
        st.info("💡 Coming soon: Real-time activity monitoring")
        
        # Placeholder for future implementation
        st.markdown("""
        **Planned features:**
        - Real-time simulation monitoring
        - User login/logout events
        - Error tracking
        - Performance metrics
        """)
    
    # ========================================================================
    # TAB 4: SETTINGS
    # ========================================================================
    with tab4:
        st.subheader("System Settings")
        
        st.markdown("### Authentication Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input(
                "Supabase URL",
                value=st.secrets.get("supabase", {}).get("url", "Not configured"),
                disabled=True
            )
        
        with col2:
            st.text_input(
                "Anon Key",
                value="••••••••" if st.secrets.get("supabase", {}).get("anon_key") else "Not configured",
                disabled=True,
                type="password"
            )
        
        if auth.is_configured():
            st.success("✅ Authentication system is properly configured")
        else:
            st.error("❌ Authentication system is not configured")
        
        st.markdown("---")
        
        st.markdown("### System Information")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Python Version", "3.11+")
        
        with col2:
            st.metric("Streamlit Version", st.__version__)
        
        with col3:
            st.metric("Database", "Supabase PostgreSQL")
        
        st.markdown("---")
        
        st.markdown("### Maintenance")
        
        st.warning("⚠️ Danger Zone")
        
        with st.expander("🔧 Advanced Options"):
            st.markdown("""
            **Available maintenance actions:**
            - Clear cached data
            - Regenerate user tokens
            - Export user data (GDPR compliance)
            - Database backup
            
            *These features require additional implementation.*
            """)

# Run the admin page
admin_page()
