import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output

# Load and Prepare Data ***************************************************
directory = 'C:/Users/reach/python_1/first_app_dash'
df = pd.read_csv(f'{directory}/tweets.csv')

# Convert column values for consistency
df["name"] = df["name"].str.lower()
df["date_time"] = pd.to_datetime(df["date_time"], dayfirst=True)

# Ensure date_time is explicitly included before grouping
df["date_time"] = df["date_time"].dt.date

# Group by date and name, aggregating likes and shares
df = df.groupby(["date_time", "name"], as_index=False).agg(
    {"number_of_likes": "mean", "number_of_shares": "mean"}
)

# Convert only numeric columns to integers
df[["number_of_likes", "number_of_shares"]] = df[["number_of_likes", "number_of_shares"]].astype(int)

# Dash App Setup **********************************************************
stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]
app = Dash(__name__, external_stylesheets=stylesheets)

app.layout = html.Div([
    html.Div(html.H1("Twitter Likes Analysis of Famous People", style={"textAlign": "center"}), className="row"),

    html.Div(dcc.Graph(id="line-chart"), className="row"),

    html.Div([
        html.Div(dcc.Dropdown(
            id="my-dropdown",
            multi=True,
            options=[{"label": x, "value": x} for x in sorted(df["name"].unique())],
            value=["taylorswift13", "cristiano", "jtimberlake"],
        ), className="three columns"),

        html.Div(html.A(
            "Click here to Visit Twitter", href="https://twitter.com/explore", target="_blank"
        ), className="two columns"),
    ], className="row"),
])


# Callback Function ********************************************************
@app.callback(
    Output("line-chart", "figure"),
    [Input("my-dropdown", "value")]
)
def update_graph(chosen_value):
    if not chosen_value:
        return px.line()

    df_filtered = df[df["name"].isin(chosen_value)]
    fig = px.line(
        df_filtered,
        x="date_time",
        y="number_of_likes",
        color="name",
        log_y=True,
        labels={"number_of_likes": "Likes", "date_time": "Date", "name": "Celebrity"},
    )

    fig.update_traces(mode="markers+lines", marker=dict(size=6))

    return fig


# Run Server ***************************************************************
if __name__ == "__main__":
    app.run(debug=True)
