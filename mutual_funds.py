import pandas as pd
from typing import List, Dict, Union
from datetime import datetime
import numpy as np
import requests
import logging


def get_simple_logger(name, level="info"):
    """Creates a simple loger that outputs to stdout"""
    level_to_int_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    if isinstance(level, str):
        level = level_to_int_map[level.lower()]
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if logger.hasHandlers():
        logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class Trasaction:
    """A transaction is a single transaction in a mutual fund. It can be a purchase or a sell transaction.

    Attributes
    ----------
    date: str
        The date of the transaction
    units: float
        The number of units in the transaction
    average_nav: float
        The average nav of the transaction
    transaction_type: str
        The type of transaction. Can be either purchase or sell. The base class does not have a transaction type. The subclasses `Purchase` and `Sell` have the transaction type.
    """

    def __init__(
        self,
        date: str,
        units: float,
        average_nav: float,
        logger: Union[str, datetime] = None,
    ) -> float:

        self.date_ = datetime.strptime(date, "%Y-%m-%d")
        self.date = self.date_.strftime("%Y-%m-%d")
        self.units = units
        self.average_nav = average_nav
        self.transaction_type = None
        self.logger = logger or get_simple_logger(self.__class__.__name__)

    def __str__(self) -> str:
        start = (
            self.transaction_type.title() if self.transaction_type else "Transaction"
        )
        return (
            f"{start} on {self.date} for {self.units} units at {self.average_nav} NAV"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def pnl(self, new_nav: float, percentage: bool = False):
        val = self.units * (new_nav - self.average_nav)
        if percentage:
            return val / self.average_nav * 100
        return val

    @property
    def nav_with_sign(self) -> float:
        if self.transaction_type is None:
            return self.average_nav

        if self.transaction_type == "purchase":
            self.logger.debug(f"Purchase nav {self.average_nav}")
            return self.average_nav
        self.logger.debug(f"Sell nav {self.average_nav}")
        return -self.average_nav

    @property
    def units_with_sign(self) -> float:
        if self.transaction_type is None:
            return self.units

        if self.transaction_type == "purchase":
            self.logger.debug(f"Purchase units {self.units}")
            return self.units
        self.logger.debug(f"Sell units {self.units}")
        return -self.units


class Purchase(Trasaction):
    """A purchase transaction in a mutual fund. Inherits from `Transaction` class."""

    def __init__(self, date: str, units: float, average_nav: float, logger=None):
        super().__init__(date, units, average_nav)
        self.logger = logger or get_simple_logger(self.__class__.__name__)
        self.transaction_type = "purchase"


class Sell(Trasaction):
    """A sell transaction in a mutual fund. Inherits from `Transaction` class."""

    def __init__(self, date: str, units: float, average_nav: float, logger=None):
        super().__init__(date, units, average_nav)
        self.logger = logger or get_simple_logger(self.__class__.__name__)
        self.transaction_type = "sell"


class TrasactionHistory:
    def __init__(self, logger: Union[str, datetime] = None) -> float:
        self.transaction_history_og: List[Trasaction] = []
        self.max_date = None
        self.logger = logger or get_simple_logger(self.__class__.__name__)

    def __str__(self) -> str:
        num_transcations = len(self.transaction_history)
        return f"Transaction history with {num_transcations} transactions"

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self):
        return len(self.transaction_history)

    def __getitem__(self, key):
        return self.transaction_history[key]

    def __add__(self, other):
        new = self.__class__()
        new.transaction_history_og = (
            self.transaction_history_og + other.transaction_history_og
        )
        return new

    def add_transaction(
        self, date: str, units: float, average_nav: float, transaction_type: str
    ):
        """Adds a transaction to the transaction history"""
        if transaction_type == "purchase":
            self.logger.debug(f"Adding purchase transaction")
            transaction = Purchase(date, units, average_nav)
        elif transaction_type == "sell":
            self.logger.debug(f"Adding sell transaction")
            transaction = Sell(date, units, average_nav)
        else:
            raise ValueError(
                "Invalid transaction type. Must be either purchase or sell."
            )
        self.transaction_history.append(transaction)

    @property
    def transaction_history(self) -> List[Trasaction]:
        """Filters the transaction history based on the max_date attribute and returns the filtered transactions. If max_date is None, returns the original transaction history. This is necessary to calculate the correct values of various metrics used in the class."""
        if self.max_date is None:
            return self.transaction_history_og

        if isinstance(self.max_date, str):
            self.max_date = datetime.strptime(self.max_date, "%Y-%m-%d")

        t = [x for x in self.transaction_history_og if x.date_ <= self.max_date]
        self.logger.debug(f"{len(t)} transcations filtered for date: {self.max_date}")
        return t

    @property
    def unit_array(self) -> np.ndarray:
        """Get the units of all transactions in the transaction history as a numpy array."""
        units_list = [x.units for x in self.transaction_history]
        return np.array(units_list)

    @property
    def units_array_with_sign(self) -> np.ndarray:
        """Get the units of all transactions in the transaction history as a numpy array with sign. Sold transactions have negative units."""
        units_list = [x.units_with_sign for x in self.transaction_history]
        return np.array(units_list)

    @property
    def nav_array(self) -> np.ndarray:
        """Get the nav of all transactions in the transaction history as a numpy array."""
        nav_list = [x.nav for x in self.transaction_history]
        return np.array(nav_list)

    @property
    def nav_array_with_sign(self) -> np.ndarray:
        """Get the nav of all transactions in the transaction history as a numpy array with sign. Sold transactions have negative nav."""
        nav_list = [x.nav_with_sign for x in self.transaction_history]
        return np.array(nav_list)

    def total_units(self, max_date: Union[str, datetime] = None) -> float:
        """Calculate the total units in the transaction history. If max_date is provided, the transactions after the max_date are not considered."""
        self.max_date = max_date
        return np.sum(self.units_array_with_sign)

    def average_nav(self, max_date: Union[str, datetime] = None) -> float:
        """Calculate the average nav of the transaction history. If max_date is provided, the transactions after the max_date are not considered."""
        self.max_date = max_date
        units = self.unit_array
        units_sign = self.units_array_with_sign
        nav = self.nav_array_with_sign  # sold transactions have negative nav
        units_sum = np.sum(units_sign)  # remove the sold units
        if units_sum == 0:
            self.logger.info("No units in the transaction history. Returning 0.0")
            return 0
        return np.sum(units * nav) / units_sum

    def transactions_pnl(
        self,
        current_nav: float,
        percentage: bool = False,
        max_date: Union[str, datetime] = None,
    ):
        """Calculate the total pnl of the transaction history. If max_date is provided, the transactions after the max_date are not considered. If percentage is True, returns the pnl as a percentage of the invested amount."""
        self.max_date = max_date
        invested = np.sum(self.unit_array * self.nav_array_with_sign)
        current = np.sum(self.units_array_with_sign) * current_nav
        pnl = current - invested
        if percentage:
            return pnl / invested * 100
        return pnl

    def net_transaction_value(self, max_date: Union[str, datetime] = None) -> float:
        """Calculate the total invested amount in the transaction history. If max_date is provided, the transactions after the max_date are not considered."""
        self.max_date = max_date
        if self.nav_array_with_sign.sum() == 0:
            self.logger.info(
                "No transactions in the transaction history. Returning 0 for invested amount."
            )
            return 0

        return np.sum(self.unit_array * self.nav_array_with_sign)

    def sort_transactions(self, reverse: bool = True):
        """Sort the transactions in the transaction history based on the date. If reverse is True, sorts in descending order."""
        self.transaction_history_og = sorted(
            self.transaction_history_og, key=lambda x: x.date_, reverse=reverse
        )

    def create_transcations_from_dict(self, transactions: List[Dict]):
        """Create transactions from a list of dictionaries containing transaction details. Assumes that the dictionary contains keys `date`, `units`, `average_nav` and `transaction_type`."""
        keys_to_match = ["date", "units", "average_nav", "transaction_type"]
        for transaction in transactions:
            if not all([x in transaction for x in keys_to_match]):
                raise ValueError(
                    f"Transaction dictionary must contain keys {keys_to_match}"
                )

            self.add_transaction(
                transaction["date"],
                transaction["units"],
                transaction["average_nav"],
                transaction["transaction_type"],
            )


class Holding:
    """A holding is a collection of transactions for a particular scheme. It can be used to calculate the total invested amount, total holding value, total pnl, average nav and pnl timeseries.

    Attributes
    ----------
    scheme_code: int
        The scheme code of the holding
    isin: str
        The isin of the holding
    name: str
        The name of the holding
    current_nav: float
        The current nav of the holding
    logger: logging.Logger
        The logger object to log messages

    """

    def __init__(
        self,
        transcation_dict: Dict = None,
        scheme_code: int = None,
        isin: str = None,
        name: str = None,
        current_nav: float = None,
        logger: logging.Logger = None,
    ) -> float:

        self.purchase_history = TrasactionHistory()
        self.sell_history = TrasactionHistory()
        self.all_transactions = TrasactionHistory()
        self.purchase_nav = 0.0
        self.purchase_units = 0.0
        self.sell_nav = 0.0
        self.sell_units = 0.0
        self.total_units = 0.0
        self.name = name
        self.current_nav = current_nav
        self.logger = logger or get_simple_logger(self.__class__.__name__)

        if transcation_dict:
            self.scheme_code = transcation_dict.get("scheme_code")
            self.isin = transcation_dict.get("isin")
            purchase_transactions = transcation_dict.get("purchase_history", [])
            sell_transactions = transcation_dict.get("sale_history", [])
            self.create_transactions(purchase_transactions, sell_transactions)
        else:
            self.scheme_code = scheme_code
            self.isin = isin

    def __str__(self) -> str:
        if self.name is None:
            return f"Holding with Code {self.scheme_code}"

        return f"{self.name} Holding ({self.scheme_code})"

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self):
        return len(self.all_transactions)

    def __getitem__(self, key):
        return self.all_transactions[key]

    def create_transcations_dict(
        self, transactions: List[Dict], transaction_type: str
    ) -> List[Dict]:
        """Updates the transaction history dictionary with apporpriate transaction type and keys so that new `Transcation` objects can be created."""
        if transaction_type == "purchase":
            date_column = "purchase_date"
        elif transaction_type == "sell":
            date_column = "sale_date"
        else:
            raise ValueError(
                "Invalid transaction type. Must be either purchase or sell."
            )

        transactions = [
            {
                "date": x[date_column],
                "units": x["units"],
                "average_nav": x["average_nav"],
                "transaction_type": transaction_type,
            }
            for x in transactions
        ]
        self.logger.info(f"Created {len(transactions)} {transaction_type} transactions")
        return transactions

    def create_transactions(
        self,
        purchase_transactions: List[Dict],
        sell_transactions: List[Dict],
        max_date: Union[str, datetime] = None,
    ) -> None:
        """
        Creates transactions from the purchase and sell transactions and updates the purchase and sell history.

        Parameters
        ----------
        purchase_transactions: List[Dict]
            A list of dictionaries containing purchase transactions
        sell_transactions: List[Dict]
            A list of dictionaries containing sell transactions
        max_date: Union[str, datetime]
            The maximum date to consider for the transactions. This will be used to filter for transactions to get the correct values of various metrics.
        """
        purchase_transactions = self.create_transcations_dict(
            purchase_transactions, "purchase"
        )
        sell_transactions = self.create_transcations_dict(sell_transactions, "sell")
        self.purchase_history.create_transcations_from_dict(purchase_transactions)
        self.sell_history.create_transcations_from_dict(sell_transactions)
        self.all_transactions = self.purchase_history + self.sell_history
        self.all_transactions.sort_transactions()
        self.purchase_nav = self.purchase_history.average_nav(max_date)
        self.purchase_units = np.sum(self.purchase_history.unit_array)
        self.sell_nav = self.sell_history.average_nav(max_date)
        self.sell_units = np.sum(self.sell_history.unit_array)

    def average_nav(self, max_date: Union[str, datetime] = None) -> float:
        """Average nav of the holding. If max_date is provided, the transactions after the max_date are not considered."""
        return self.all_transactions.average_nav(max_date)

    def pnl(
        self,
        current_nav: float = None,
        percentage: bool = False,
        max_date: Union[str, datetime] = None,
    ) -> float:
        """Calculate the total pnl of the holding. If max_date is provided, the transactions after the max_date are not considered. If percentage is True, returns the pnl as a percentage of the invested amount."""
        return self.all_transactions.transactions_pnl(current_nav, percentage, max_date)

    def invested_amount(self, max_date: Union[str, datetime] = None) -> float:
        """Calculate the total invested amount in the holding. If max_date is provided, the transactions after the max_date are not considered."""
        return self.all_transactions.net_transaction_value(max_date)

    def get_total_units(self, max_date: Union[str, datetime] = None) -> float:
        """Calculate the total units in the holding. If max_date is provided, the transactions after the max_date are not considered."""
        return self.all_transactions.total_units(max_date)

    def holding_value(
        self, nav: float = None, max_date: Union[str, datetime] = None
    ) -> float:
        """Calculate the total holding value in the holding for a particular nav. If max_date is provided, the transactions after the max_date are not considered. If nav is None, the average nav is used."""
        if nav is None:
            nav = self.current_nav or self.average_nav(max_date)
        self.total_units = self.get_total_units(max_date)
        return self.total_units * nav

    def get_pnl_timeseries(self, nav_data: Dict = None) -> pd.DataFrame:
        """Calculate the pnl timeseries for the holding. Returns a dataframe with date, total invested amount, current value, pnl and pnl percentage.

        Parameters
        ----------
        nav_data: Dict
            The nav data for the holding. If not provided, the nav data is fetched from the API. It is assumed that the nav data is fetched from the [mfapi](https://api.mfapi.in).

        Returns
        -------
        pd.DataFrame
            A dataframe with date, total invested amount, current value, pnl and pnl percentage.
        """
        if nav_data is None:
            code = self.scheme_code
            url = f"https://api.mfapi.in/mf/{code}"
            response = requests.get(url)
            nav_data = response.json()["data"]
            self.logger.info(f"Nav data fetched for scheme code {self.scheme_code}")

        nav_df = pd.DataFrame(nav_data)
        nav_df["date"] = pd.to_datetime(nav_df["date"], format="%d-%m-%Y")
        nav_df.sort_values("date", inplace=True)
        nav_df["nav"] = pd.to_numeric(nav_df["nav"])
        nav_df = nav_df[["date", "nav"]]

        transactions = self.all_transactions.transaction_history
        transaction_dates = [x.date_ for x in transactions]
        # transcation dates will be used to change the total units
        total_units = [self.get_total_units(x) for x in transaction_dates]
        transcation_values = [self.invested_amount(t) for t in transaction_dates]
        transcation_df = pd.DataFrame(
            {
                "date": transaction_dates,
                "total_units": total_units,
                "total_invested": transcation_values,
            }
        )
        transcation_df["date"] = pd.to_datetime(transcation_df["date"])
        transcation_df.sort_values("date", inplace=True)

        merged = pd.merge_asof(nav_df, transcation_df, on="date")
        merged = merged[merged["total_units"].notna()]
        merged["total_invested"] = merged["total_invested"].clip(lower=0)
        merged = merged.query(
            "total_invested	>0"
        )  # remove rows with negative invested amount
        merged["current_value"] = merged["total_units"] * merged["nav"]
        merged["pnl"] = merged["current_value"] - merged["total_invested"]
        merged["pnl_percentage"] = merged["pnl"] / merged["total_invested"] * 100
        merged["pnl_percentage"].fillna(0, inplace=True)
        return merged

    @property
    def transaction_dates(self):
        purchase_dates = [x.date_ for x in self.purchase_history]
        sell_dates = [x.date_ for x in self.sell_history]
        return {
            "purchase_dates": purchase_dates,
            "sell_dates": sell_dates,
        }


class Portfolio:
    """A portfolio is a collection of holdings. It can be used to calculate the total invested amount, total holding value, total pnl, average nav and pnl timeseries.

    Attributes
    ----------
    holdings: List[Holding]
        A list of holding objects

    Methods
    -------
    get_invested_amount(max_date: Union[str, datetime] = None) -> float
        Returns the total invested amount in the portfolio
    get_holding_value(nav: float = None, max_date: Union[str, datetime] = None) -> float
        Returns the total holding value in the portfolio
    get_pnl(current_nav: float, percentage: bool = False, max_date: Union[str, datetime] = None) -> float
        Returns the total pnl in the portfolio
    get_average_nav(max_date: Union[str, datetime] = None) -> float
        Returns the average nav in the portfolio
    get_pnl_timeseries() -> pd.DataFrame
        Returns the pnl timeseries for the portfolio
    """

    def __init__(
        self,
        holdings: List[Holding] = None,
        transcations: Dict = None,
        logger: logging.Logger = None,
    ):
        self.holdings = holdings or []
        if transcations:
            self.create_holdings(transcations)
        self.logger = logger or get_simple_logger(self.__class__.__name__)

    def __str__(self):
        return f"Portfolio with {len(self.holdings)} holdings."

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self):
        return len(self.holdings)

    def __getitem__(self, key):
        return self.holdings[key]

    def create_holdings(self, transcations: Dict):
        """Create holdings from the transcations dictionary. The dictionary must contain keys `scheme_code`, `purchase_transactions` and `sell_transactions`."""
        for transcation in transcations:
            holding = Holding(transcation_dict=transcation)
            self.holdings.append(holding)

    def get_invested_amount(self, max_date: Union[str, datetime] = None) -> float:
        """Calculate the total invested amount in the entire `Portfolio`. If max_date is provided, the transactions after the max_date are not considered."""
        return sum([x.invested_amount(max_date) for x in self.holdings])

    def get_holding_value(
        self, nav: float = None, max_date: Union[str, datetime] = None
    ) -> float:
        """Calculate the total holding value in the entire `Portfolio` for a particular nav. If max_date is provided, the transactions after the max_date are not considered. If nav is None, the average nav is used."""
        return sum([x.holding_value(nav, max_date) for x in self.holdings])

    def get_pnl(
        self,
        current_nav: float,
        percentage: bool = False,
        max_date: Union[str, datetime] = None,
    ) -> float:
        """Calculate the total pnl in the entire `Portfolio`. If max_date is provided, the transactions after the max_date are not considered. If percentage is True, returns the pnl as a percentage of the invested amount."""
        return sum([x.pnl(current_nav, percentage, max_date) for x in self.holdings])

    def get_average_nav(self, max_date: Union[str, datetime] = None) -> float:
        units = np.array([x.get_total_units(max_date) for x in self.holdings])
        avg_nav = np.array([x.average_nav(max_date) for x in self.holdings])
        return np.sum(units * avg_nav) / np.sum(units)

    def get_pnl_timeseries(self) -> pd.DataFrame:
        """Calculate the pnl timeseries for the entire `Portfolio`. Returns a dataframe with date, total invested amount, current value, pnl and pnl percentage."""
        pnls = []
        for holding in self.holdings:
            pnl = holding.get_pnl_timeseries()
            # take only the required columns
            pnl["scheme_code"] = holding.scheme_code
            pnls.append(pnl)

        pnl = pd.concat(pnls, ignore_index=True)
        self.pnl = pnl

        pnl = pnl[["date", "total_invested", "current_value", "scheme_code"]]
        pnl = pnl.groupby("date").aggregate(
            {
                "total_invested": "sum",
                "current_value": "sum",
                "scheme_code": lambda x: str(x.tolist()),
            }
        )
        pnl = pnl.reset_index()
        pnl = pnl.query(
            "total_invested	>0"
        )  # remove rows with negative invested amount
        pnl["pnl"] = pnl["current_value"] - pnl["total_invested"]
        pnl["pnl_percentage"] = pnl["pnl"] / pnl["total_invested"] * 100
        return pnl

    @property
    def transaction_dates(self):
        """Get the transaction dates for the entire `Portfolio`. Returns a dictionary with keys `purchase_dates` and `sell_dates`."""
        transaction_dates = {"purchase_dates": [], "sell_dates": []}
        for holding in self.holdings:
            holding_purchase_dates = holding.transaction_dates["purchase_dates"]
            holding_sell_dates = holding.transaction_dates["sell_dates"]
            transaction_dates["purchase_dates"].extend(holding_purchase_dates)
            transaction_dates["sell_dates"].extend(holding_sell_dates)

        transaction_dates["purchase_dates"] = sorted(
            list(set(transaction_dates["purchase_dates"]))
        )
        transaction_dates["sell_dates"] = sorted(
            list(set(transaction_dates["sell_dates"]))
        )

        return transaction_dates
