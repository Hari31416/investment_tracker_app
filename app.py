import streamlit as st
from streamlit_modal import Modal
import streamlit_authenticator as stauth
import env as env
from datetime import datetime

from mutual_funds import Portfolio
from plots_and_summary import *

import matplotlib

cmap = matplotlib.colormaps["RdYlGn"]

logger = get_simple_logger("app")
st.set_page_config(
    layout="wide",
    page_title="Mutual Fund Portfolio Analysis",
    page_icon="🧊",
    initial_sidebar_state="expanded",
)
# center the page
st.markdown(
    """
    <style>
    body {
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Mutual Fund Portfolio Analysis")


@st.cache_data
def create_portfolio(username, date):
    client = get_mongo_client()
    transactions = get_transcations(client, username)

    portfolio = Portfolio(transcations=transactions)
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
    st.write(f'Welcome *{st.session_state["name"]}*')

elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password")

# columns = st.columns([1, 1, 1])
# # create a register user button on top right
# register_user_btn = columns[2].button("Register User")


# if register_user_btn:
#     modal = Modal(key="register_user", title="Register User")
#     with modal.container():
#         try:
#             (
#                 email_of_registered_user,
#                 username_of_registered_user,
#                 name_of_registered_user,
#             ) = authenticator.register_user(pre_authorization=False)
#             if email_of_registered_user:
#                 st.success("User registered successfully")
#                 save_config(config)

#         except Exception as e:
#             st.error(e)


def plot_all(pnl, holding=None, names_scheme_mapping=None, pnl_all=None):
    if holding is None:
        (
            summary_tab,
            scheme_level_summary_tab,
            pnl_tab,
            total_investment_tab,
        ) = st.tabs(
            [
                "Summary",
                "Scheme Level Summary",
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
        scheme_level_summary_tab = None

    logger.info("Plotting")

    with summary_tab:
        st.write("Summary")
        extra_deltas = st.multiselect(
            "Select Extra Deltas in Days. This will be added to the summary",
            options=list(range(4, 700, 1)),
        )
        try:
            summary_df = create_summary(pnl=pnl, extra_deltas=extra_deltas)
            st.dataframe(summary_df.style.background_gradient(cmap=cmap, axis=0))
        except Exception as e:
            st.error(f"Error in creating summary: {e}")

    if scheme_level_summary_tab is not None:
        with scheme_level_summary_tab:
            num_days = st.slider(
                "Number of Days to look back for the scheme level summary",
                min_value=1,
                max_value=15,
                value=3,
                step=1,
            )
            st.write("Scheme Level Summary")
            pnl_summary_scheme_level = create_scheme_level_summary(
                pnl_all, names_scheme_mapping, num_days
            )
            st.dataframe(
                pnl_summary_scheme_level.style.background_gradient(cmap=cmap, axis=0)
            )

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


try:
    if username is None:
        st.stop()
    date = datetime.today().strftime("%Y-%m-%d")
    pnl, portfolio = create_portfolio(username, date)
    pnl_all = portfolio.pnl.copy()
    pnl = pnl.copy()
except NoTranscation as e:
    error_text = f"User {username} does not have any transcations"
    st.error(error_text)
    st.stop()

names_scheme_mapping, schemes_names_mapping = get_all_holdings_(pnl_all)
names = list(names_scheme_mapping.values())
names = ["Portfolio"] + names
latest_date = pnl["date"].max().strftime("%Y-%m-%d")
st.markdown(
    f"""
    #### Data Available Till {latest_date}
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
