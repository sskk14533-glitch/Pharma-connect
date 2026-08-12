
# ============================================================
# PHARMACONNECT DEMO - COMPLETE APP
# ============================================================

import streamlit as st
import sqlite3
import hashlib
import requests
import math
from datetime import date

# Optional map support
try:
    import folium
    from streamlit_folium import st_folium
    MAP_AVAILABLE = True
except Exception:
    MAP_AVAILABLE = False


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="PharmaConnect",
    page_icon="💊",
    layout="wide"
)

DB_PATH = "/content/pharmaconnect/database/pharmaconnect.db"


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return conn


def query_db(query, params=(), fetch=True):

    conn = get_connection()

    try:

        cursor = conn.cursor()
        cursor.execute(query, params)

        if fetch:

            result = cursor.fetchall()

            conn.close()

            return result

        conn.commit()
        conn.close()

        return True

    except Exception:

        conn.rollback()
        conn.close()

        raise


# ============================================================
# PASSWORD
# ============================================================

def hash_password(password):

    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


# ============================================================
# DEMO ACCOUNTS
# ============================================================

DEMO_ACCOUNTS = {

    "rep": {
        "name": "Demo Medical Representative",
        "email": "rep@pharmaconnect.demo",
        "password": "123456",
        "role": "rep"
    },

    "pharmacy": {
        "name": "Demo Pharmacy",
        "email": "pharmacy@pharmaconnect.demo",
        "password": "123456",
        "role": "pharmacy"
    },

    "admin": {
        "name": "Demo Admin",
        "email": "admin@pharmaconnect.demo",
        "password": "admin123",
        "role": "admin"
    }
}


def ensure_demo_accounts():

    """
    Creates the three independent demo accounts
    only if they do not already exist.

    IMPORTANT:
    Roles match the SQLite CHECK constraint exactly:
        rep
        pharmacy
        admin
    """

    for account in DEMO_ACCOUNTS.values():

        existing = query_db(
            """
            SELECT user_id
            FROM users
            WHERE LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (account["email"],)
        )

        if existing:
            continue

        try:

            user_id = create_user_only(
                name=account["name"],
                email=account["email"],
                password=account["password"],
                role=account["role"]
            )

            # ------------------------------------------------
            # Create pharmacy profile ONLY for pharmacy
            # ------------------------------------------------

            if account["role"] == "pharmacy":

                existing_pharmacy = query_db(
                    """
                    SELECT pharmacy_id
                    FROM pharmacies
                    WHERE user_id = ?
                    LIMIT 1
                    """,
                    (user_id,)
                )

                if not existing_pharmacy:

                    create_pharmacy(
                        user_id=user_id,
                        name="Demo Pharmacy",
                        phone="01000000000",
                        address="Cairo, Egypt",
                        latitude=30.0444,
                        longitude=31.2357,
                        entrance="Main entrance",
                        floor="Ground Floor",
                        landmark="Demo Location",
                        parking_notes="Demo parking area",
                        visible_to_reps=1
                    )

        except Exception:
            # Do not break the whole app if demo data
            # already exists in a slightly different database.
            pass


# ============================================================
# USER CREATION
# ============================================================

def create_user_only(
    name,
    email,
    password,
    role
):

    # --------------------------------------------------------
    # VERY IMPORTANT
    # Database accepts ONLY:
    # rep / pharmacy / admin
    # --------------------------------------------------------

    allowed_roles = [
        "rep",
        "pharmacy",
        "admin"
    ]

    if role not in allowed_roles:

        raise ValueError(
            f"Invalid role: {role}. "
            f"Allowed roles are: {allowed_roles}"
        )

    existing = query_db(
        """
        SELECT user_id
        FROM users
        WHERE LOWER(email) = LOWER(?)
        LIMIT 1
        """,
        (email.strip(),)
    )

    if existing:

        raise ValueError(
            "This email is already registered."
        )

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                name.strip(),
                email.strip(),
                hash_password(password),
                role
            )
        )

        user_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return user_id

    except Exception:

        conn.rollback()
        conn.close()

        raise


def create_user(
    name,
    email,
    password,
    role
):

    try:

        user_id = create_user_only(
            name,
            email,
            password,
            role
        )

        return user_id, None

    except Exception as e:

        return None, str(e)


# ============================================================
# AUTHENTICATION
# ============================================================

def login(email, password):

    rows = query_db(
        """
        SELECT *
        FROM users
        WHERE LOWER(email) = LOWER(?)
        LIMIT 1
        """,
        (email.strip(),)
    )

    if not rows:

        return None

    user = rows[0]

    stored_password = user["password"]

    # Support hashed passwords
    if stored_password == hash_password(password):

        return user

    # Support old demo plain-text passwords
    if stored_password == password:

        return user

    return None


# ============================================================
# SESSION STATE
# ============================================================

if "user" not in st.session_state:

    st.session_state.user = None


if "external_results" not in st.session_state:

    st.session_state.external_results = []


if "selected_external" not in st.session_state:

    st.session_state.selected_external = None


# ============================================================
# PHARMACY
# ============================================================

def get_user_pharmacy(user_id):

    rows = query_db(
        """
        SELECT *
        FROM pharmacies
        WHERE user_id = ?
        LIMIT 1
        """,
        (user_id,)
    )

    return rows[0] if rows else None


def create_pharmacy(
    user_id,
    name,
    phone="",
    address="",
    latitude=None,
    longitude=None,
    entrance="",
    floor="",
    landmark="",
    parking_notes="",
    visible_to_reps=1
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # One pharmacy profile per pharmacy account
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT pharmacy_id
            FROM pharmacies
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,)
        )

        existing = cursor.fetchone()

        if existing:

            conn.close()

            return existing["pharmacy_id"]

        cursor.execute(
            """
            INSERT INTO pharmacies
            (
                user_id,
                name,
                phone,
                address,
                latitude,
                longitude,
                entrance,
                floor,
                landmark,
                parking_notes,
                visible_to_reps,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                name,
                phone,
                address,
                latitude,
                longitude,
                entrance,
                floor,
                landmark,
                parking_notes,
                visible_to_reps
            )
        )

        pharmacy_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return pharmacy_id

    except Exception:

        conn.rollback()
        conn.close()

        raise


# ============================================================
# PHARMACY SEARCH
# ============================================================

def search_local_pharmacies(search):

    return query_db(
        """
        SELECT *
        FROM pharmacies
        WHERE visible_to_reps = 1
        AND
        (
            LOWER(name) LIKE LOWER(?)
            OR LOWER(address) LIKE LOWER(?)
        )
        ORDER BY name
        """,
        (
            f"%{search}%",
            f"%{search}%"
        )
    )


# ============================================================
# OPENSTREETMAP
# ============================================================

def search_external_map(
    search,
    location_hint
):

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": f"{search}, {location_hint}",
        "format": "jsonv2",
        "limit": 5,
        "addressdetails": 1
    }

    headers = {
        "User-Agent": "PharmaConnect-Demo/1.0"
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        results = []

        for item in data:

            results.append(
                {
                    "name": item.get(
                        "display_name",
                        search
                    ),

                    "address": item.get(
                        "display_name",
                        ""
                    ),

                    "latitude": float(
                        item["lat"]
                    ),

                    "longitude": float(
                        item["lon"]
                    ),

                    "type": item.get(
                        "type",
                        ""
                    ),

                    "osm_id": item.get(
                        "osm_id"
                    )
                }
            )

        return results, None

    except Exception as e:

        return [], str(e)


# ============================================================
# POINTS
# ============================================================

def get_points_balance(pharmacy_id):

    rows = query_db(
        """
        SELECT COALESCE(
            SUM(points),
            0
        ) AS balance
        FROM points_transactions
        WHERE pharmacy_id = ?
        """,
        (pharmacy_id,)
    )

    return int(
        rows[0]["balance"] or 0
    )


def add_points(
    pharmacy_id,
    points,
    transaction_type,
    description,
    reference_id=None
):

    conn = get_connection()

    try:

        conn.execute(
            """
            INSERT INTO points_transactions
            (
                pharmacy_id,
                purchase_id,
                points,
                transaction_type,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                pharmacy_id,
                reference_id,
                points,
                transaction_type,
                description
            )
        )

        conn.commit()
        conn.close()

    except Exception:

        conn.rollback()
        conn.close()

        raise


# ============================================================
# BONUS
# ============================================================

def calculate_bonus(amount):

    rules = query_db(
        """
        SELECT *
        FROM bonus_rules
        WHERE active = 1
        ORDER BY purchase_threshold DESC
        """
    )

    total_points = 0

    for rule in rules:

        threshold = float(
            rule["purchase_threshold"] or 0
        )

        bonus = int(
            rule["bonus_points"] or 0
        )

        if threshold > 0:

            multiplier = math.floor(
                amount / threshold
            )

            total_points += (
                multiplier * bonus
            )

    return total_points


# ============================================================
# PURCHASE
# ============================================================

def create_purchase(
    pharmacy_id,
    amount
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO purchases
            (
                pharmacy_id,
                amount,
                purchase_date
            )
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (
                pharmacy_id,
                amount
            )
        )

        purchase_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return purchase_id

    except Exception:

        conn.rollback()
        conn.close()

        raise


# ============================================================
# NOTIFICATIONS
# ============================================================

def create_notification(
    user_id,
    title,
    message
):

    conn = get_connection()

    try:

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                is_read,
                created_at
            )
            VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                title,
                message
            )
        )

        conn.commit()
        conn.close()

    except Exception:

        conn.rollback()
        conn.close()

        raise


def get_notifications(user_id):

    return query_db(
        """
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,)
    )


# ============================================================
# ORDERS
# ============================================================

def create_order(
    pharmacy_id,
    rep_user_id,
    amount,
    notes
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO orders
            (
                pharmacy_id,
                rep_user_id,
                total_amount,
                status,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                pharmacy_id,
                rep_user_id,
                amount,
                "pending",
                notes
            )
        )

        order_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return order_id

    except Exception:

        conn.rollback()
        conn.close()

        raise


# ============================================================
# AUTH PAGE
# ============================================================

def show_auth():

    st.title("💊 PharmaConnect")

    st.subheader(
        "AI-Powered Medical Rep & Pharmacy Platform"
    )

    st.write(
        "Connect medical representatives, pharmacies, "
        "campaigns, rewards and smart location services."
    )

    st.divider()

    login_tab, signup_tab = st.tabs(
        [
            "🔐 Login",
            "📝 Sign Up"
        ]
    )

    # ========================================================
    # LOGIN
    # ========================================================

    with login_tab:

        col1, col2, col3 = st.columns(
            [1, 2, 1]
        )

        with col2:

            st.markdown(
                "### 🔐 Login"
            )

            email = st.text_input(
                "Email",
                placeholder="Enter your email",
                key="login_email"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )

            if st.button(
                "🔐 Login",
                use_container_width=True,
                key="login_button"
            ):

                if not email or not password:

                    st.warning(
                        "Please enter email and password."
                    )

                else:

                    user = login(
                        email,
                        password
                    )

                    if user:

                        st.session_state.user = dict(
                            user
                        )

                        st.success(
                            f"Welcome, {user['name']}!"
                        )

                        st.rerun()

                    else:

                        st.error(
                            "❌ Invalid email or password."
                        )

        # ====================================================
        # DEMO LOGIN ACCOUNTS
        # ====================================================

        st.divider()

        st.subheader(
            "🧪 Demo Login Accounts"
        )

        st.info(
            "Use any of the following accounts "
            "to explore the three different dashboards."
        )

        c1, c2, c3 = st.columns(3)

        # ----------------------------------------------------
        # REP
        # ----------------------------------------------------

        with c1:

            st.markdown(
                """
                ### 👨‍💼 Medical Rep

                **Email**

                `rep@pharmaconnect.demo`

                **Password**

                `123456`
                """
            )

            if st.button(
                "Login as Medical Rep",
                use_container_width=True,
                key="demo_rep"
            ):

                st.session_state.user = dict(
                    login(
                        "rep@pharmaconnect.demo",
                        "123456"
                    )
                )

                st.rerun()

        # ----------------------------------------------------
        # PHARMACY
        # ----------------------------------------------------

        with c2:

            st.markdown(
                """
                ### 🏪 Pharmacy

                **Email**

                `pharmacy@pharmaconnect.demo`

                **Password**

                `123456`
                """
            )

            if st.button(
                "Login as Pharmacy",
                use_container_width=True,
                key="demo_pharmacy"
            ):

                st.session_state.user = dict(
                    login(
                        "pharmacy@pharmaconnect.demo",
                        "123456"
                    )
                )

                st.rerun()

        # ----------------------------------------------------
        # ADMIN
        # ----------------------------------------------------

        with c3:

            st.markdown(
                """
                ### 👨‍💻 Admin

                **Email**

                `admin@pharmaconnect.demo`

                **Password**

                `admin123`
                """
            )

            if st.button(
                "Login as Admin",
                use_container_width=True,
                key="demo_admin"
            ):

                st.session_state.user = dict(
                    login(
                        "admin@pharmaconnect.demo",
                        "admin123"
                    )
                )

                st.rerun()

    # ========================================================
    # SIGN UP
    # ========================================================

    with signup_tab:

        st.subheader(
            "📝 Create New Account"
        )

        st.info(
            "Each account type is completely independent. "
            "Creating a Medical Rep account will NOT create "
            "a Pharmacy account."
        )

        # ----------------------------------------------------
        # ROLE
        # ----------------------------------------------------

        role_label = st.radio(
            "Account Type",
            [
                "👨‍💼 Medical Rep",
                "🏪 Pharmacy",
                "👨‍💻 Admin"
            ],
            horizontal=True,
            key="signup_role"
        )

        # ----------------------------------------------------
        # BASIC INFORMATION
        # ----------------------------------------------------

        name = st.text_input(
            "Full Name / Pharmacy Name",
            key="signup_name"
        )

        email = st.text_input(
            "Email",
            key="signup_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="signup_password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="signup_confirm"
        )

        # ====================================================
        # PHARMACY ONLY FIELDS
        # ====================================================

        if role_label == "🏪 Pharmacy":

            st.divider()

            st.markdown(
                "### 🏪 Pharmacy Information"
            )

            st.caption(
                "These fields appear ONLY when creating "
                "a Pharmacy account."
            )

            phone = st.text_input(
                "Phone",
                key="signup_phone"
            )

            address = st.text_area(
                "Full Address",
                key="signup_address"
            )

            col1, col2 = st.columns(2)

            with col1:

                latitude = st.number_input(
                    "Latitude",
                    value=30.0444,
                    format="%.6f",
                    key="signup_lat"
                )

            with col2:

                longitude = st.number_input(
                    "Longitude",
                    value=31.2357,
                    format="%.6f",
                    key="signup_lon"
                )

            entrance = st.text_input(
                "Entrance Description",
                key="signup_entrance"
            )

            floor = st.text_input(
                "Floor",
                key="signup_floor"
            )

            landmark = st.text_input(
                "Landmark",
                key="signup_landmark"
            )

            parking = st.text_area(
                "Parking / Access Notes",
                key="signup_parking"
            )

        else:

            # ------------------------------------------------
            # IMPORTANT:
            # No pharmacy fields for Rep/Admin
            # ------------------------------------------------

            phone = ""
            address = ""
            latitude = None
            longitude = None
            entrance = ""
            floor = ""
            landmark = ""
            parking = ""

        # ====================================================
        # ROLE INFORMATION
        # ====================================================

        if role_label == "👨‍💼 Medical Rep":

            st.info(
                "👨‍💼 Medical Rep account: "
                "Only the Rep user account will be created."
            )

        elif role_label == "🏪 Pharmacy":

            st.info(
                "🏪 Pharmacy account: "
                "A Pharmacy user account and its own "
                "Pharmacy profile will be created."
            )

        elif role_label == "👨‍💻 Admin":

            st.warning(
                "👨‍💻 Demo Admin: Admin registration is enabled "
                "for demonstration only."
            )

        # ====================================================
        # CREATE ACCOUNT
        # ====================================================

        if st.button(
            "🚀 Create Account",
            use_container_width=True,
            key="create_account_button"
        ):

            if not name:

                st.error(
                    "Please enter your name."
                )

            elif not email:

                st.error(
                    "Please enter your email."
                )

            elif not password:

                st.error(
                    "Please enter a password."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            else:

                # ------------------------------------------------
                # Convert UI role to EXACT DB role
                # ------------------------------------------------

                if role_label == "👨‍💼 Medical Rep":

                    account_role = "rep"

                elif role_label == "🏪 Pharmacy":

                    account_role = "pharmacy"

                else:

                    account_role = "admin"

                # ------------------------------------------------
                # Create ONLY the selected user
                # ------------------------------------------------

                user_id, error = create_user(
                    name,
                    email,
                    password,
                    account_role
                )

                if error:

                    st.error(
                        error
                    )

                else:

                    # ============================================
                    # PHARMACY ONLY
                    # ============================================

                    if account_role == "pharmacy":

                        try:

                            pharmacy_id = create_pharmacy(
                                user_id,
                                name,
                                phone,
                                address,
                                latitude,
                                longitude,
                                entrance,
                                floor,
                                landmark,
                                parking,
                                1
                            )

                            st.success(
                                "🎉 Pharmacy account created successfully!"
                            )

                            st.info(
                                f"Pharmacy ID: {pharmacy_id}"
                            )

                        except Exception as e:

                            st.error(
                                f"Pharmacy profile error: {e}"
                            )

                    # ============================================
                    # REP ONLY
                    # ============================================

                    elif account_role == "rep":

                        st.success(
                            "🎉 Medical Rep account created successfully!"
                        )

                        st.info(
                            "No Pharmacy profile was created."
                        )

                    # ============================================
                    # ADMIN ONLY
                    # ============================================

                    elif account_role == "admin":

                        st.success(
                            "🎉 Admin account created successfully!"
                        )

                        st.info(
                            "No Pharmacy or Medical Rep profile was created."
                        )

                    st.info(
                        "You can now login using your "
                        "email and password."
                    )


# ============================================================
# HEADER
# ============================================================

def show_header():

    user = st.session_state.user

    col1, col2 = st.columns(
        [5, 1]
    )

    with col1:

        st.title(
            "💊 PharmaConnect"
        )

        st.caption(
            f"Logged in: {user['name']} "
            f"• Role: {user['role']}"
        )

    with col2:

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            st.session_state.user = None

            st.session_state.external_results = []

            st.session_state.selected_external = None

            st.rerun()


# ============================================================
# MANUAL ADD PHARMACY - MEDICAL REP
# ============================================================

def manual_add_pharmacy_form():

    st.subheader(
        "➕ Add Pharmacy Manually"
    )

    st.caption(
        "The Medical Rep can add a pharmacy even when "
        "it is not found in PharmaConnect or on the map."
    )

    with st.form(
        "manual_add_pharmacy"
    ):

        name = st.text_input(
            "Pharmacy Name"
        )

        phone = st.text_input(
            "Phone"
        )

        address = st.text_area(
            "Full Address"
        )

        col1, col2 = st.columns(2)

        with col1:

            latitude = st.number_input(
                "Latitude",
                value=30.0444,
                format="%.6f"
            )

        with col2:

            longitude = st.number_input(
                "Longitude",
                value=31.2357,
                format="%.6f"
            )

        entrance = st.text_input(
            "Entrance Description"
        )

        floor = st.text_input(
            "Floor"
        )

        landmark = st.text_input(
            "Landmark"
        )

        parking = st.text_area(
            "Parking / Access Notes"
        )

        save = st.form_submit_button(
            "💾 Save Pharmacy",
            use_container_width=True
        )

    if save:

        if not name:

            st.error(
                "Pharmacy name is required."
            )

        else:

            pharmacy_id = create_pharmacy(
                st.session_state.user["user_id"],
                name,
                phone,
                address,
                latitude,
                longitude,
                entrance,
                floor,
                landmark,
                parking,
                1
            )

            st.success(
                f"🎉 Pharmacy added successfully! "
                f"ID: {pharmacy_id}"
            )


# ============================================================
# MEDICAL REP DASHBOARD
# ============================================================

def medical_rep_dashboard():

    st.header(
        "👨‍💼 Medical Representative Dashboard"
    )

    st.write(
        f"Welcome back, "
        f"**{st.session_state.user['name']}**!"
    )

    tabs = st.tabs(
        [
            "🔎 Search Pharmacy",
            "➕ Add Pharmacy",
            "🗺️ Pharmacy Map",
            "📢 Campaigns",
            "⭐ Rewards",
            "📝 Field Feedback",
            "📦 Orders",
            "🔔 Notifications"
        ]
    )

    # ========================================================
    # SEARCH
    # ========================================================

    with tabs[0]:

        st.subheader(
            "🔎 Search Pharmacy"
        )

        search = st.text_input(
            "Pharmacy Name / Address",
            placeholder="Example: Ezz Pharmacy",
            key="rep_search"
        )

        if st.button(
            "🔎 Search PharmaConnect",
            use_container_width=True,
            key="rep_local_search"
        ):

            if not search.strip():

                st.warning(
                    "Enter a pharmacy name."
                )

            else:

                results = search_local_pharmacies(
                    search
                )

                if results:

                    st.success(
                        f"Found {len(results)} pharmacy result(s)."
                    )

                    for pharmacy in results:

                        with st.container(
                            border=True
                        ):

                            st.markdown(
                                f"### 🏪 {pharmacy['name']}"
                            )

                            st.write(
                                f"📍 "
                                f"{pharmacy['address'] or 'No address'}"
                            )

                            if pharmacy["phone"]:

                                st.write(
                                    f"📞 "
                                    f"{pharmacy['phone']}"
                                )

                            if pharmacy["latitude"] is not None:

                                st.write(
                                    f"📌 GPS: "
                                    f"{pharmacy['latitude']}, "
                                    f"{pharmacy['longitude']}"
                                )

                                maps_url = (
                                    "https://www.google.com/maps/search/"
                                    "?api=1&query="
                                    f"{pharmacy['latitude']},"
                                    f"{pharmacy['longitude']}"
                                )

                                st.link_button(
                                    "🗺️ Open Navigation",
                                    maps_url
                                )

                            st.write(
                                f"🚪 Entrance: "
                                f"{pharmacy['entrance'] or '-'}"
                            )

                            st.write(
                                f"🏢 Floor: "
                                f"{pharmacy['floor'] or '-'}"
                            )

                            st.write(
                                f"📌 Landmark: "
                                f"{pharmacy['landmark'] or '-'}"
                            )

                            st.write(
                                f"🚗 Parking: "
                                f"{pharmacy['parking_notes'] or '-'}"
                            )

                else:

                    st.warning(
                        "❌ Pharmacy not found in PharmaConnect."
                    )

                    st.info(
                        "🌍 Let's try Smart Map Search."
                    )

                    location = st.text_input(
                        "Area / City",
                        value="Egypt",
                        key="search_area"
                    )

                    if st.button(
                        "🌍 Search OpenStreetMap",
                        use_container_width=True,
                        key="osm_search"
                    ):

                        with st.spinner(
                            "Searching map..."
                        ):

                            results, error = search_external_map(
                                search,
                                location
                            )

                        if error:

                            st.error(
                                f"Map error: {error}"
                            )

                        elif results:

                            st.session_state.external_results = results

                            st.success(
                                f"Found {len(results)} "
                                f"possible result(s)."
                            )

                        else:

                            st.warning(
                                "❌ Pharmacy was not found on the map."
                            )

                            st.info(
                                "You can add it manually."
                            )

        # ====================================================
        # MAP SEARCH RESULTS
        # ====================================================

        if st.session_state.external_results:

            st.divider()

            st.subheader(
                "🌍 Smart Map Discovery"
            )

            for i, result in enumerate(
                st.session_state.external_results
            ):

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 📍 Result {i + 1}"
                    )

                    st.write(
                        result["name"]
                    )

                    st.caption(
                        result["address"]
                    )

                    st.write(
                        f"📌 Latitude: "
                        f"{result['latitude']}"
                    )

                    st.write(
                        f"📌 Longitude: "
                        f"{result['longitude']}"
                    )

                    maps_url = (
                        "https://www.google.com/maps/search/"
                        "?api=1&query="
                        f"{result['latitude']},"
                        f"{result['longitude']}"
                    )

                    col1, col2 = st.columns(2)

                    with col1:

                        st.link_button(
                            "🗺️ Open Location",
                            maps_url,
                            use_container_width=True
                        )

                    with col2:

                        if st.button(
                            "➕ Add This Pharmacy",
                            key=f"map_add_{i}",
                            use_container_width=True
                        ):

                            st.session_state.selected_external = result

                            st.rerun()

        # ====================================================
        # CONFIRM MAP PHARMACY
        # ====================================================

        selected = st.session_state.selected_external

        if selected:

            st.divider()

            st.subheader(
                "✅ Add Pharmacy From Map"
            )

            st.info(
                selected["address"]
            )

            with st.form(
                "map_pharmacy_form"
            ):

                name = st.text_input(
                    "Pharmacy Name",
                    value=selected["name"].split(",")[0]
                )

                address = st.text_area(
                    "Address",
                    value=selected["address"]
                )

                phone = st.text_input(
                    "Phone"
                )

                entrance = st.text_input(
                    "Entrance"
                )

                floor = st.text_input(
                    "Floor"
                )

                landmark = st.text_input(
                    "Landmark"
                )

                parking = st.text_area(
                    "Parking Notes"
                )

                save = st.form_submit_button(
                    "💾 Add to PharmaConnect",
                    use_container_width=True
                )

            if save:

                pharmacy_id = create_pharmacy(
                    st.session_state.user["user_id"],
                    name,
                    phone,
                    address,
                    selected["latitude"],
                    selected["longitude"],
                    entrance,
                    floor,
                    landmark,
                    parking,
                    1
                )

                st.success(
                    f"🎉 Pharmacy added! "
                    f"ID: {pharmacy_id}"
                )

                st.session_state.external_results = []

                st.session_state.selected_external = None

                st.rerun()

    # ========================================================
    # ADD PHARMACY
    # ========================================================

    with tabs[1]:

        manual_add_pharmacy_form()

    # ========================================================
    # PHARMACY MAP
    # ========================================================

    with tabs[2]:

        st.subheader(
            "🗺️ Pharmacy Location Hub"
        )

        pharmacies = query_db(
            """
            SELECT *
            FROM pharmacies
            WHERE visible_to_reps = 1
            ORDER BY name
            """
        )

        if not pharmacies:

            st.info(
                "No pharmacies registered yet."
            )

        elif not MAP_AVAILABLE:

            st.warning(
                "Map package is not installed."
            )

            for pharmacy in pharmacies:

                st.write(
                    f"🏪 {pharmacy['name']} — "
                    f"{pharmacy['address'] or '-'}"
                )

        else:

            pharmacies_with_location = [
                p for p in pharmacies
                if p["latitude"] is not None
                and p["longitude"] is not None
            ]

            if pharmacies_with_location:

                center_lat = sum(
                    p["latitude"]
                    for p in pharmacies_with_location
                ) / len(
                    pharmacies_with_location
                )

                center_lon = sum(
                    p["longitude"]
                    for p in pharmacies_with_location
                ) / len(
                    pharmacies_with_location
                )

                pharmacy_map = folium.Map(
                    location=[
                        center_lat,
                        center_lon
                    ],
                    zoom_start=11
                )

                for pharmacy in pharmacies_with_location:

                    popup = f"""
                    <b>🏪 {pharmacy['name']}</b><br>
                    📍 {pharmacy['address'] or '-'}<br>
                    🚪 {pharmacy['entrance'] or '-'}<br>
                    🏢 {pharmacy['floor'] or '-'}<br>
                    📌 {pharmacy['landmark'] or '-'}<br>
                    🚗 {pharmacy['parking_notes'] or '-'}
                    """

                    folium.Marker(
                        location=[
                            pharmacy["latitude"],
                            pharmacy["longitude"]
                        ],
                        popup=popup,
                        tooltip=pharmacy["name"]
                    ).add_to(
                        pharmacy_map
                    )

                st_folium(
                    pharmacy_map,
                    width=None,
                    height=550
                )

            else:

                st.info(
                    "No pharmacies have GPS coordinates."
                )

    # ========================================================
    # CAMPAIGNS
    # ========================================================

    with tabs[3]:

        st.subheader(
            "📢 Campaigns"
        )

        try:

            campaigns = query_db(
                """
                SELECT *
                FROM campaigns
                WHERE active = 1
                OR status = 'active'
                ORDER BY created_at DESC
                """
            )

        except Exception:

            campaigns = []

        if campaigns:

            for campaign in campaigns:

                title = (
                    campaign["title"]
                    or campaign["name"]
                    or "Campaign"
                )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🎯 {title}"
                    )

                    st.write(
                        campaign["description"] or ""
                    )

                    st.write(
                        f"Minimum Purchase: "
                        f"{campaign['minimum_purchase'] or 0:,.0f} EGP"
                    )

                    st.write(
                        f"Reward: "
                        f"{campaign['reward_points'] or 0:,.0f} points"
                    )

        else:

            st.info(
                "No active campaigns."
            )

    # ========================================================
    # REWARDS
    # ========================================================

    with tabs[4]:

        st.subheader(
            "⭐ Rewards Tracking"
        )

        st.info(
            "Medical Rep can monitor the available "
            "Rewards / Campaign reward structure."
        )

        try:

            rewards = query_db(
                """
                SELECT *
                FROM rewards
                WHERE active = 1
                ORDER BY points_required
                """
            )

        except Exception:

            rewards = []

        if rewards:

            for reward in rewards:

                name = (
                    reward["name"]
                    or reward["reward_name"]
                    or "Reward"
                )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🎁 {name}"
                    )

                    st.write(
                        reward["description"] or ""
                    )

                    st.write(
                        f"⭐ Required: "
                        f"{int(reward['points_required'] or 0):,}"
                    )

                    st.write(
                        f"📦 Stock: "
                        f"{int(reward['stock'] or 0):,}"
                    )

        else:

            st.info(
                "No rewards available."
            )

    # ========================================================
    # FIELD FEEDBACK
    # ========================================================

    with tabs[5]:

        st.subheader(
            "📝 Field Feedback"
        )

        feedback_pharmacy = st.text_input(
            "Pharmacy Name",
            key="feedback_pharmacy"
        )

        feedback_type = st.selectbox(
            "Feedback Type",
            [
                "General Feedback",
                "Campaign Feedback",
                "Product Feedback",
                "Location Issue",
                "Customer / Pharmacy Issue"
            ],
            key="feedback_type"
        )

        feedback_text = st.text_area(
            "Feedback",
            key="feedback_text"
        )

        if st.button(
            "📤 Submit Feedback",
            use_container_width=True
        ):

            if not feedback_text.strip():

                st.warning(
                    "Please enter your feedback."
                )

            else:

                st.success(
                    "✅ Field feedback submitted successfully."
                )

    # ========================================================
    # ORDERS
    # ========================================================

    with tabs[6]:

        st.subheader(
            "📦 Create Order"
        )

        pharmacies = query_db(
            """
            SELECT *
            FROM pharmacies
            WHERE visible_to_reps = 1
            ORDER BY name
            """
        )

        if pharmacies:

            pharmacy_options = {
                f"{p['name']} — "
                f"{p['address'] or 'No address'}":
                p["pharmacy_id"]
                for p in pharmacies
            }

            selected_label = st.selectbox(
                "Pharmacy",
                list(
                    pharmacy_options.keys()
                ),
                key="order_pharmacy"
            )

            amount = st.number_input(
                "Order Amount (EGP)",
                min_value=0.0,
                step=1000.0,
                key="order_amount"
            )

            notes = st.text_area(
                "Notes",
                key="order_notes"
            )

            if st.button(
                "📦 Create Order",
                use_container_width=True
            ):

                order_id = create_order(
                    pharmacy_options[
                        selected_label
                    ],
                    st.session_state.user["user_id"],
                    amount,
                    notes
                )

                st.success(
                    f"Order #{order_id} "
                    f"created successfully."
                )

        else:

            st.info(
                "No pharmacies available."
            )

    # ========================================================
    # NOTIFICATIONS
    # ========================================================

    with tabs[7]:

        st.subheader(
            "🔔 Notifications"
        )

        notifications = get_notifications(
            st.session_state.user["user_id"]
        )

        if notifications:

            for n in notifications:

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🔔 {n['title']}"
                    )

                    st.write(
                        n["message"]
                    )

                    st.caption(
                        str(n["created_at"])
                    )

        else:

            st.info(
                "No notifications yet."
            )


# ============================================================
# PHARMACY DASHBOARD
# ============================================================

def pharmacy_dashboard():

    pharmacy = get_user_pharmacy(
        st.session_state.user["user_id"]
    )

    st.header(
        "🏪 Pharmacy Dashboard"
    )

    if not pharmacy:

        st.error(
            "No pharmacy profile found for this account."
        )

        return

    balance = get_points_balance(
        pharmacy["pharmacy_id"]
    )

    st.metric(
        "⭐ Available Points",
        balance
    )

    tabs = st.tabs(
        [
            "🏪 My Pharmacy",
            "📢 Campaigns",
            "💰 Purchases",
            "⭐ Wallet",
            "🎁 Rewards",
            "🔔 Notifications"
        ]
    )

    # ========================================================
    # PROFILE
    # ========================================================

    with tabs[0]:

        st.subheader(
            pharmacy["name"]
        )

        st.write(
            f"📍 Address: "
            f"{pharmacy['address'] or '-'}"
        )

        st.write(
            f"📞 Phone: "
            f"{pharmacy['phone'] or '-'}"
        )

        st.write(
            f"🚪 Entrance: "
            f"{pharmacy['entrance'] or '-'}"
        )

        st.write(
            f"🏢 Floor: "
            f"{pharmacy['floor'] or '-'}"
        )

        st.write(
            f"📌 Landmark: "
            f"{pharmacy['landmark'] or '-'}"
        )

        st.write(
            f"🚗 Parking / Access: "
            f"{pharmacy['parking_notes'] or '-'}"
        )

        if (
            pharmacy["latitude"] is not None
            and pharmacy["longitude"] is not None
        ):

            if MAP_AVAILABLE:

                pharmacy_map = folium.Map(
                    location=[
                        pharmacy["latitude"],
                        pharmacy["longitude"]
                    ],
                    zoom_start=16
                )

                folium.Marker(
                    location=[
                        pharmacy["latitude"],
                        pharmacy["longitude"]
                    ],
                    popup=pharmacy["name"],
                    tooltip="My Pharmacy"
                ).add_to(
                    pharmacy_map
                )

                st_folium(
                    pharmacy_map,
                    width=None,
                    height=450
                )

            else:

                st.write(
                    f"📍 GPS: "
                    f"{pharmacy['latitude']}, "
                    f"{pharmacy['longitude']}"
                )

    # ========================================================
    # CAMPAIGNS
    # ========================================================

    with tabs[1]:

        st.subheader(
            "📢 Available Campaigns"
        )

        try:

            campaigns = query_db(
                """
                SELECT *
                FROM campaigns
                WHERE active = 1
                OR status = 'active'
                ORDER BY created_at DESC
                """
            )

        except Exception:

            campaigns = []

        if campaigns:

            for campaign in campaigns:

                title = (
                    campaign["title"]
                    or campaign["name"]
                    or "Campaign"
                )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🎯 {title}"
                    )

                    st.write(
                        campaign["description"] or ""
                    )

                    st.write(
                        f"Minimum Purchase: "
                        f"{campaign['minimum_purchase'] or 0:,.0f} EGP"
                    )

                    st.write(
                        f"Reward: "
                        f"{campaign['reward_points'] or 0:,.0f} points"
                    )

                    try:

                        accepted = query_db(
                            """
                            SELECT acceptance_id
                            FROM campaign_acceptances
                            WHERE campaign_id = ?
                            AND pharmacy_id = ?
                            LIMIT 1
                            """,
                            (
                                campaign["campaign_id"],
                                pharmacy["pharmacy_id"]
                            )
                        )

                        if accepted:

                            st.success(
                                "✅ Campaign Accepted"
                            )

                        else:

                            if st.button(
                                "✅ Accept Campaign",
                                key=f"accept_campaign_{campaign['campaign_id']}"
                            ):

                                query_db(
                                    """
                                    INSERT INTO campaign_acceptances
                                    (
                                        campaign_id,
                                        pharmacy_id,
                                        status,
                                        accepted_at
                                    )
                                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                                    """,
                                    (
                                        campaign["campaign_id"],
                                        pharmacy["pharmacy_id"],
                                        "accepted"
                                    ),
                                    fetch=False
                                )

                                st.success(
                                    "Campaign accepted!"
                                )

                                st.rerun()

                    except Exception:

                        st.info(
                            "Campaign available."
                        )

        else:

            st.info(
                "No active campaigns."
            )

    # ========================================================
    # PURCHASES
    # ========================================================

    with tabs[2]:

        st.subheader(
            "💰 Purchases"
        )

        purchases = query_db(
            """
            SELECT *
            FROM purchases
            WHERE pharmacy_id = ?
            ORDER BY purchase_date DESC
            """,
            (
                pharmacy["pharmacy_id"],
            )
        )

        if purchases:

            for p in purchases:

                st.write(
                    f"💰 "
                    f"{p['amount']:,.2f} EGP "
                    f"— {p['purchase_date']}"
                )

        else:

            st.info(
                "No purchases yet."
            )

        st.divider()

        st.subheader(
            "🧪 Demo Purchase"
        )

        amount = st.number_input(
            "Purchase Amount",
            min_value=0.0,
            step=1000.0,
            key="purchase_amount"
        )

        if st.button(
            "Add Purchase & Calculate Bonus",
            use_container_width=True,
            key="add_purchase"
        ):

            if amount <= 0:

                st.warning(
                    "Enter an amount."
                )

            else:

                purchase_id = create_purchase(
                    pharmacy["pharmacy_id"],
                    amount
                )

                points = calculate_bonus(
                    amount
                )

                if points > 0:

                    add_points(
                        pharmacy["pharmacy_id"],
                        points,
                        "purchase_bonus",
                        f"Purchase bonus for {amount:,.2f} EGP",
                        purchase_id
                    )

                st.success(
                    "Purchase recorded."
                )

                st.info(
                    f"⭐ Bonus earned: "
                    f"{points:,} points"
                )

                st.rerun()

    # ========================================================
    # WALLET
    # ========================================================

    with tabs[3]:

        st.subheader(
            "⭐ Points Wallet"
        )

        rows = query_db(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN points > 0
                            THEN points
                            ELSE 0
                        END
                    ),
                    0
                ) AS earned,

                COALESCE(
                    SUM(
                        CASE
                            WHEN points < 0
                            THEN ABS(points)
                            ELSE 0
                        END
                    ),
                    0
                ) AS redeemed,

                COALESCE(
                    SUM(points),
                    0
                ) AS available

            FROM points_transactions
            WHERE pharmacy_id = ?
            """,
            (
                pharmacy["pharmacy_id"],
            )
        )

        wallet = rows[0]

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "⭐ Earned",
                int(wallet["earned"] or 0)
            )

        with c2:

            st.metric(
                "🎁 Redeemed",
                int(wallet["redeemed"] or 0)
            )

        with c3:

            st.metric(
                "💰 Available",
                int(wallet["available"] or 0)
            )

        st.divider()

        st.subheader(
            "📜 Transaction History"
        )

        transactions = query_db(
            """
            SELECT *
            FROM points_transactions
            WHERE pharmacy_id = ?
            ORDER BY created_at DESC
            """,
            (
                pharmacy["pharmacy_id"],
            )
        )

        if transactions:

            for transaction in transactions:

                points = int(
                    transaction["points"] or 0
                )

                if points >= 0:

                    icon = "🟢"

                else:

                    icon = "🔴"

                st.write(
                    f"{icon} "
                    f"{points:+,} points — "
                    f"{transaction['description']}"
                )

        else:

            st.info(
                "No point transactions yet."
            )

    # ========================================================
    # REWARDS
    # ========================================================

    with tabs[4]:

        st.subheader(
            "🎁 Rewards"
        )

        balance = get_points_balance(
            pharmacy["pharmacy_id"]
        )

        st.metric(
            "⭐ Your Points",
            balance
        )

        rewards = query_db(
            """
            SELECT *
            FROM rewards
            WHERE active = 1
            ORDER BY points_required
            """
        )

        if rewards:

            for reward in rewards:

                reward_name = (
                    reward["name"]
                    or reward["reward_name"]
                    or "Reward"
                )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🎁 {reward_name}"
                    )

                    st.write(
                        reward["description"] or ""
                    )

                    required = int(
                        reward["points_required"] or 0
                    )

                    stock = int(
                        reward["stock"] or 0
                    )

                    st.write(
                        f"⭐ Required: "
                        f"{required:,}"
                    )

                    st.write(
                        f"📦 Stock: "
                        f"{stock}"
                    )

                    if (
                        balance >= required
                        and stock > 0
                    ):

                        if st.button(
                            "🎁 Redeem",
                            key=f"redeem_{reward['reward_id']}"
                        ):

                            add_points(
                                pharmacy["pharmacy_id"],
                                -required,
                                "reward_redemption",
                                f"Redeemed {reward_name}",
                                reward["reward_id"]
                            )

                            query_db(
                                """
                                UPDATE rewards
                                SET stock = stock - 1
                                WHERE reward_id = ?
                                AND stock > 0
                                """,
                                (
                                    reward["reward_id"],
                                ),
                                fetch=False
                            )

                            st.success(
                                f"🎉 {reward_name} redeemed!"
                            )

                            st.rerun()

                    elif stock <= 0:

                        st.warning(
                            "Out of stock."
                        )

                    else:

                        st.warning(
                            "Not enough points."
                        )

        else:

            st.info(
                "No rewards available."
            )

    # ========================================================
    # NOTIFICATIONS
    # ========================================================

    with tabs[5]:

        st.subheader(
            "🔔 Notifications"
        )

        notifications = get_notifications(
            st.session_state.user["user_id"]
        )

        if notifications:

            for n in notifications:

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🔔 {n['title']}"
                    )

                    st.write(
                        n["message"]
                    )

                    st.caption(
                        str(n["created_at"])
                    )

        else:

            st.info(
                "No notifications yet."
            )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def admin_dashboard():

    st.header(
        "👨‍💻 Admin Dashboard"
    )

    st.info(
        "🧪 DEMO MODE: Full Admin control is enabled."
    )

    tabs = st.tabs(
        [
            "📊 Overview",
            "👥 Users",
            "🏪 Pharmacies",
            "💰 Bonus Rules",
            "📢 Campaigns",
            "🎁 Rewards",
            "💳 Transactions",
            "📊 Reports",
            "🔔 Notifications"
        ]
    )

    # ========================================================
    # OVERVIEW
    # ========================================================

    with tabs[0]:

        users_count = query_db(
            """
            SELECT COUNT(*) AS c
            FROM users
            """
        )[0]["c"]

        pharmacy_count = query_db(
            """
            SELECT COUNT(*) AS c
            FROM pharmacies
            """
        )[0]["c"]

        reps_count = query_db(
            """
            SELECT COUNT(*) AS c
            FROM users
            WHERE role = 'rep'
            """
        )[0]["c"]

        orders_count = query_db(
            """
            SELECT COUNT(*) AS c
            FROM orders
            """
        )[0]["c"]

        campaigns_count = query_db(
            """
            SELECT COUNT(*) AS c
            FROM campaigns
            """
        )[0]["c"]

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(
            "👥 Users",
            users_count
        )

        c2.metric(
            "🏪 Pharmacies",
            pharmacy_count
        )

        c3.metric(
            "👨‍💼 Medical Reps",
            reps_count
        )

        c4.metric(
            "📦 Orders",
            orders_count
        )

        c5.metric(
            "📢 Campaigns",
            campaigns_count
        )

    # ========================================================
    # USERS
    # ========================================================

    with tabs[1]:

        st.subheader(
            "👥 Manage Users"
        )

        users = query_db(
            """
            SELECT
                user_id,
                name,
                email,
                role,
                created_at
            FROM users
            ORDER BY created_at DESC
            """
        )

        if users:

            for user in users:

                with st.container(
                    border=True
                ):

                    role = user["role"]

                    if role == "rep":

                        role_display = (
                            "👨‍💼 Medical Rep"
                        )

                    elif role == "pharmacy":

                        role_display = (
                            "🏪 Pharmacy"
                        )

                    elif role == "admin":

                        role_display = (
                            "👨‍💻 Admin"
                        )

                    else:

                        role_display = role

                    st.markdown(
                        f"### {user['name']}"
                    )

                    st.write(
                        f"📧 {user['email']}"
                    )

                    st.write(
                        f"Role: {role_display}"
                    )

                    st.caption(
                        str(user["created_at"])
                    )

        else:

            st.info(
                "No users found."
            )

    # ========================================================
    # PHARMACIES
    # ========================================================

    with tabs[2]:

        st.subheader(
            "🏪 Manage Pharmacies"
        )

        pharmacies = query_db(
            """
            SELECT *
            FROM pharmacies
            ORDER BY created_at DESC
            """
        )

        if pharmacies:

            for pharmacy in pharmacies:

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### 🏪 {pharmacy['name']}"
                    )

                    st.write(
                        f"📍 "
                        f"{pharmacy['address'] or '-'}"
                    )

                    st.write(
                        f"📞 "
                        f"{pharmacy['phone'] or '-'}"
                    )

                    st.write(
                        f"📌 GPS: "
                        f"{pharmacy['latitude']}, "
                        f"{pharmacy['longitude']}"
                    )

                    st.write(
                        "👁️ Visible to Reps: "
                        +
                        (
                            "Yes"
                            if pharmacy["visible_to_reps"]
                            else "No"
                        )
                    )

        else:

            st.info(
                "No pharmacies yet."
            )

    # ========================================================
    # BONUS RULES
    # ========================================================

    with tabs[3]:

        st.subheader(
            "💰 Points Rules"
        )

        rules = query_db(
            """
            SELECT *
            FROM bonus_rules
            ORDER BY purchase_threshold
            """
        )

        if rules:

            for rule in rules:

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### "
                        f"{rule['name'] or 'Bonus Rule'}"
                    )

                    st.write(
                        f"💰 "
                        f"{rule['purchase_threshold']:,.0f} EGP "
                        f"→ "
                        f"⭐ "
                        f"{rule['bonus_points']:,} points"
                    )

                    if st.button(
                        "🗑️ Delete Rule",
                        key=f"delete_bonus_{rule['rule_id']}"
                    ):

                        query_db(
                            """
                            DELETE FROM bonus_rules
                            WHERE rule_id = ?
                            """,
                            (
                                rule["rule_id"],
                            ),
                            fetch=False
                        )

                        st.rerun()

        st.divider()

        st.subheader(
            "➕ Add Bonus Rule"
        )

        rule_name = st.text_input(
            "Rule Name",
            key="rule_name"
        )

        threshold = st.number_input(
            "Purchase Threshold (EGP)",
            min_value=1.0,
            value=100000.0,
            step=10000.0,
            key="rule_threshold"
        )

        bonus_points = st.number_input(
            "Bonus Points",
            min_value=1,
            value=10000,
            step=1000,
            key="rule_points"
        )

        if st.button(
            "💾 Save Bonus Rule",
            use_container_width=True,
            key="save_bonus"
        ):

            query_db(
                """
                INSERT INTO bonus_rules
                (
                    name,
                    purchase_threshold,
                    bonus_points,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (
                    rule_name or "Bonus Rule",
                    threshold,
                    bonus_points
                ),
                fetch=False
            )

            st.success(
                "Bonus rule added."
            )

            st.rerun()

    # ========================================================
    # CAMPAIGNS
    # ========================================================

    with tabs[4]:

        st.subheader(
            "📢 Campaign Management"
        )

        title = st.text_input(
            "Campaign Title",
            key="campaign_title"
        )

        description = st.text_area(
            "Campaign Description",
            key="campaign_description"
        )

        minimum_purchase = st.number_input(
            "Minimum Purchase",
            min_value=0.0,
            step=1000.0,
            key="campaign_minimum"
        )

        reward_points = st.number_input(
            "Reward Points",
            min_value=0.0,
            step=100.0,
            key="campaign_reward"
        )

        start_date = st.date_input(
            "Start Date",
            value=date.today(),
            key="campaign_start"
        )

        end_date = st.date_input(
            "End Date",
            value=date.today(),
            key="campaign_end"
        )

        if st.button(
            "📢 Create Campaign",
            use_container_width=True,
            key="create_campaign"
        ):

            if not title:

                st.warning(
                    "Campaign title is required."
                )

            else:

                query_db(
                    """
                    INSERT INTO campaigns
                    (
                        name,
                        title,
                        description,
                        minimum_purchase,
                        reward_points,
                        start_date,
                        end_date,
                        status,
                        target,
                        active,
                        created_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        title,
                        title,
                        description,
                        minimum_purchase,
                        reward_points,
                        str(start_date),
                        str(end_date),
                        "active",
                        "pharmacy"
                    ),
                    fetch=False
                )

                # Notify pharmacies
                pharmacy_users = query_db(
                    """
                    SELECT user_id
                    FROM pharmacies
                    WHERE user_id IS NOT NULL
                    """
                )

                for p in pharmacy_users:

                    create_notification(
                        p["user_id"],
                        "🎯 New Campaign",
                        f"A new campaign '{title}' is available."
                    )

                st.success(
                    "Campaign created and pharmacies notified."
                )

                st.rerun()

        st.divider()

        campaigns = query_db(
            """
            SELECT *
            FROM campaigns
            ORDER BY created_at DESC
            """
        )

        for campaign in campaigns:

            title_display = (
                campaign["title"]
                or campaign["name"]
                or "Campaign"
            )

            with st.container(
                border=True
            ):

                st.markdown(
                    f"### 🎯 {title_display}"
                )

                st.write(
                    campaign["description"] or ""
                )

                st.write(
                    f"Minimum Purchase: "
                    f"{campaign['minimum_purchase'] or 0:,.0f}"
                )

                st.write(
                    f"Reward: "
                    f"{campaign['reward_points'] or 0:,.0f} points"
                )

    # ========================================================
    # REWARDS
    # ========================================================

    with tabs[5]:

        st.subheader(
            "🎁 Rewards Management"
        )

        reward_name = st.text_input(
            "Reward Name",
            key="reward_name"
        )

        reward_description = st.text_area(
            "Reward Description",
            key="reward_description"
        )

        points_required = st.number_input(
            "Points Required",
            min_value=1,
            step=500,
            key="reward_points_required"
        )

        stock = st.number_input(
            "Stock",
            min_value=0,
            step=1,
            key="reward_stock"
        )

        if st.button(
            "➕ Add Reward",
            use_container_width=True,
            key="add_reward"
        ):

            if not reward_name:

                st.warning(
                    "Reward name is required."
                )

            else:

                query_db(
                    """
                    INSERT INTO rewards
                    (
                        name,
                        description,
                        points_required,
                        stock,
                        active,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """,
                    (
                        reward_name,
                        reward_description,
                        points_required,
                        stock
                    ),
                    fetch=False
                )

                st.success(
                    "Reward added."
                )

                st.rerun()

        st.divider()

        rewards = query_db(
            """
            SELECT *
            FROM rewards
            ORDER BY points_required
            """
        )

        for reward in rewards:

            name = (
                reward["name"]
                or reward["reward_name"]
                or "Reward"
            )

            st.write(
                f"🎁 {name} | "
                f"{reward['points_required']} points | "
                f"Stock: {reward['stock']}"
            )

    # ========================================================
    # TRANSACTIONS
    # ========================================================

    with tabs[6]:

        st.subheader(
            "💳 View Transactions"
        )

        try:

            transactions = query_db(
                """
                SELECT *
                FROM points_transactions
                ORDER BY created_at DESC
                """
            )

            if transactions:

                for transaction in transactions:

                    st.write(
                        f"⭐ "
                        f"{transaction['points']:+,} points | "
                        f"{transaction['transaction_type']} | "
                        f"{transaction['description']} | "
                        f"{transaction['created_at']}"
                    )

            else:

                st.info(
                    "No transactions yet."
                )

        except Exception as e:

            st.warning(
                f"Transactions are not available: {e}"
            )

    # ========================================================
    # REPORTS
    # ========================================================

    with tabs[7]:

        st.subheader(
            "📊 Reports"

        )

        try:

            purchase_rows = query_db(
                """
                SELECT
                    COUNT(*) AS purchases_count,
                    COALESCE(
                        SUM(amount),
                        0
                    ) AS total_sales
                FROM purchases
                """
            )

            purchase_data = purchase_rows[0]

            c1, c2 = st.columns(2)

            with c1:

                st.metric(
                    "🛒 Purchases",
                    int(
                        purchase_data[
                            "purchases_count"
                        ] or 0
                    )
                )

            with c2:

                st.metric(
                    "💰 Total Purchase Value",
                    f"{float(purchase_data['total_sales'] or 0):,.2f} EGP"
                )

        except Exception:

            st.info(
                "No report data available yet."
            )

    # ========================================================
    # NOTIFICATIONS
    # ========================================================

    with tabs[8]:

        st.subheader(
            "🔔 Send Notification"
        )

        users = query_db(
            """
            SELECT
                user_id,
                name,
                email,
                role
            FROM users
            ORDER BY name
            """
        )

        if users:

            user_options = {
                f"{u['name']} — "
                f"{u['role']} — "
                f"{u['email']}":
                u["user_id"]
                for u in users
            }

            selected_user = st.selectbox(
                "Recipient",
                list(
                    user_options.keys()
                ),
                key="notification_recipient"
            )

            notification_title = st.text_input(
                "Notification Title",
                key="notification_title"
            )

            notification_message = st.text_area(
                "Notification Message",
                key="notification_message"
            )

            if st.button(
                "📨 Send Notification",
                use_container_width=True,
                key="send_notification"
            ):

                if not notification_title:

                    st.warning(
                        "Enter a notification title."
                    )

                elif not notification_message:

                    st.warning(
                        "Enter a notification message."
                    )

                else:

                    create_notification(
                        user_options[
                            selected_user
                        ],
                        notification_title,
                        notification_message
                    )

                    st.success(
                        "Notification sent successfully."
                    )


# ============================================================
# MAIN APP
# ============================================================

# ------------------------------------------------------------
# Make sure the demo accounts exist
# ------------------------------------------------------------

ensure_demo_accounts()


# ------------------------------------------------------------
# START APPLICATION
# ------------------------------------------------------------

if st.session_state.user is None:

    show_auth()

else:

    show_header()

    role = (
        st.session_state.user["role"]
        .lower()
        .strip()
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Database role is "rep", NOT "medical_rep"
    # --------------------------------------------------------

    if role == "rep":

        medical_rep_dashboard()

    elif role == "pharmacy":

        pharmacy_dashboard()

    elif role == "admin":

        admin_dashboard()

    else:

        st.error(
            f"Unknown user role: {role}"
        )
