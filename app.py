import streamlit as st
from streamlit_modal import Modal
import streamlit_authenticator as stauth
import env as env
from datetime import datetime
import time

from mutual_funds import Portfolio
from plots_and_summary import *

import matplotlib

cmap = matplotlib.colormaps["RdYlGn"]

logger = get_simple_logger("app")
st.set_page_config(
    layout="wide",
    page_title="Mutual Fund Portfolio Analysis",
    page_icon="📈",
    initial_sidebar_state="auto",
)

st.title("Mutual Fund Portfolio Analysis")


@st.cache_data
def create_portfolio(username, date):
    client = get_mongo_client()
    transactions = get_transactions(client, username)

    portfolio = Portfolio(transactions=transactions)
    pnl = portfolio.get_pnl_timeseries()
    return pnl, portfolio


@st.cache_data
def load_config_():
    return load_config()


@st.cache_data
def get_all_holdings_(pnl):
    return get_all_holdings(pnl)


config = load_config_()
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    config["pre-authorized"],
)

name, authentication_status, username = authenticator.login(
    location="main", fields=["name", "username"]
)

if st.session_state["authentication_status"]:
    authenticator.logout(location="sidebar")
    with st.sidebar:
        reset_btn = st.button("Reset Password", key="reset-password")
    with st.sidebar:
        st.write(f'Welcome *{st.session_state["name"]}*')
elif st.session_state["authentication_status"] is False:
    reset_btn = False
    st.error("Username/password is incorrect")
elif st.session_state["authentication_status"] is None:
    reset_btn = False
    st.warning("Please enter your username and password")


def reset_password():
    try:
        if authenticator.reset_password(st.session_state["username"]):
            save_config(config=config)
            st.success("Password modified successfully")
    except Exception as e:
        st.error(e)


def register_new_user():
    try:
        (
            email_of_registered_user,
            _,
            name_of_registered_user,
        ) = authenticator.register_user(pre_authorization=False)
        if email_of_registered_user:
            save_config(config=config)
            st.success(f"User {name_of_registered_user} registered successfully")

    except Exception as e:
        st.error(e)


# Reset password
reset_password_modal = Modal("Reset Password", key="reset-password-modal")
if reset_btn:
    reset_password_modal.open()
if reset_password_modal.is_open():
    with reset_password_modal.container():
        st.write("Please enter the details below")
        reset_password()
        st.cache_data.clear()
        config = load_config_()
        time.sleep(2)

# Register new
if st.session_state["authentication_status"]:
    register_btn = False
else:
    st.markdown("**Add a new user by clicking the button below:**")
    register_btn = st.button("Register New User")
register_modal = Modal("Register New User", key="register-new-user-modal")
if register_btn:
    register_modal.open()
if register_modal.is_open():
    with register_modal.container():
        st.write("Please enter the details below")
        register_new_user()
        st.cache_data.clear()
        config = load_config_()
        time.sleep(2)


def color_rules(val):
    if isinstance(val, (float, int)):
        color = "#fa7069" if val < 0 else "#8ced79"
        return f"color: {color}"  # to adapt. background color could be managed too
    elif isinstance(val, (pd.Timestamp, str)):
        return "color: orange"  # to adapt. background color could be managed too
    else:
        return "color: grey"


def display_filtered(df, filter):
    date_columns = df.columns[df.columns.str.contains("date", case=False)]
    if filter:
        columns = df.filter(like=filter).columns
    else:
        columns = df.columns
    df = df[date_columns.tolist() + columns.tolist()]

    df.columns = df.columns.str.replace(filter, "", regex=False)
    all_columns = df.columns
    column_config = {
        col: st.column_config.NumberColumn(col, format="%.4f", width=90, help=col)
        for col in all_columns
        if col not in date_columns
    }
    make_plot = st.checkbox("Plot", key=f"make_plot_{filter}")
    if not make_plot:
        st.dataframe(
            df.style.map(color_rules),
            column_config=column_config,
        )
        return
    # st.line_chart(df)
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    fig = make_subplots(rows=1, cols=1, shared_xaxes=True)

    for col in all_columns:
        if col in date_columns:
            continue
        fig.add_trace(
            go.Scatter(x=df.index, y=df[col], mode="lines", name=col), row=1, col=1
        )

    filter = "PnL %" if "%" in filter else "PnL"
    fig.update_layout(
        title_text=filter,
        xaxis_title=df.index.name,
        yaxis_title=filter,
    )
    st.plotly_chart(fig)


def plot_all(pnl, holding=None, names_scheme_mapping=None, pnl_all=None):
    if holding is None:
        (
            summary_tab,
            scheme_level_absolute_summary_tab,
            scheme_level_relative_summary_tab,
            pnl_tab,
            total_investment_tab,
        ) = st.tabs(
            [
                "Summary",
                "Scheme Level Absolute Summary",
                "Scheme Level Relative Summary",
                "PnL",
                "Total Investment",
            ]
        )
    else:
        (
            summary_tab,
            pnl_tab,
            total_investment_tab,
        ) = st.tabs(
            [
                "Summary",
                "PnL",
                "Total Investment",
            ]
        )
        scheme_level_absolute_summary_tab = None
        scheme_level_relative_summary_tab = None

    logger.info("Plotting")

    with summary_tab:
        st.write("Summary")
        extra_deltas = st.multiselect(
            "Select Extra Deltas in Days. This will be added to the summary",
            options=list(range(4, 700, 1)),
            key="summary_tab",
        )
        try:
            summary_df = create_summary(pnl=pnl, extra_deltas=extra_deltas)
            st.dataframe(summary_df.style.applymap(color_rules))
        except Exception as e:
            st.error(f"Error in creating summary: {e}")

    if scheme_level_absolute_summary_tab is not None:
        with scheme_level_absolute_summary_tab:
            columns = st.columns([1, 1])
            with columns[0]:
                num_days = st.slider(
                    "Number of Days to look back for the scheme level summary",
                    min_value=1,
                    max_value=15,
                    value=3,
                    step=1,
                )
            with columns[1]:
                column_to_view = st.selectbox(
                    "Select the column to view",
                    [
                        "Percentage PnL",
                        "PnL",
                    ],
                    key="scheme_level_absolute_summary",
                )

            pnl_summary_scheme_level = create_scheme_level_absolute_pnl_summary(
                pnl_all, names_scheme_mapping, num_days
            )
            if column_to_view == "PnL":
                column_to_view = "Pnl_"
            else:
                column_to_view = "Pnl%_"
            pnl_summary_scheme_level = pnl_summary_scheme_level.filter(
                like=column_to_view
            )
            display_filtered(pnl_summary_scheme_level, column_to_view)

    if scheme_level_relative_summary_tab is not None:
        with scheme_level_relative_summary_tab:
            columns = st.columns([1, 1])
            with columns[0]:
                extra_deltas = st.multiselect(
                    "Select Extra Deltas in Days. This will be added to the summary",
                    options=list(range(4, 700, 1)),
                    key="scheme_level_relative_summary_delta",
                )
            with columns[1]:
                column_to_view = st.selectbox(
                    "Select the column to view",
                    [
                        "Percentage Change in PnL",
                        "Change in PnL",
                    ],
                    key="scheme_level_relative_summary_columns",
                )

            if column_to_view == "Change in PnL":
                column_to_view = "change_in_pnl_"
            else:
                column_to_view = "change_in_pnl%_"

            summary_df = create_scheme_level_relative_pnl_summary(
                pnl=pnl_all,
                extra_deltas=extra_deltas,
                names_scheme_mapping=names_scheme_mapping,
            )
            display_filtered(summary_df, column_to_view)

    def create_figure_element_with_resample(func_to_use, **kwargs):
        resample_frequency = st.selectbox(
            "Select a Resample Frequency. If None, no resampling will be done.",
            [None, "W", "M", "Y"],
            index=0,
            key=func_to_use.__name__,
        )
        fig = func_to_use(resample_frequency=resample_frequency, **kwargs)
        with st.container():
            st.plotly_chart(fig)

    if holding is None:
        transaction_dates = portfolio.transaction_dates
    else:
        transaction_dates = holding.transaction_dates

    with pnl_tab:
        create_figure_element_with_resample(
            plot_pnl_and_pnl_percentage, df=pnl, transaction_dates=transaction_dates
        )

    with total_investment_tab:
        create_figure_element_with_resample(
            plot_total_investment_and_current_value,
            df=pnl,
            transaction_dates=transaction_dates,
        )


no_transaction = True
try:
    if username is None:
        st.stop()
    date = datetime.today().strftime("%Y-%m-%d")
    pnl, portfolio = create_portfolio(username, date)
    pnl_all = portfolio.pnl.copy()
    pnl = pnl.copy()
    no_transaction = False
except NoTransactions as e:
    error_text = f"User {username} does not have any transactions. Upload the transaction data using the Update Transactions"
    st.error(error_text)

# add a refresh button
refresh_btn = st.sidebar.button("Refresh Data", key="refresh_data")
if refresh_btn and not no_transaction:
    # create a random date
    month = np.random.randint(1, 12)
    day = np.random.randint(1, 28)
    year = np.random.randint(2010, 2024)
    date = datetime(year, month, day).strftime("%Y-%m-%d")
    pnl, portfolio = create_portfolio(username, date)
    pnl_all = portfolio.pnl.copy()
    pnl = pnl.copy()

update_transactions_btn = st.sidebar.button(
    "Update Transactions", key="update_transactions"
)
modal = Modal("Update Transactions", key="update_transactions_modal")

if update_transactions_btn:
    modal.open()

if modal.is_open():
    with modal.container():
        st.markdown(
            "Upload a file with the following columns: date, scheme_code, amount, units, nav, type. The file can be downloaded from Zerodha by following the [link](https://console.zerodha.com/reports/tradebook).",
            unsafe_allow_html=True,
        )
        file_picker = st.file_uploader("Upload a file", type=["csv", "xlsx"])

        if file_picker is not None:
            logger.info("Updating Transactions")
            try:
                update_transactions(file_picker, username, debug=False)
                st.success(
                    "Transactions Updated Successfully. Data will be refreshed automatically"
                )

                time.sleep(2)
                # close the modal
                modal.close()
            except Exception as e:
                st.error(f"Error in updating transactions: {e}")

if no_transaction:
    st.stop()
# create a container with half height
container = st.container(border=False)
with container:
    rows1 = st.columns(1)
    with rows1[0]:
        overall_pnl = int(pnl.iloc[-1]["pnl"])
        overall_pnl_percentage = round(pnl.iloc[-1]["pnl_percentage"], 2)
        total_invested = pnl.iloc[-1]["total_invested"]
        current_value = pnl.iloc[-1]["current_value"]
        overall_pnl_color = "#fa7069" if overall_pnl < 0 else "#8ced79"
        overall_pnl_percentage_color = (
            "#fa7069" if overall_pnl_percentage < 0 else "#8ced79"
        )
        st.markdown(
            f"""
            <h4 style="color:{overall_pnl_color}">₹{overall_pnl} &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;{overall_pnl_percentage}%</h4>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <h6 style="color:grey">Total Invested: ₹{int(total_invested)}</h6>
            <h6 style="color:grey"> Current Value: ₹{int(current_value)}</h6>
            """,
            unsafe_allow_html=True,
        )


names_scheme_mapping, schemes_names_mapping = get_all_holdings_(pnl_all)
names = list(names_scheme_mapping.values())
names = ["Portfolio"] + names
latest_date = pnl["date"].max().strftime("%Y-%m-%d")

with st.sidebar:
    st.markdown(
        f"""
        Data Available Till *{latest_date}*
        """
    )

sidebars = st.sidebar.selectbox(
    "Select A Mutual Fund or the Entire Portfolio",
    names,
)

with st.sidebar:
    if sidebars != "Portfolio":
        scheme_code = schemes_names_mapping[sidebars]
        pnl_to_use = pnl_all[pnl_all["scheme_code"] == scheme_code]
        holding = list(
            filter(lambda x: x.scheme_code == scheme_code, portfolio.holdings)
        )[0]
    else:
        pnl_to_use = pnl
        holding = None

plot_all(pnl_to_use, holding, names_scheme_mapping, pnl_all)
