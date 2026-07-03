from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun, WikipediaQueryRun, ArxivQueryRun
from langchain_community.utilities import WikipediaAPIWrapper, ArxivAPIWrapper
from langchain_core.tools import tool
import sqlite3
import os
import requests
from datetime import datetime
import pytz

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STOCK_API = os.getenv("ALPHA_VANTAGE_API_KEY")


# backend.py

load_dotenv()

# -------------------
# 1. LLM
# -------------------
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=GROQ_API_KEY,
    temperature=0.3,
    max_tokens=1000
)

# -------------------
# 2. Tools
# -------------------
# Tools
search_tool = DuckDuckGoSearchRun(region="us-en")

# --- Wikipedia lookup ---
wikipedia_tool = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=1500)
)

# --- ArXiv paper search ---
arxiv_tool = ArxivQueryRun(
    api_wrapper=ArxivAPIWrapper(top_k_results=3, doc_content_chars_max=1500)
)


@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={STOCK_API}"
    r = requests.get(url)
    return r.json()



@tool
def get_current_datetime(timezone: str = "UTC") -> dict:
    """
    Get the current date and time, optionally in a specific IANA timezone
    (e.g. 'Asia/Kolkata', 'America/New_York', 'Europe/London'). Defaults to UTC.
    Useful whenever the user asks what day/date/time it is, or asks about
    something relative to "today", "now", "this week", etc.
    """
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return {
            "timezone": timezone,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
        }
    except Exception as e:
        return {"error": f"Unknown timezone '{timezone}': {e}"}


@tool
def convert_units(value: float, from_unit: str, to_unit: str, category: str) -> dict:
    """
    Convert a value between units. 
    category must be one of: 'length', 'weight', 'temperature'.
    
    length units: mm, cm, m, km, in, ft, yd, mile
    weight units: mg, g, kg, lb, oz
    temperature units: celsius, fahrenheit, kelvin
    """
    try:
        category = category.lower()

        if category == "length":
            to_meters = {
                "mm": 0.001, "cm": 0.01, "m": 1, "km": 1000,
                "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mile": 1609.34,
            }
            if from_unit not in to_meters or to_unit not in to_meters:
                return {"error": f"Unsupported length unit(s): {from_unit}, {to_unit}"}
            meters = value * to_meters[from_unit]
            result = meters / to_meters[to_unit]

        elif category == "weight":
            to_grams = {"mg": 0.001, "g": 1, "kg": 1000, "lb": 453.592, "oz": 28.3495}
            if from_unit not in to_grams or to_unit not in to_grams:
                return {"error": f"Unsupported weight unit(s): {from_unit}, {to_unit}"}
            grams = value * to_grams[from_unit]
            result = grams / to_grams[to_unit]

        elif category == "temperature":
            from_unit_l, to_unit_l = from_unit.lower(), to_unit.lower()
            # Convert to Celsius first
            if from_unit_l == "celsius":
                celsius = value
            elif from_unit_l == "fahrenheit":
                celsius = (value - 32) * 5 / 9
            elif from_unit_l == "kelvin":
                celsius = value - 273.15
            else:
                return {"error": f"Unsupported temperature unit: {from_unit}"}

            if to_unit_l == "celsius":
                result = celsius
            elif to_unit_l == "fahrenheit":
                result = celsius * 9 / 5 + 32
            elif to_unit_l == "kelvin":
                result = celsius + 273.15
            else:
                return {"error": f"Unsupported temperature unit: {to_unit}"}

        else:
            return {"error": f"Unsupported category '{category}'. Use length, weight, or temperature."}

        return {
            "input": f"{value} {from_unit}",
            "output": f"{round(result, 4)} {to_unit}",
            "category": category,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_exchange_rate(from_currency: str, to_currency: str, amount: float = 1.0) -> dict:
    """
    Get the current exchange rate and converted amount between two currencies
    (e.g. from_currency='USD', to_currency='INR'). Uses the free Frankfurter API,
    no key required.
    """
    try:
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_currency.upper()}&to={to_currency.upper()}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if "rates" not in data:
            return {"error": f"Could not fetch rate for {from_currency} -> {to_currency}", "raw": data}
        converted = data["rates"].get(to_currency.upper())
        return {
            "from": from_currency.upper(),
            "to": to_currency.upper(),
            "amount": amount,
            "converted_amount": converted,
            "date": data.get("date"),
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_crypto_price(coin_id: str, vs_currency: str = "usd") -> dict:
    """
    Get the current price of a cryptocurrency (e.g. coin_id='bitcoin', 'ethereum',
    'dogecoin') in a given fiat currency (default 'usd'). Uses the free
    CoinGecko API, no key required. coin_id should be the CoinGecko slug
    (lowercase, e.g. 'bitcoin' not 'BTC').
    """
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id.lower()}&vs_currencies={vs_currency.lower()}&include_24hr_change=true"
        r = requests.get(url, timeout=10)
        data = r.json()
        if coin_id.lower() not in data:
            return {"error": f"Unknown coin_id '{coin_id}'. Use CoinGecko slugs like 'bitcoin', 'ethereum'."}
        return {"coin": coin_id.lower(), "currency": vs_currency.lower(), **data[coin_id.lower()]}
    except Exception as e:
        return {"error": str(e)}


@tool
def get_weather(city: str) -> dict:
    """
    Get the current weather for a city using OpenWeatherMap.
    Requires OPENWEATHER_API_KEY to be set in the environment (.env file).
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return {"error": "OPENWEATHER_API_KEY is not set in the environment."}
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        r = requests.get(url, timeout=10)
        data = r.json()
        if str(data.get("cod")) != "200":
            return {"error": data.get("message", "Could not fetch weather")}
        return {
            "city": data.get("name"),
            "country": data.get("sys", {}).get("country"),
            "temperature_c": data.get("main", {}).get("temp"),
            "feels_like_c": data.get("main", {}).get("feels_like"),
            "condition": data.get("weather", [{}])[0].get("description"),
            "humidity_pct": data.get("main", {}).get("humidity"),
            "wind_speed_mps": data.get("wind", {}).get("speed"),
        }
    except Exception as e:
        return {"error": str(e)}



tools = [
    search_tool,
    get_stock_price,
    calculator,
    wikipedia_tool,
    arxiv_tool,
    get_current_datetime,
    convert_units,
    get_exchange_rate,
    get_crypto_price,
    get_weather,
]
llm_with_tools = llm.bind_tools(tools)

# -------------------
# 3. State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------
# 4. Nodes
# -------------------
def chat_node(state: ChatState):
    """LLM node that may answer or request a tool call."""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode(tools)

# -------------------
# 5. Checkpointer
# -------------------
conn = sqlite3.connect(database="chatbot.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

# -------------------
# 6. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")

graph.add_conditional_edges("chat_node",tools_condition)
graph.add_edge('tools', 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)

# -------------------
# 7. Helper
# -------------------
def retrieve_all_threads(user_id: str | None = None):
    """
    Return thread_ids, optionally scoped to a single user.

    user_id is matched against the checkpoint metadata, which is populated
    from the `metadata` dict passed in `config` when the graph is invoked
    (see frontend.py: CONFIG["metadata"]["user_id"]).
    """
    all_threads = set()
    list_filter = {"user_id": user_id} if user_id else None
    for checkpoint in checkpointer.list(None, filter=list_filter):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)


def delete_thread(thread_id: str) -> None:
    """Delete all saved checkpoints and writes for a specific thread."""
    checkpointer.delete_thread(thread_id)


def delete_all_threads(user_id: str | None = None) -> None:
    """
    Delete saved chat threads from the checkpoint database.

    If user_id is provided, only that user's threads are deleted.
    If user_id is None, EVERY thread in the database is deleted
    (kept for backward compatibility / admin use only).
    """
    for thread_id in retrieve_all_threads(user_id):
        delete_thread(thread_id)