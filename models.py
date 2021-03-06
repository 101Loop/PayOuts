import calendar
import os
from dataclasses import dataclass, field, asdict
import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional

from tempoapiclient.client import Tempo


JIRA_BASE_URL = os.environ["JIRA_BASE_URL"]
TEMPO_BASE_URL = os.environ["TEMPO_BASE_URL"]


def to_json(object):
    def format_value(value):
        json_val = value
        if isinstance(json_val, (datetime.date, datetime.datetime)):
            json_val = json_val.isoformat()
        elif isinstance(json_val, Decimal):
            json_val = str(json_val)
        elif isinstance(json_val, BillMode):
            json_val = {"name": json_val.name, "value": json_val.value}
        elif isinstance(json_val, list):
            json_val = [format_value(curr_val) for curr_val in json_val]
        elif isinstance(json_val, dict):
            json_val = {format_value(curr_key): format_value(curr_val) for curr_key, curr_val in json_val.items()}
        elif isinstance(json_val, (WorkLog, InvoiceItem, Invoice)):
            json_val = json_val.to_json()
        elif isinstance(json_val, (TempoUser, JiraIssue)):
            json_val = asdict(json_val)
        return json_val

    json_dict = {}

    for key, val in object.__dict__.items():
        json_val = format_value(val)
        json_key = format_value(key)
        json_dict[json_key] = json_val

    return json_dict


class BillMode(Enum):
    MONTHLY = "M"
    HOURLY = "H"


@dataclass
class TempoUser:
    account_id: str
    name: str

    def __str__(self):
        return f"{JIRA_BASE_URL}/user?accountId={self.account_id}"

    @classmethod
    def from_tempo_api(cls, api_dict: Dict):
        return cls(account_id=api_dict["accountId"], name=api_dict["displayName"])


@dataclass
class JiraIssue:
    key: str
    jira_id: int

    def __str__(self):
        return f"{JIRA_BASE_URL}/issue/{self.key}"

    @classmethod
    def from_tempo_api(cls, api_dict: Dict):
        return cls(key=api_dict["key"], jira_id=api_dict["id"])


@dataclass
class WorkLog:
    """WorkLog

    Represents WorkLog from Tempo
    """

    worklog_id: int
    jira_id: int
    time_spent_seconds: int
    billable_seconds: int
    date: datetime.date
    description: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    author: TempoUser
    issue: JiraIssue
    account: str

    def __str__(self):
        return f"{TEMPO_BASE_URL}/worklogs/{self.worklog_id}"

    def __add__(self, other):
        return self.__add(other)

    def __radd__(self, other):
        return self.__add(other)

    def __add(self, other) -> Decimal:
        """Add

        Used in __add__ and __radd__

        Each WorkLog can be added to any int, float, decimal or another WorkLog.
        `hours` attribute is added.

        Args:
            other (any): Object with which hours needs to be added

        Returns:
            Decimal: Sum of self.hours and other
        """
        if isinstance(other, WorkLog):
            other = other.hours
        elif isinstance(other, (int, float)):
            other = str(other)

        return self.hours + Decimal(other)

    @property
    def hours(self):
        """Hours"""
        return self.billable_seconds / Decimal(60 * 60)

    def to_json(self):
        json_dict = {"hours": str(self.hours)}
        json_dict.update(to_json(self))
        return json_dict

    @staticmethod
    def filter_account_value(attribute) -> bool:
        """Filter Account Value

        Filter function for filtering attribute.

        Returns:
            bool: True if attribute is for Account, False otherwise
        """
        return attribute["key"] == "_Account_"

    @classmethod
    def from_tempo_api(cls, worklog_dict: Dict):
        return cls(
            worklog_id=worklog_dict["tempoWorklogId"],
            jira_id=worklog_dict["jiraWorklogId"],
            time_spent_seconds=worklog_dict["timeSpentSeconds"],
            billable_seconds=worklog_dict["billableSeconds"],
            date=datetime.date.fromisoformat(worklog_dict["startDate"]),
            description=worklog_dict["description"],
            created_at=datetime.datetime.strptime(worklog_dict["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc
            ),
            updated_at=datetime.datetime.strptime(worklog_dict["updatedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc
            ),
            author=TempoUser.from_tempo_api(worklog_dict["author"]),
            issue=JiraIssue.from_tempo_api(worklog_dict["issue"]),
            account=list(filter(WorkLog.filter_account_value, worklog_dict["attributes"]["values"]))[0],
        )


@dataclass
class InvoiceItem:
    """InvoiceItem

    Represents an invoice item. Each item corresponds to one work day.
    """

    date: datetime.date
    billing_mode: BillMode
    work_logs: List[WorkLog] = field(default_factory=list)

    def __str__(self):
        return f"{self.date.isoformat()} - {self.work_unit}"

    def __add__(self, other):
        return self.__add(other)

    def __radd__(self, other):
        return self.__add(other)

    def __add(self, other):
        """Add

        Used in __add__ and __radd__

        Each InvoiceItem can be added to any int, float, decimal or another InvoiceItem.
        `work_unit` attribute is added.

        Args:
            other (any): Object with which work_unit needs to be added

        Returns:
            Decimal: Sum of self.work_unit and other
        """
        if isinstance(other, InvoiceItem):
            other = other.work_unit
        elif isinstance(other, (int, float)):
            other = str(other)

        return self.work_unit + Decimal(other)

    @property
    def total_work_hours(self) -> Decimal:
        return sum(self.work_logs)

    @property
    def is_workday(self) -> bool:
        """Is Workday

        Check whether the bill date is a countable workday

        Returns:
            True if total work hours is more than 0 or weekday is in Mon-Fri
        """
        return self.total_work_hours > 3 or self.date.weekday() < 5

    @property
    def work_unit(self) -> Decimal:
        """Work Unit

        Returns:
            Decimal: total_work_hours if billing mode is hourly, else computes work days
        """
        return (
            self.total_work_hours
            if self.billing_mode == BillMode.HOURLY
            else Decimal(True)
        )

    def to_json(self):
        json_dict = {
            "total_work_hours": str(self.total_work_hours),
            "is_workday": self.is_workday,
            "work_unit": str(self.work_unit),
        }
        json_dict.update(to_json(self))
        return json_dict


@dataclass
class Invoice:
    """Invoice

    Represents a Invoice object for work done between start date and invoice date, both inclusive.
    """

    start_date: datetime.date
    # Invoice date is the last date of week i.e. Friday
    invoice_date: datetime.date

    rate: Decimal
    billing_mode: BillMode
    items: Dict[datetime.date, InvoiceItem] = field(default_factory=dict)

    def __post_init__(self):
        """
        Initialize self.items with all dates in the invoice and a blank bill
        """
        next_date = self.start_date
        while next_date <= self.invoice_date:
            self.items[next_date] = InvoiceItem(date=next_date, billing_mode=self.billing_mode)
            next_date += datetime.timedelta(days=1)

    def __str__(self):
        return f"{self.invoice_date.isoformat()} - {self.invoice_amount}"

    @property
    def total_work_unit(self) -> Decimal:
        """Total Work Unit

        Returns:
            Decimal: Sum of work unit of each items
        """
        return sum(self.items.values())

    @property
    def net_rate(self) -> Decimal:
        """Net Rate

        In case of hourly, net rate is rate itself.
        In case of monthly billing, net rate varies.
        Further, daily rate is calculated based on dividing monthly rate with total number of days in the month and
        calculating on the basis of 7 days in a week.

        Returns:
            Decimal: rate rounded upto 4 places
        """
        if self.billing_mode == BillMode.HOURLY:
            rate: Decimal = self.rate
        else:
            # For monthly, we calculate on the basis of number of days in a month
            start_day_of_month, no_of_days_in_start_month = calendar.monthrange(self.start_date.year, self.start_date.month)
            start_day_of_end_month, no_of_days_in_end_month = calendar.monthrange(self.invoice_date.year, self.invoice_date.month)

            if no_of_days_in_end_month == no_of_days_in_start_month:
                rate: Decimal = self.rate / no_of_days_in_start_month
            else:
                # Change in month and also number of days in month
                work_days_in_start_month = no_of_days_in_start_month - self.start_date.day + 1
                work_days_in_end_month = self.invoice_date.day
                rate_in_start_month = self.rate / no_of_days_in_start_month
                rate_in_end_month = self.rate / no_of_days_in_end_month
                rate = ((rate_in_start_month * work_days_in_start_month) + (rate_in_end_month * work_days_in_end_month)) / (work_days_in_start_month + work_days_in_end_month)
        return round(rate, 4)

    @property
    def invoice_amount(self) -> Decimal:
        """Invoice Amount"""
        return round(self.net_rate * self.total_work_unit, 4)

    @property
    def due_date(self) -> datetime.date:
        """Due Date

        Due Date based on NET30 term

        Returns:
            datetime.date: Due date based on NET30 term
        """
        return self.invoice_date + datetime.timedelta(days=30)

    def total_work_days(self) -> int:
        """Total Work Days

        Returns:
            int: Sum of work days in each bill
        """
        return sum(int(bill.is_workday) for bill in self.items.values())

    def to_json(self) -> Dict:
        json_dict = {
            "total_work_days": str(self.total_work_days()),
            "total_work_unit": str(self.total_work_unit),
            "net_rate": str(self.net_rate),
            "invoice_amount": str(self.invoice_amount),
            "due_date": self.due_date.isoformat(),
        }

        json_dict.update(to_json(self))
        return json_dict


@dataclass
class Consultant:
    billing_mode: BillMode
    rate: Decimal
    tempo_instance: Tempo
    name: str = None
    user_id: str = None

    @staticmethod
    def billing_date_bounds(*, date: datetime.date):
        """Billing Date Bounds

        Billing Start Date is Saturday.
        Billing End Date is Friday
        Calculates the last Saturday and the next Friday based on given date.

        Args:
            date (datetime.date): Any date of the week for which billing is to be done

        Returns:
            tuple: tuple of start_date, end_date
        """
        weekday = date.weekday()

        if weekday >= 5:
            # If it's Saturday or Sunday, timedelta for start_date is date's weekday - 5 (i.e. Saturday's weekday)
            start_date = date - datetime.timedelta(days=weekday - 5)
            # Timedelta for end_date is 6 - date's weekday (no. of days to Sunday) + Friday's weekday (4) + 1
            end_date = date + datetime.timedelta(days=5 + (6 - weekday))
        else:
            # Otherwise, time delta is date's weekday + 2 (reversing weekday takes on Monday, and 2 days for Sun & Sat)
            start_date = date - datetime.timedelta(days=weekday + 2)
            # Timedelta for end_date is Friday's Weekday (4) - date's weekday
            end_date = date + datetime.timedelta(days=4 - weekday)

        return start_date, end_date

    def __invoice_for_work_date(self, work_date: datetime.date) -> Invoice:
        """Invoice for work date

        Computes Invoice for a given work date.

        Args:
            work_date (datetime.date): Can we any date within 7 days week period

        Returns:
            Invoice: Invoice object
        """
        start_date, end_date = Consultant.billing_date_bounds(date=work_date)
        invoice = Invoice(start_date=start_date, invoice_date=end_date, billing_mode=self.billing_mode, rate=self.rate)

        work_logs = self.tempo_instance.get_worklogs(dateFrom=start_date, dateTo=end_date)
        work_log_objects = map(WorkLog.from_tempo_api, work_logs)

        # Add all work log in invoice items
        [invoice.items[work_log.date].work_logs.append(work_log) for work_log in work_log_objects]

        return invoice

    def invoices_in_range(self, start_date: datetime.date, end_date: Optional[datetime.date]) -> Dict[datetime.date, Invoice]:
        """Invoices in Range

        Computes all possible invoices for work done between start date and end date

        Args:
            start_date (datetime.date): Start date of range
            end_date (:obj:`datetime.date`, optional): End date of range, defaults to today

        Returns:
            dict: Dictionary containing invoice date as key and corresponding Invoice object as value
        """
        end_date = end_date or datetime.date.today()
        invoices = {}
        next_date = start_date
        while next_date <= end_date:
            invoice = self.__invoice_for_work_date(work_date=next_date)
            next_date += datetime.timedelta(days=7)
            invoices[invoice.invoice_date] = invoice

        return invoices
