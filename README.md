# my-first-ai-app

Personal AI lab — starting with a **WK2 garage log** for a 2014 Jeep Grand Cherokee 3.0 diesel.

Dump notes in plain English. The app stores structured history you can search and build on later.

## Quick start

```bash
pip install -r requirements.txt
python garage.py profile
python garage.py add "Oil and filter at 78,000 miles, £85 at local garage"
python garage.py log
```

### Optional: AI parsing

Without an API key, notes are saved as-is. With one, entries get structured (type, mileage, cost, tags):

```bash
export OPENAI_API_KEY="your-key-here"
python garage.py add "Replaced rear pads, squealing gone, 79k miles"
```

## What's next

- Maintenance reminders from mileage
- Mod / build planner
- Ask questions over your own log history (RAG)
