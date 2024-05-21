from typing import List, Dict
from collections import OrderedDict
import pandas as pd
from pymongo import MongoClient
from urllib.parse import quote_plus
import env as env
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

# set plotly theme
pio.templates.default = "plotly_dark"
# set font
pio.templates[pio.templates.default].layout["font"]["family"] = "Roboto"
pio.templates[pio.templates.default].layout["font"]["size"] = 12


from mutual_funds import get_simple_logger

logger = get_simple_logger("plots_and_summary")


class NoTranscation(Exception):
    pass


def get_mongo_client():
    string = f"mongodb+srv://{env.MONGO_USER}:{env.MONGO_PASSWORD}@{env.MONGO_HOST}/funds?retryWrites=true&w=majority"
    string = string.replace(env.MONGO_USER, quote_plus(env.MONGO_USER))
    string = string.replace(env.MONGO_PASSWORD, quote_plus(env.MONGO_PASSWORD))
    client = MongoClient(string)
    return client


def load_config():
    client = get_mongo_client()
    db = client["funds"]
    collection = db["users"]
    config = collection.find_one()
    if not config:
        raise Exception("No config found")
    logger.info("Config loaded")
    return config


def save_config(config):
    client = get_mongo_client()
    db = client["funds"]
    collection = db["users"]
    collection.update_one({}, {"$set": config})
    logger.info("Config saved")


def get_transcations(client, username):
    db = client["funds"]
    transcations = db["transactions"]
    transcations = transcations.find_one({"username": username})
    if not transcations:
        raise NoTranscation(f"No transcations found for {username}")
    return transcations["transactions"]


def create_mapping():
    client = get_mongo_client()
    db = client["funds"]
    mapping_c = db["mappings"]
    mapping = mapping_c.find_one()["isin_to_scheme_code"]
    return mapping


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


def create_scheme_level_summary(pnl_all, names_scheme_mapping, num_days=3):
    pnl_all["date"] = pd.to_datetime(pnl_all["date"])
    dates = pnl_all["date"].unique()
    dates = sorted(dates)
    # select maximum three dates
    dates_to_take = dates[-num_days:]

    pnl_summary = pnl_all[pnl_all["date"].isin(dates_to_take)]
    pnl_summary["scheme_name"] = pnl_summary["scheme_code"].replace(
        names_scheme_mapping
    )
    pnl_summary = pnl_summary.sort_index(ascending=False)

    pnl_summary_pivot = (
        pnl_summary.pivot(
            index="scheme_name", columns="date", values=["pnl", "pnl_percentage"]
        )
        .fillna(0)
        .reset_index()
    )
    pnl_summary_pivot.columns = ["scheme"] + [
        f"{col[0]}_{col[1].date()}" for col in pnl_summary_pivot.columns[1:]
    ]
    pnl_summary_pivot = pnl_summary_pivot.T.sort_index(ascending=False).T
    pnl_summary_pivot = pnl_summary_pivot.sort_values(
        by=pnl_summary_pivot.columns[1], ascending=False
    )
    float_columns = pnl_summary_pivot.columns[1 : len(dates_to_take) + 1]
    int_columns = pnl_summary_pivot.columns[len(dates_to_take) + 1 :]
    pnl_summary_pivot[int_columns] = pnl_summary_pivot[int_columns].astype(int)
    pnl_summary_pivot[float_columns] = pnl_summary_pivot[float_columns].round(2)
    og_columns = pnl_summary_pivot.columns
    new_columns = [col.title() for col in og_columns]
    rename_map = dict(zip(og_columns, new_columns))
    pnl_summary_pivot = pnl_summary_pivot.rename(columns=rename_map).T

    pnl_summary_pivot.columns = pnl_summary_pivot.iloc[0]
    pnl_summary_pivot = pnl_summary_pivot[1:]

    return pnl_summary_pivot


label_map = {
    "pnl": "PnL",
    "pnl_percentage": "PnL %",
    "total_invested": "Total Investment",
    "current_value": "Current Value",
}


def plot_single_column_with_date(
    df: pd.DataFrame,
    transaction_dates: Dict[str, List[str]],
    column_name: str,
    title: str,
    add_transcations: bool = True,
    resample_frequency: str = None,
):
    """Plot a single column with date on the x-axis

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to plot. Must have a column named "date"
    transaction_dates : dict
        A dictionary containing the purchase_dates and sell_dates
    column_name : str
        The column to plot
    title : str
        The title of the plot
    add_transcations : bool, optional
        Whether to add the purchase and sell dates as dots on the plot, by default True
    resample_frequency : str, optional
        The frequency to resample the data to, by default None. If None, the data is not resampled

    Returns
    -------
    go.Figure
        A plotly figure
    """
    yaxis_label = label_map[column_name]
    if resample_frequency:
        df = df.copy()
        df = df.set_index("date")
        df = df.asfreq(resample_frequency, method="ffill")
        df["date"] = df.index

    # create a plotly figure
    fig = go.Figure()
    # add a line to the plot
    fig.add_trace(
        go.Scatter(x=df["date"], y=df[column_name], mode="lines", name=yaxis_label)
    )
    # set the title
    fig.update_layout(title=title)
    # set the x-axis label
    fig.update_xaxes(title_text="Date")
    # set the y-axis label
    fig.update_yaxes(title_text=yaxis_label)
    if not add_transcations or resample_frequency:
        return fig

    purchase_dates = transaction_dates["purchase_dates"]
    sell_dates = transaction_dates["sell_dates"]
    purchase_dates_value = df[df["date"].isin(purchase_dates)][
        column_name
    ].drop_duplicates()
    sell_dates_value = df[df["date"].isin(sell_dates)][column_name].drop_duplicates()

    # add the purchase_dates as green dots
    fig.add_trace(
        go.Scatter(
            x=purchase_dates,
            y=purchase_dates_value,
            mode="markers",
            marker=dict(color="green", size=10),
            name="Purchase",
        )
    )

    # add the sell_dates as red dots
    fig.add_trace(
        go.Scatter(
            x=sell_dates,
            y=sell_dates_value,
            mode="markers",
            marker=dict(color="red", size=10),
            name="Sell",
        )
    )

    return fig


def plot_two_columns_with_date(
    df: pd.DataFrame,
    transaction_dates: Dict[str, List[str]],
    column_name1: str,
    column_name2: str,
    title: str,
    add_transcations: bool = True,
    resample_frequency: str = None,
):
    """Plot two columns with date on the x-axis

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to plot. Must have a column named "date"
    transaction_dates : dict
        A dictionary containing the purchase_dates and sell_dates
    column_name1 : str
        The first column to plot
    column_name2 : str
        The second column to plot
    title : str
        The title of the plot
    add_transcations : bool, optional
        Whether to add the purchase and sell dates as dots on the plot, by default True
    resample_frequency : str, optional
        The frequency to resample the data to, by default None. If None, the data is not resampled

    Returns
    -------
    go.Figure
        A plotly figure
    """
    yaxis_label1 = label_map[column_name1]
    yaxis_label2 = label_map[column_name2]

    if resample_frequency:
        df = df.copy()
        df = df.set_index("date")
        df = df.asfreq(resample_frequency, method="ffill")
        df["date"] = df.index
    # create a plotly figure
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    # add a line to the plot
    fig.add_trace(
        go.Scatter(x=df["date"], y=df[column_name1], mode="lines", name=yaxis_label1),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df["date"], y=df[column_name2], mode="lines", name=yaxis_label2),
        secondary_y=True,
    )
    # set the title
    fig.update_layout(title=title)
    # set the x-axis label
    fig.update_xaxes(title_text="Date")
    # set the y-axis label
    fig.update_yaxes(title_text=yaxis_label1, secondary_y=False)
    fig.update_yaxes(title_text=yaxis_label2, secondary_y=True)
    if not add_transcations:
        return fig

    purchase_dates = transaction_dates["purchase_dates"]
    sell_dates = transaction_dates["sell_dates"]
    purchase_dates_value1 = df[df["date"].isin(purchase_dates)][
        column_name1
    ].drop_duplicates()
    purchase_dates_value2 = df[df["date"].isin(purchase_dates)][
        column_name2
    ].drop_duplicates()
    sell_dates_value1 = df[df["date"].isin(sell_dates)][column_name1].drop_duplicates()
    sell_dates_value2 = df[df["date"].isin(sell_dates)][column_name2].drop_duplicates()

    # add the purchase_dates as green dots
    fig.add_trace(
        go.Scatter(
            x=purchase_dates,
            y=purchase_dates_value1,
            mode="markers",
            marker=dict(color="green", size=8),
            name="Purchase",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=purchase_dates,
            y=purchase_dates_value2,
            mode="markers",
            marker=dict(color="green", size=8),
            name="Purchase",
        ),
        secondary_y=True,
    )

    # add the sell_dates as red dots
    fig.add_trace(
        go.Scatter(
            x=sell_dates,
            y=sell_dates_value1,
            mode="markers",
            marker=dict(color="red", size=8),
            name="Sell",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sell_dates,
            y=sell_dates_value2,
            mode="markers",
            marker=dict(color="red", size=8),
            name="Sell",
        ),
        secondary_y=True,
    )
    return fig


def plot_pnl(
    df,
    transaction_dates,
    holding_name=None,
    resample_frequency=None,
):
    """Plots the PnL for a holding/portfolio"""
    if holding_name:
        title = f"PnL for {holding_name}"
    else:
        title = "PnL"

    return plot_single_column_with_date(
        df, transaction_dates, "pnl", title, resample_frequency=resample_frequency
    )


def plot_pnl_percentage(
    df,
    transaction_dates,
    holding_name=None,
    resample_frequency=None,
):
    """Plots the PnL % for a holding/portfolio"""
    if holding_name:
        title = f"PnL % for {holding_name}"
    else:
        title = "PnL %"

    return plot_single_column_with_date(
        df,
        transaction_dates,
        "pnl_percentage",
        title,
        resample_frequency=resample_frequency,
    )


def plot_total_investment(
    df,
    transaction_dates,
    holding_name=None,
    resample_frequency=None,
):
    """Plots the total investment for a holding/portfolio"""
    if holding_name:
        title = f"Total Investment for {holding_name}"
    else:
        title = "Total Investment"

    return plot_single_column_with_date(
        df,
        transaction_dates,
        "total_invested",
        title,
        resample_frequency=resample_frequency,
    )


def plot_current_value(
    df,
    transaction_dates,
    holding_name=None,
    resample_frequency=None,
):
    """Plots the current value for a holding/portfolio"""
    if holding_name:
        title = f"Current Value for {holding_name}"
    else:
        title = "Current Value"

    return plot_single_column_with_date(
        df,
        transaction_dates,
        "current_value",
        title,
        resample_frequency=resample_frequency,
    )


def plot_total_investment_and_current_value(
    df,
    transaction_dates,
    holding_name=None,
    resample_frequency=None,
):
    """Plots the total investment and current value for a holding/portfolio on the same plot"""
    if holding_name:
        title = f"Total Investment and Current Value for {holding_name}"
    else:
        title = "Total Investment and Current Value"

    return plot_two_columns_with_date(
        df,
        transaction_dates,
        "total_invested",
        "current_value",
        title,
        resample_frequency=resample_frequency,
    )


def plot_pnl_and_pnl_percentage(
    df,
    transaction_dates,
    holding_name=None,
    resample_frequency=None,
):
    """Plots the PnL and PnL % for a holding/portfolio on the same plot"""
    if holding_name:
        title = f"PnL and PnL % for {holding_name}"
    else:
        title = "PnL and PnL %"

    return plot_two_columns_with_date(
        df,
        transaction_dates,
        "pnl",
        "pnl_percentage",
        title,
        resample_frequency=resample_frequency,
    )


def _get_latest_date(all_pnl_date, date_to_match):
    for date in all_pnl_date:
        if date >= date_to_match:
            return date
    return date_to_match


def create_summary(pnl, extra_deltas=None, extra_names=None):
    last_date = pnl["date"].max()
    all_pnl_dates = pnl["date"]
    last1d = last_date - pd.Timedelta(days=1)
    last2d = last_date - pd.Timedelta(days=2)
    last3d = last_date - pd.Timedelta(days=3)
    last_week = last_date - pd.Timedelta(days=7)
    last_15_days = last_date - pd.Timedelta(days=15)
    last_month = last_date - pd.Timedelta(days=30)

    dates_to_use = [
        last_date,
        last1d,
        last2d,
        last3d,
        last_week,
        last_15_days,
        last_month,
    ]
    if extra_deltas:
        dates_to_use.extend([last_date - pd.Timedelta(days=i) for i in extra_deltas])

    dates_matched = [_get_latest_date(all_pnl_dates, date) for date in dates_to_use]
    summary_df = pnl[pnl["date"].isin(dates_matched)]
    summary_df = summary_df.sort_values("date", ascending=False)

    total_investments = summary_df["total_invested"].values.tolist()
    current_values = summary_df["current_value"].values.tolist()
    pnl_ = summary_df["pnl"].values
    final_pnl = pnl_[0]
    pnl_change = final_pnl - pnl_
    date_names = ["T", "T-1", "T-2", "T-3", "Last Week", "Last 15 Days", "Last Month"]

    if extra_names:
        date_names += extra_names
    if len(dates_to_use) != len(date_names):
        new_names_to_add = len(dates_to_use) - len(date_names)
        date_names += [f"Last {extra_deltas[i]} Days" for i in range(new_names_to_add)]

    summary_dict = {
        "date": date_names,
        "total_investments": total_investments,
        "current_values": current_values,
        "pnl_change_relative": pnl_change,
    }
    summary_df = pd.DataFrame(summary_dict)
    summary_df["pnl"] = summary_df["current_values"] - summary_df["total_investments"]
    summary_df["pnl_percentage"] = (
        summary_df["pnl"] / summary_df["total_investments"]
    ) * 100
    summary_df["pnl_change_relative_percentage"] = (
        summary_df["pnl_change_relative"] / summary_df["total_investments"].iloc[0]
    ) * 100

    int_columns = ["total_investments", "current_values", "pnl", "pnl_change_relative"]
    summary_df[int_columns] = summary_df[int_columns].astype(int)
    float_columns = ["pnl_percentage", "pnl_change_relative_percentage"]
    summary_df[float_columns] = summary_df[float_columns].round(2)
    rename_map = {
        "date": "Time Period",
        "total_investments": "Total Investment",
        "current_values": "Current Value",
        "pnl": "PnL",
        "pnl_percentage": "PnL %",
        "pnl_change_relative": "PnL Change",
        "pnl_change_relative_percentage": "PnL Change %",
    }
    summary_df = summary_df.rename(columns=rename_map)
    return summary_df
