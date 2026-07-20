from data_collection import fetch_company_financials


# Gets the latest available value for a specific financial metric
def get_latest_value(statement, metric):
    # Check if the metric exists
    if metric not in statement:
        return None

    # Get all quarterly values for the metric
    values = statement[metric]

    # Return the first available value
    for date, value in values.items():
        if value is not None:
            return value

    return None


# Calculates what percentage of revenue becomes profit
# Formula: Net Income / Revenue * 100
def calculate_net_profit_margin(income_statement):
    net_income = get_latest_value(income_statement, "Net Income")
    revenue = get_latest_value(income_statement, "Total Revenue")

    # Check for missing data and avoid division by zero
    if net_income is None or revenue is None or revenue == 0:
        return None

    return (net_income / revenue) * 100


# Calculates how much debt the company has compared to equity
# Formula: Total Debt / Stockholders Equity
def calculate_debt_to_equity(balance_sheet):
    total_debt = get_latest_value(balance_sheet, "Total Debt")
    equity = get_latest_value(balance_sheet, "Stockholders Equity")

    # Check for missing data and avoid division by zero
    if total_debt is None or equity is None or equity == 0:
        return None

    return total_debt / equity


# Calculates revenue growth between the latest two quarters
def calculate_revenue_growth(income_statement):
    if "Total Revenue" not in income_statement:
        return None

    revenues = []

    # Collect all available revenue values
    for date, value in income_statement["Total Revenue"].items():
        if value is not None:
            revenues.append(value)

    # Need at least two quarters to compare
    if len(revenues) < 2:
        return None

    current_revenue = revenues[0]
    previous_revenue = revenues[1]

    # Avoid division by zero
    if previous_revenue == 0:
        return None

    return ((current_revenue - previous_revenue) / previous_revenue) * 100


# Calculates earnings growth between the latest two quarters
# Uses Net Income to measure earnings
def calculate_earnings_growth(income_statement):
    if "Net Income" not in income_statement:
        return None

    earnings = []

    # Collect all available Net Income values
    for date, value in income_statement["Net Income"].items():
        if value is not None:
            earnings.append(value)

    # Need at least two quarters to compare
    if len(earnings) < 2:
        return None

    current_earnings = earnings[0]
    previous_earnings = earnings[1]

    # Avoid division by zero
    if previous_earnings == 0:
        return None

    return ((current_earnings - previous_earnings) / previous_earnings) * 100


# Calculates Free Cash Flow
# Shows how much cash the company generates after capital expenditures
def calculate_free_cash_flow(cash_flow):
    operating_cash_flow = get_latest_value(
        cash_flow, "Operating Cash Flow"
    )

    capital_expenditure = get_latest_value(
        cash_flow, "Capital Expenditure"
    )

    # Return None if required data is missing
    if operating_cash_flow is None or capital_expenditure is None:
        return None

    # Yahoo fin reports Capital Expenditure as a neg number
    return operating_cash_flow + capital_expenditure


# Calculates the company's ability to pay short-term obligations
# Formula: Current Assets / Current Liabilities
def calculate_current_ratio(balance_sheet):
    current_assets = get_latest_value(
        balance_sheet, "Current Assets"
    )

    current_liabilities = get_latest_value(
        balance_sheet, "Current Liabilities"
    )

    # Check for missing data and avoid division by zero
    if (
        current_assets is None
        or current_liabilities is None
        or current_liabilities == 0
    ):
        return None

    return current_assets / current_liabilities


# Calculates Return on Equity (ROE)
# Shows how efficiently the company generates profit from equity
# Formula: Net Income / Stockholders Equity * 100
def calculate_roe(income_statement, balance_sheet):
    net_income = get_latest_value(
        income_statement, "Net Income"
    )

    equity = get_latest_value(
        balance_sheet, "Stockholders Equity"
    )

    # Check for missing data and avoid division by zero
    if net_income is None or equity is None or equity == 0:
        return None

    return (net_income / equity) * 100


# Gets the company's financial data and calculates all KPIs
def calculate_kpis(ticker):

    # Fetch financial data from data_collection.py
    data = fetch_company_financials(ticker)

    # Return empty dictionary if fetching failed
    if not data:
        return {}

    # Separate the three financial statements
    income_statement = data["income_statement"]
    balance_sheet = data["balance_sheet"]
    cash_flow = data["cash_flow"]

    # Calculate and return all 7 KPIs
    return {
        "net_profit_margin": calculate_net_profit_margin(
            income_statement
        ),
        "debt_to_equity": calculate_debt_to_equity(
            balance_sheet
        ),
        "revenue_growth": calculate_revenue_growth(
            income_statement
        ),
        "earnings_growth": calculate_earnings_growth(
            income_statement
        ),
        "free_cash_flow": calculate_free_cash_flow(
            cash_flow
        ),
        "current_ratio": calculate_current_ratio(
            balance_sheet
        ),
        "roe": calculate_roe(
            income_statement,
            balance_sheet
        )
    }


# Test all KPIs with AAPL as an example
if __name__ == "__main__":
    kpis = calculate_kpis("AAPL")  # Change the ticker symbol as needed

    print("\n--- AAPL KPI Results ---")

    for name, value in kpis.items():
        if value is not None:
            print(f"{name}: {value:.2f}")
        else:
            print(f"{name}: N/A")