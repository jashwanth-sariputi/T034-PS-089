
import streamlit as st

from src.auth import register_customer, authenticate_user
from src.database import get_connection


st.set_page_config(
    page_title="PS-089 | Usage Billing",
    page_icon="💳",
    layout="wide"
)


def show_registration():
    st.subheader("Create your account")

    with st.form("registration_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email address")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input(
            "Confirm password",
            type="password"
        )

        plan = st.selectbox(
            "Choose your plan",
            ["STARTER", "GROWTH", "SCALE"]
        )

        submitted = st.form_submit_button(
            "Create account",
            use_container_width=True
        )

        if submitted:
            if password != confirm_password:
                st.error("Passwords do not match.")

            else:
                try:
                    customer_id = register_customer(
                        name,
                        email,
                        password,
                        plan
                    )

                    st.success("Registration successful!")
                    st.info(f"Your customer ID: {customer_id}")
                    st.write("You can now log in.")

                except Exception as error:
                    st.error(str(error))


def show_login():
    st.subheader("Welcome back")

    with st.form("login_form"):
        email = st.text_input("Email address")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button(
            "Login",
            use_container_width=True
        )

        if submitted:
            customer_id = authenticate_user(email, password)

            if customer_id:
                st.session_state["customer_id"] = customer_id
                st.rerun()
            else:
                st.error("Invalid email or password.")


def show_dashboard(customer_id):
    with get_connection() as connection:
        customer = connection.execute(
            """
            SELECT customer_id, customer_name, email,
                   plan_name, monthly_quota
            FROM customers
            WHERE customer_id = ?
            """,
            (customer_id,)
        ).fetchone()

    if customer is None:
        st.error("Customer account not found.")
        st.session_state.clear()
        st.rerun()
        return

    st.title("Usage & Billing Dashboard")
    st.write(f"Welcome, {customer['customer_name']}!")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

    st.divider()

    col1, col2, col3 = st.columns(3)

    col1.metric("Account", customer["customer_id"])
    col2.metric("Current Plan", customer["plan_name"])
    col3.metric(
        "Monthly API Quota",
        f"{customer['monthly_quota']:,}"
    )

    st.subheader("Account Information")
    st.write(f"**Name:** {customer['customer_name']}")
    st.write(f"**Email:** {customer['email']}")

    st.info(
        "Your usage, pricing and invoice information "
        "will appear here as the billing modules are connected."
    )


def main():
    st.sidebar.title("PS-089 Billing Platform")

    if "customer_id" in st.session_state:
        show_dashboard(st.session_state["customer_id"])
        return

    page = st.sidebar.radio(
        "Navigation",
        ["Login", "Register"]
    )

    st.title("API Usage Metering & Billing")
    st.caption(
        "Monitor API consumption, manage plans "
        "and understand your billing."
    )

    if page == "Register":
        show_registration()
    else:
        show_login()


if __name__ == "__main__":
    main()
