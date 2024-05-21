import streamlit as st
import streamlit_authenticator as stauth
import env as env
import time
from collections import OrderedDict

from mutual_funds import Portfolio
from plots_and_summary import *

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
def create_portfolio(username):
    client = get_mongo_client()
    transactions = get_transcations(client, username)

    portfolio = Portfolio(transcations=transactions)
    pnl = portfolio.get_pnl_timeseries()
    return pnl, portfolio


config = load_config()
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
    authenticator.logout()
    st.write(f'Welcome *{st.session_state["name"]}*')

elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password")


def plot_all(pnl, holding=None):
    (
        summary_tab,
        pnl_tab,
        # pnl_percentage_tab,
        total_investment_tab,
        # current_value_tab,
    ) = st.tabs(
        [
            "Summary",
            "PnL",
            # "PnL Percentage",
            "Total Investment",
            # "Current Value",
        ]
    )
    logger.info("Plotting")

    with summary_tab:
        st.write("Summary")
        extra_deltas = st.multiselect(
            "Select Extra Deltas in Days. This will be added to the summary",
            options=list(range(35, 700, 5)),
        )
        summary_df = create_summary(pnl=pnl, extra_deltas=extra_deltas)
        st.dataframe(summary_df)

    def create_figure_element_with_resample(func_to_use, **kwargs):
        resample_frequency = st.selectbox(
            "Select a Resample Frequency. If None, no resampling will be done.",
            [None, "W", "M", "Y"],
            index=0,
            key=func_to_use.__name__,
        )
        fig = func_to_use(resample_frequency=resample_frequency, **kwargs)
        with st.container():
            # center the plot
            st.plotly_chart(fig)

    if holding is None:
        transaction_dates = portfolio.transaction_dates
    else:
        transaction_dates = holding.transaction_dates

    with pnl_tab:
        create_figure_element_with_resample(
            plot_pnl_and_pnl_percentage, df=pnl, transaction_dates=transaction_dates
        )

    # with pnl_percentage_tab:
    #     create_figure_element_with_resample(
    #         plot_pnl_percentage, df=pnl, transaction_dates=transaction_dates
    #     )

    with total_investment_tab:
        create_figure_element_with_resample(
            plot_total_investment_and_current_value,
            df=pnl,
            transaction_dates=transaction_dates,
        )

    # with current_value_tab:
    #     create_figure_element_with_resample(
    #         plot_current_value, df=pnl, transaction_dates=transaction_dates
    #     )


def get_all_holdings(pnl_all):
    mapping = create_mapping()
    schemes = pnl_all["scheme_code"].unique().tolist()
    names = []
    for scheme in schemes:
        matched = list(filter(lambda x: x["scheme_code"] == scheme, mapping))
        if matched:
            names.append(matched[0]["symbol"])
        else:
            names.append("Unknown")

    names_scheme_mapping = OrderedDict(zip(schemes, names))
    schemes_names_mapping = OrderedDict(zip(names, schemes))
    return names_scheme_mapping, schemes_names_mapping


try:
    if username is None:
        st.stop()
    pnl, portfolio = create_portfolio(username)
    pnl_all = portfolio.pnl
except NoTranscation as e:
    error_text = f"User {username} does not have any transcations"
    st.error(error_text)
    st.stop()

names_scheme_mapping, schemes_names_mapping = get_all_holdings(pnl_all)
names = list(names_scheme_mapping.values())
names = ["Portfolio"] + names

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

plot_all(pnl_to_use, holding)
