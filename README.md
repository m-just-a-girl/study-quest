# Study Quest

> `v2-development` is an isolated preview track. The production service continues to deploy from `main`.

An AI-powered study workspace with onboarding, a personalized dashboard, notes and quizzes, Ask AI, exam assistance, Pomodoro focus sessions, progress tracking, and rewards.

## Run locally

1. Create a virtual environment and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add your OpenRouter API key.

3. Start the app:

   ```bash
   python main.py
   ```

4. Open `http://127.0.0.1:5000`.

## Deploy on Render

This repository includes a `render.yaml` Blueprint. Connect the GitHub repository to Render, add `OPENROUTER_API_KEY`, and deploy. After deployment, add the public Render domain to Firebase Authentication's authorized domains.

Private `.env` values are excluded from GitHub.

