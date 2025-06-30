# 📈 Crypto Scalping Bot Framework with ML Dashboard

This project is a complete crypto scalping framework that:
- Collects live market data using Binance API
- Runs rule-based and machine learning strategies
- Logs signals and trades to PostgreSQL
- Allows you to train an ML model (LightGBM) on historical data
- Provides a **dashboard** to visualize market data, predictions, and performance

---

## 🛠 Requirements

**Python Version:** Python 3.8–3.11 recommended

### 🔧 Installation

1. Clone the repository or download the source code:
```bash

cd to to the folder of the project
Create and activate a virtual environment (recommended):

bash
Copy
Edit
python -m venv venv
source venv/bin/activate    # on Linux/macOS
venv\Scripts\activate       # on Windows
Install all dependencies:

bash
Copy
Edit
pip install -r requirements.txt
📦 Required Python Packages
If requirements.txt is missing, here are the main packages used:

txt
Copy
Edit
pandas
numpy
scikit-learn
joblib
sqlalchemy
psycopg2-binary
requests
ta-lib
binance
streamlit
apscheduler
Install them manually:

bash
Copy
Edit
pip install pandas numpy scikit-learn joblib sqlalchemy psycopg2-binary requests ta-lib binance streamlit apscheduler
✅ Note: TA-Lib may require compilation. If you face issues on Windows, try:

bash
Copy
Edit
pip install TA-Lib‑0.4.0‑cp311‑cp311‑win_amd64.whl
🧠 How to Run the Project
if you have vscode installed after installing all nessecarry files just run the poject starting withe the Scalping Framework.py  and then the ml trainer the the dashboard sequentilly if you dont have vs code 
then:
1. ✅ Run the Scalping Framework (Real-time Data Collector + Strategy Engine)
This collects data from Binance and evaluates strategies:

bash
Copy
Edit
python scalping_bot_framework.py
Make sure your .env or config section has the correct database credentials and Binance symbol (e.g., BTCUSDT, ETHUSDT).

2. 🧪 Train the LightGBM Model
After some data is collected, run the trainer:

bash
Copy
Edit
python backend/ml/trainer_lightgbm.py
This fetches recent market data from the DB and trains a regression model to predict price direction.

It saves the model at:

models/lightgbm_model.pkl

3. 📊 Launch the Dashboard
Use Streamlit to visualize market trends and predictions:

bash
Copy
Edit
cd dashboard
streamlit run dashboard.py
The dashboard displays:

Live price chart

RSI, MACD, EMA indicators

Model predictions

Strategy signal logs

PnL over time

🧠 Strategy Modules
Your strategies are modular and located in:

bash
Copy
Edit
backend/strategies/
├── rsi_strategy.py
├── macd_strategy.py
├── ema_crossover.py
├── bb_strategy.py
├── evaluate_lightgbm.py  # ML-based strategy
You can add custom strategies by creating new Python functions that accept row and return a signal dict.

✅ Summary of Steps
Step	Script	Description
1	scalping_bot_framework.py	Starts data collection & runs strategy logic
2	backend/ml/trainer_lightgbm.py	Trains and saves LightGBM model
3	dashboard/dashboard.py	Launches the dashboard via Streamlit

⚠️ Notes
Make sure your PostgreSQL database is running and credentials are valid.

Binance API can disconnect sometimes — the bot will auto-reconnect.

Always run the scalping bot first before training the model or viewing the dashboard.

Keep your models/ directory in place to avoid missing file errors.

🧠 Tips
To test fast, reduce the interval to "1m" in Binance settings.

Keep Streamlit and the bot running in separate terminals.

You can extend the ML model to use sentiment data or multi-timeframe inputs.

🤖 Author
Made by [Your Name] – Freelance Data Scientist / Algo Dev
📧 Reach me on Upwork or GitHub if you have questions or want upgrades!

yaml
Copy
Edit

---

Let me know your:
- Dashboard filename (if not `dashboard.py`)
- Actual repo name
- Any optional features (like Telegram alerts)

And I can customize this further.
