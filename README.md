# Pulse AI News 🌱

Pulse is a lightning-fast Progressive Web App (PWA) designed to curate, aggregate, and smartly filter news across AI, Technology, and Robotics.

It features a custom-built HTML web scraper that natively syndicates profound AI model updates directly from Anthropic and OpenAI alongside standard global RSS feeds.

## Local Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd pulse
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the project root containing your API keys (see `.env.example`).
   ```env
   NEWS_API_KEY=your_key_here
   ANTHROPIC_API_KEY=your_key_here
   SUMMARISE_WITH_AI=false
   ```

4. **Run the Application:**
   Pulse utilises `uvicorn` to serve its FastAPI backend asynchronously.
   ```bash
   python3 main.py
   # Or alternatively:
   # uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Navigate to `http://localhost:8000/` in your browser.

## Cloud Deployment (Render.com)

Pulse is pre-configured for instant zero-downtime deployments on Render.
1. Connect this repository to your Render account.
2. Select **Blueprint** to deploy via the attached `render.yaml`, or create a **Web Service** manually using the `Procfile`.
3. Render will automatically execute `pip install -r requirements.txt` and launch the app via `uvicorn`. Ensure you supply the `NEWS_API_KEY` and `ANTHROPIC_API_KEY` in the Render Environment Variables dashboard.

The platform relies on the `GET /health` route to verify load balancer stability during container rollout.
